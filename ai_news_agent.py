"""
ai_news_agent.py

ai news agent (v1.2)

fetches ai-related rss/atom feeds, extracts article content, generates short
bullet summaries and keyword tags (using gemini llm or local heuristics),
and pushes unique entries to a notion database.

environment variables control behavior (see .env.example and readme.md).
written for reliability and minimal dependencies.
"""

import os
import re
import time
import json
import hashlib
import logging
import pathlib
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtparser
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode
import urllib.robotparser

import requests
from requests.adapters import HTTPAdapter, Retry
import feedparser
import certifi
from notion_client import Client
from dotenv import load_dotenv

# env & config
load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("ai-news-agent")

DEFAULT_FEED_NAME = "AI News"
DEFAULT_FEED_URL = "https://artificialintelligence-news.com/feed/"

DAYS_BACK = int(os.getenv("DAYS_BACK", "3"))
MAX_PER_FEED = int(os.getenv("MAX_PER_FEED", "10"))
TOTAL_LIMIT = int(os.getenv("TOTAL_LIMIT", "50"))

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_VERSION = os.getenv("NOTION_VERSION", "2022-06-28")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}" if NOTION_TOKEN else "",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

TAGS_ENABLED = os.getenv("TAGS_ENABLED", "true").lower() == "true"
TAGS_MAX = int(os.getenv("TAGS_MAX", "4"))

ENABLE_SUMMARY = os.getenv("ENABLE_SUMMARY", "true").lower() == "true"
SUMMARY_BULLETS = int(os.getenv("SUMMARY_BULLETS", "5"))
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", "6000"))
SUMMARIZER = os.getenv("SUMMARIZER", "google").lower()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# optional dependencies
_have_trafilatura = False
try:
    import trafilatura
    _have_trafilatura = True
except Exception:
    pass

_have_bs4 = False
try:
    from bs4 import BeautifulSoup
    _have_bs4 = True
except Exception:
    pass

_have_gemini = False
try:
    import google.generativeai as genai
    _have_gemini = True
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
except Exception:
    pass

# agent meta
AGENT_NAME = "AI-News-Agent"
AGENT_VERSION = "1.2"
AGENT_URL = "https://github.com/moniburnejko/ai-news-agent"
CUSTOM_USER_AGENT = f"{AGENT_NAME}/{AGENT_VERSION} (+{AGENT_URL})"

# cache
CACHE_PATH = pathlib.Path(".cache/feeds.json")
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
try:
    FEED_CACHE: Dict[str, Dict[str, str]] = json.loads(CACHE_PATH.read_text())
except Exception:
    FEED_CACHE = {}

# http session
def make_session() -> requests.Session:
    """
    create a requests.Session with retry behavior and a custom user-agent.

    returns:
        requests.Session: configured session with mounted http adapters.

    notes:
        - retry configuration is set conservatively for 429 and common 5xx errors.
        - this function attempts to set 'allowed_methods' in a backwards-compatible
          way so it works with different urllib3 versions.
    """
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
    try:
        retries.allowed_methods = frozenset(["GET", "POST"])
    except Exception:
        try:
            retries.method_whitelist = frozenset(["GET", "POST"])  # type: ignore
        except Exception:
            pass
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": CUSTOM_USER_AGENT})
    return s

SESSION = make_session()

# utilitties
def canonical_url(u: Optional[str]) -> str:
    """
    normalize a url for deduplication and canonical storage.

    - lowercases scheme and netloc.
    - removes known tracking query parameters (utm_*, gclid, fbclid).
    - removes fragment.
    - ensures path is not empty ("/" fallback).
    - sorts query parameters deterministically while preserving repeated keys
      using urlencode(..., doseq=True).

    args:
        u: raw url string

    returns:
        normalized url string (empty string if input falsey)
    """
    if not u:
        return ""
    try:
        p = urlsplit(u)
    except Exception:
        return u or ""
    track_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_name", "gclid", "fbclid"}
    q_pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in track_params]
    query = urlencode(sorted(q_pairs), doseq=True)
    clean = p._replace(
        scheme=p.scheme.lower(),
        netloc=p.netloc.lower(),
        path=(p.path.rstrip("/") or "/"),
        query=query,
        fragment="",
    )
    return urlunsplit(clean)

def normalize_text(s: Optional[str]) -> str:
    """
    collapse whitespace to single spaces and trim.

    args:
        s: input string or none

    returns:
        cleaned string
    """
    return re.sub(r"\s+", " ", s or "").strip()

def url_uid(url: str) -> str:
    """
    create a short, stable uid for a url based on a canonicalized form.
    """
    c = canonical_url(url or "")
    return hashlib.sha1(c.encode("utf-8")).hexdigest()[:12]

def parse_date(entry: Dict[str, Any]) -> Optional[datetime]:
    """
    parse a published/updated date from a feedparser entry.

    tries several common keys (published, updated, dc_date) and falls back to
    published_parsed (struct_time). ensures returned datetime is timezone-aware
    and converted to utc.

    args:
        entry: feedparser entry mapping

    returns:
        datetime in utc or none if not parseable
    """
    for key in ("published", "updated", "dc_date"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                dt = dtparser.parse(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                continue
    try:
        tp = entry.get("published_parsed") or getattr(entry, "published_parsed", None)
        if tp:
            import time as _time
            return datetime.fromtimestamp(_time.mktime(tp), tz=timezone.utc)
    except Exception:
        pass
    return None

def within_days(published_dt: Optional[datetime], days: int) -> bool:
    """
    check whether the provided datetime is within the last `days` days.

    accepts none (treats as true so items without dates are not dropped).
    """
    if not published_dt:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return published_dt >= cutoff

# robots.txt
def check_robots_permission(url: str, user_agent: str = AGENT_NAME) -> bool:
    """
    check robots.txt for permission to fetch a given url.

    - fetches /robots.txt from the target host and parses it with the
      standard urllib.robotparser.
    - on network/parse errors returns true (permissive) to avoid blocking
      basic scraping.

    args:
        url: full URL to check
        user_agent: agent name used to test allow/disallow

    returns:
        true if allowed or robots.txt cannot be read; false if explicitly disallowed.
    """
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc.lower()}"
        robots_url = f"{base}/robots.txt"
        resp = SESSION.get(robots_url, timeout=10, verify=certifi.where())
        if resp.status_code != 200:
            return True
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(resp.text.splitlines())
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True

# feed loader
def load_feed(url: str):
    """
    fetch and parse an rrs/atom feed with etag/last-modified caching.

    - uses FEED_CACHE to provide If-None-Match / If-Modified-Since headers.
    - updates FEED_CACHE with new ETag/Last-Modified values on success.
    - returns (feedparser-parsed-object, None) on success, or (None, error_msg).

    args:
        url: feed url to fetch

    rturns:
        tuple(feed, error_msg) where error_msg is none on success.
    """
    headers = {"User-Agent": CUSTOM_USER_AGENT}
    cache = FEED_CACHE.get(url, {})
    if "etag" in cache:
        headers["If-None-Match"] = cache["etag"]
    if "modified" in cache:
        headers["If-Modified-Since"] = cache["modified"]
    try:
        r = SESSION.get(url, headers=headers, timeout=20, verify=certifi.where())
        if r.status_code == 304:
            log.info("[FEED] 304 Not Modified (cache)")
            return {"entries": []}, None
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        feed = feedparser.parse(r.content)
        FEED_CACHE[url] = {
            "etag": r.headers.get("ETag"),
            "modified": r.headers.get("Last-Modified"),
        }
        CACHE_PATH.write_text(json.dumps(FEED_CACHE, indent=2))
        time.sleep(1.0)
        return feed, None
    except Exception as e:
        return None, str(e)

# article extraction
def extract_article_text(url: str) -> str:
    """
    extract the main article text for a given url.

    strategy and fallbacks:
      1. respect robots.txt.
      2. use trafilatura if available (recommended).
      3. if trafilatura not available, fetch HTML and use BeautifulSoup
         (if installed) to extract <p> content while removing common
         non-content tags.
      4. as a last resort, return the raw body text (normalized).

    returns an empty string on any failure or when blocked by robots.

    args:
      url: full article url

    returns:
      normalized plaintext string (may contain html if BeautifulSoup not available)
    """
    try:
        if not check_robots_permission(url):
            return ""
        if _have_trafilatura:
            d = trafilatura.fetch_url(url)
            if d:
                text = trafilatura.extract(d)
                return normalize_text(text)
        r = SESSION.get(url, timeout=20, verify=certifi.where(), headers={"User-Agent": CUSTOM_USER_AGENT})
        if r.status_code != 200:
            return ""
        body = r.text or ""
        if _have_bs4 and body:
            soup = BeautifulSoup(body, "lxml")
            for t in soup(["script", "style", "nav", "header", "footer", "form", "aside"]):
                t.decompose()
            paragraphs = [normalize_text(p.get_text(" ", strip=True)) for p in soup.find_all("p")]
            return " ".join(p for p in paragraphs if p)
        return normalize_text(body)
    except Exception:
        return ""

# gemini keywords
def keywords_google(text: str, n: int = 4) -> list[str]:
    """
    use google gemini (if configured) to extract a short list of topical tags.

    args:
        text: article text to extract keywords from (preferably cleaned)
        n: desired number of tags

    returns:
        list of lowercase tag strings (may be fewer than n if llm output is noisy
        or if gemini is not available).
    """
    if not (_have_gemini and GOOGLE_API_KEY):
        return []
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            "Extract topical keywords from the article. "
            f"Return EXACTLY {n} short tags, lowercased, no hashtags, no emojis. "
            "Prefer domain terms (e.g., 'diffusion models', 'rag', 'inference'). "
            "Output as comma-separated list only.\n\n"
            f"Article:\n{text[:SUMMARY_MAX_CHARS]}"
        )
        resp = model.generate_content(prompt)
        raw = (getattr(resp, "text", "") or "").strip()
        # parse: split commas, trim, keep 1–3 words per tag
        parts = [normalize_text(p) for p in re.split(r"[,\n]", raw)]
        tags = []
        for p in parts:
            p = re.sub(r"^[#\-\*\d\.\)\s]+", "", p)
            if not p:
                continue
            if len(p.split()) > 3:
                continue
            tags.append(p.lower())
        out = []
        seen = set()
        for t in tags:
            if t and t not in seen:
                seen.add(t)
                out.append(t)
            if len(out) >= n:
                break
        return out
    except Exception as e:
        log.warning("[Gemini] tags failed: %s", e)
        return []

# gemini summary
def bullets_google(text: str, k: int = SUMMARY_BULLETS) -> List[str]:
    """
    produce k concise bullet points using google gemini (if configured).

    the function returns an empty list if Gemini is not available or if the
    summarization fails; callers should fall back to local heuristics.

    args:
        text: article text to summarize
        k: number of bullets requested

    returns:
        list of bullet strings (<= k)
    """
    if not (_have_gemini and GOOGLE_API_KEY):
        return []
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            "Summarize this article into exactly "
            f"{k} concise bullet points. Each bullet should be a full sentence (max 30 words), no emojis, no markdown.\n\n"
            f"Article:\n{text[:SUMMARY_MAX_CHARS]}"
        )
        response = model.generate_content(prompt)
        content = (getattr(response, "text", None) or "").strip()
        if not content:
            return []
        lines = [normalize_text(l) for l in content.split("\n")]
        bullets: List[str] = []
        for l in lines:
            l = re.sub(r"^[-*\d\.\)\s]+", "", l)
            if l:
                bullets.append(l)
        return bullets[:k]
    except Exception as e:
        log.warning("[Gemini] summarization failed: %s", e)
        return []

# local fallback
def fallback_bullets(text: str, k: int = SUMMARY_BULLETS) -> List[str]:
    """
    simple local summarization fallback: pick 1..k sentences from the article.

    heuristic:
    - split on sentence boundaries (., !, ?).
    - keep sentences between 40 and 400 characters to avoid trivial or huge fragments.

    args:
        text: article text
        k: number of bullets to return

    returns:
        list of extracted sentence strings (<= k)
    """
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if 40 <= len(s) <= 400]
    return sentences[:k]

def build_bullets(text: str, k: int = SUMMARY_BULLETS) -> List[str]:
    """
    build bullet summaries, using configured summarizer then falling back locally.

    args:
        text: article text
        k: number of bullets desired

    returns:
        list of bullet strings
    """
    if not ENABLE_SUMMARY or not text:
        return []
    if SUMMARIZER == "google":
        b = bullets_google(text, k)
        return b if b else fallback_bullets(text, k)
    return fallback_bullets(text, k)

# notion
def get_notion_client() -> Client:
    """
    return a configured notion client.

    raises:
        RuntimeError: if NOTION_TOKEN or NOTION_DATABASE_ID are missing.

    notes:
        the wrapper centralizes notion sdk creation so other functions can call it
        once the environment is validated.
    """
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        raise RuntimeError("Missing NOTION_TOKEN or NOTION_DATABASE_ID.")
    return Client(auth=NOTION_TOKEN)

def notion_has_item(uid: str, url: str) -> Optional[bool]:
    """
    query the notion database to determine whether an item already exists.

    returns:
        true if exists, false if not found, none if the query failed transiently.

    notes:
        returning none allows callers to make a conservative decision (skip push)
        to avoid creating duplicates when the query is unreliable.
    """
    payload = {"filter": {"or": [{"property": "UID", "rich_text": {"equals": uid}},
                                 {"property": "URL", "url": {"equals": url}}]}, "page_size": 1}
    try:
        r = SESSION.post(f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query",
                         headers=NOTION_HEADERS, json=payload, timeout=20, verify=certifi.where())
        if r.status_code != 200:
            log.warning("Notion query returned %s %s", r.status_code, r.text[:400])
            return False
        return len(r.json().get("results", [])) > 0
    except Exception as e:
        log.warning("Notion query failed: %s", e)
        return None

def create_page_in_notion(notion: Client, item: Dict[str, Any], tags: Optional[list[str]] = None) -> str:
    """
    create a new page in the configured notion database.

    args:
        notion: an instance of notion_client.Client
        item: dict with keys title, url, published, uid, source
        tags: optional list of tags to add to the multi-select 'Tags' property

    returns:
        the created notion page id

    notes:
        - this function assumes the notion database has properties named:
          Title, Published, URL, UID, Source, and optionally Tags.
        - errors from the notion sdk will propagate to the caller.
    """
    title = item.get("title") or "(no title)"
    url = canonical_url(item.get("url") or "")
    published = item.get("published")
    uid = item.get("uid")
    source = item.get("source") or DEFAULT_FEED_NAME

    published_iso = ((published or datetime.now(timezone.utc)).astimezone(timezone.utc)).isoformat()

    props = {
        "Title": {"title": [{"text": {"content": title}}]},
        "Published": {"date": {"start": published_iso}},
        "URL": {"url": url},
        "UID": {"rich_text": [{"text": {"content": uid}}]},
        "Source": {"select": {"name": source}},
    }
    if tags:
        props["Tags"] = {"multi_select": [{"name": t} for t in tags]}

    page = notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
    return page["id"]

def append_bullets_to_page(notion: Client, page_id: str, bullets: List[str]):
    """
    append a list of bulleted list blocks to a notion page.

    the notion api limits batch sizes; this function chunks children to 50.
    """
    if not bullets:
        return
    children = [
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": b}}]}
        }
        for b in bullets
    ]
    for i in range(0, len(children), 50):
        try:
            notion.blocks.children.append(block_id=page_id, children=children[i : i + 50])
        except Exception as e:
            log.warning("Failed to append bullets to page %s: %s", page_id, e)

def push_item_to_notion(notion: Client, item: Dict[str, Any], bullets: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> bool:
    """
    push an item to notion if it does not already exist.

    returns:
        true if a new page was created, false otherwise.

    behavior:
        - if notion_has_item returns none (transient error), this function logs and
          skips creation to avoid potential duplicates.
        - otherwise, it creates the page and appends bullets if provided.
    """
    url = canonical_url(item.get("url") or "")
    uid = item.get("uid") or ""
    exists = notion_has_item(uid, url)
    if exists is None:
        log.warning("Skipping push due to Notion query uncertainty for %s", url)
        return False
    if exists:
        return False
    page_id = create_page_in_notion(notion, item, tags=tags)
    if bullets:
        append_bullets_to_page(notion, page_id, bullets)
    return True


# fetch
def fetch_feed_items(
    feed_url: str = DEFAULT_FEED_URL,
    feed_name: str = DEFAULT_FEED_NAME,
    days_back: int = DAYS_BACK,
    max_per_feed: int = MAX_PER_FEED,
) -> List[Dict[str, Any]]:
    """
    fetch items from a single feed url, parse, filter by date and return a list
    of normalized item dicts.

    each item dict contains: source, title, url, published (datetime or none), uid.

    args:
        feed_url: url of the feed to fetch
        feed_name: human-friendly source name used when writing to notion
        days_back: drop items older than this many days
        max_per_feed: cap number of items returned per feed

    returns:
        list of item dicts (may be empty)
    """
    items: List[Dict[str, Any]] = []
    feed, err = load_feed(feed_url)
    if err:
        log.error("[FEED] %s (%s)", err, feed_url)
        return items
    entries = getattr(feed, "entries", None) or []
    log.info("[FEED] received entries: %d", len(entries))
    per_feed = 0
    for e in entries:
        if per_feed >= max_per_feed:
            break
        title = normalize_text(e.get("title", ""))
        link = canonical_url(e.get("link", ""))
        published_dt = parse_date(e)
        if not link:
            log.debug("[DROP] no link")
            continue
        if not within_days(published_dt, days_back):
            log.debug("[DROP] too old: %s", published_dt)
            continue
        items.append(
            {
                "source": feed_name,
                "title": title,
                "url": link,
                "published": published_dt,
                "uid": url_uid(link),
            }
        )
        per_feed += 1
    log.info("[FEED] kept: %d", len(items))
    return items

def sort_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    sort items by published date (newest first). items without dates are treated
    as the oldest (datetime.min). returns a new sorted list.
    """
    return sorted(items, key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

# main
def main():
    """
    main entrypoint for the script.

    - fetches items from the default feed (fetch_feed_items).
    - optionally extracts article text to build bullet summaries and tags.
    - pushes new items to notion (avoiding duplicates when possible).
    - logs a summary at the end.

    side effects:
      - network calls to feed / article hosts and notion.
      - updates .cache/feeds.json with ETag/Last-Modified headers.
    """
    items = sort_items(fetch_feed_items())[:TOTAL_LIMIT]
    if not items:
        log.warning("No new items found.")
        return
    notion = get_notion_client()
    added = 0
    for it in items:
        bullets: List[str] = []
        tags: List[str] = []
        txt = ""
        if ENABLE_SUMMARY or TAGS_ENABLED:
            txt = extract_article_text(it["url"])

        if ENABLE_SUMMARY and txt:
            bullets = build_bullets(txt[:SUMMARY_MAX_CHARS], SUMMARY_BULLETS)

        if TAGS_ENABLED and txt:
            tags = keywords_google(txt[:SUMMARY_MAX_CHARS], TAGS_MAX)

        ok = push_item_to_notion(notion, it, bullets, tags)
        if ok:
            added += 1
            log.info("+ %s | bullets: %d", it.get("title"), len(bullets))
        else:
            log.info("= SKIP | %s", it.get("title"))
    log.info("Done. Added %d/%d items.", added, len(items))

if __name__ == "__main__":
    main()