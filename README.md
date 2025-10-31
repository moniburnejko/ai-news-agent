## 📰 ai news agent
ai news agent is a lightweight python tool that automatically fetches the latest ai-related articles from rss/atom feeds, extracts the main content, summarizes each article into short bullet points, generates keyword tags, and pushes the structured results directly to a notion database.

### quick start
```bash
# clone the repository
git clone https://github.com/moniburnejko/ai-news-agent.git
cd ai-news-agent

# create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# create a `.env` file (or copy from `.env.example`) with your notion token, notion db id and any optionak keys

# run the agent
python ai_news_agent.py
```
that's it! the agent will fetch the default feed, extract content, build bullets/tags (if enabled) and push new pages to your notion database.

### example outputs and behavior
**primary outputs:**
- new notion pages created for unique feed items. each page contains:
  - Title (page title property)
  - Tags (multi-select, optional)
  - Source (select property)
  - Published (date property)
  - URL (url property)
  - UID (rich_text unique id)
  - bulleted summary blocks appended to the page body (optional)

**behavior summary:**
- feeds are fetched with conservative retries and etag/last-modified caching stored in `.cache/feeds.json`.
- items older than DAYS_BACK (default 3 days) are dropped.
- duplicate detection:
  - a stable uid is derived from the canonicalized url (sha1 prefix).
  - before creating a notion page the agent queries the notion db for existing uid or url.
  - if the notion query fails transiently, the agent conservatively skips creation to avoid duplicates.
- article extraction:
  - if `trafilatura` is available it is used for robust extraction.
  - otherwise falls back to fetching the html and extracting &lt;p&gt; using BeautifulSoup (if installed).
  - if nothing else works, it returns normalized page body text.
  - respects robots.txt when deciding to fetch full articles.
- summaries and tags:
  - if configured with google gemini (and GOOGLE_API_KEY present) the agent will call gemini for bullet summaries and keyword extraction.
  - if gemini is not configured or fails, a simple local heuristic picks 1..k sentences as bullets.
- notion api:
  - uses the notion sdk to create pages and append bullets in chunks.

**example notion page (simplified):**
- Title: "New AI paper shows xyz"
- Tags: ["retrieval-augmented-generation", "multimodal"]
- Source: AI News
- Published: 2025-10-31T12:00:00Z
- URL: https://example.com/ai-paper
- UID: 3f2a1b4c5d6e
- Body:
  - • sentence 1 summarizing main claim.
  - • sentence 2 summarizing method.
  - • sentence 3 summarizing results.

see examples/ for concrete sample inputs and outputs.

**why notion?**      
notion is my fav platform for organizing research and reading materials.  
using notion’s database view, each fetched article becomes a page - with tags, urls, and bullet summaries.  
this setup allows:
- filtering and sorting articles by tags, source, or date  
- adding your own notes, images, or screenshots under each entry  
- moving articles between folders (e.g., *read later*, *research*, *projects*)  
- connecting articles to other notion pages or dashboards  

in short, it’s not just an archive - it’s a growing, editable ai knowledge hub.

### architecture and modules
the agent is organized by responsibilities in `ai_news_agent.py`:

- **configuration & env**
  - loads env vars via `dotenv`, sets constants like DAYS_BACK, NOTION_*.

- **networking**
  - `make_session()` sets up a requests.Session with retries and custom User-Agent.

- **feed layer**
  - `load_feed(url)` — fetches feed with ETag/Last-Modified support; updates `.cache/feeds.json`.
  - `fetch_feed_items(...)` — parses `feedparser` entries, normalizes, filters by date and per-feed cap.

- **url & dedupe utilities**
  - `canonical_url(u)` — normalizes URLs (lowercase host, remove tracking params, remove fragments).
  - `url_uid(url)` — stable short UID from canonical URL (sha1 prefix).

- **extraction & robots**
  - `check_robots_permission(url)` — consults robots.txt and permits or blocks fetch.
  - `extract_article_text(url)` — uses trafilatura or BeautifulSoup fallback; returns cleaned text.

- **summarization & keywords**
  - `bullets_google`, `keywords_google` — call google gemini if configured.
  - `fallback_bullets` — local sentence-extraction fallback.
  - `build_bullets` — entry point to choose configured summarizer with fallbacks.

- **notion integration**
  - `get_notion_client()` — create notion_client.Client
  - `notion_has_item(uid, url)` — query db for existing items
  - `create_page_in_notion(notion, item, tags)` — creates page properties
  - `append_bullets_to_page(notion, page_id, bullets)` — appends bullets in batches
  - `push_item_to_notion(...)` — orchestrates existence check, creation and appending

- **orchestration / main loop**
  - `main()` — fetches feed items (sorted & limited), optionally extracts text, generates bullets & tags, pushes to notion and logs results.

**flow (high-level):**
1. fetch feed -> parse -> filter -> list of items
2. for each item (newest first, limited):
   - get article text (if needed)
   - build bullets & tags
   - check notion for duplicates
   - create notion page & append bullets
3. log summary and persist feed cache

### configuration reference    
the agent is configured primarily through environment variables. below is a reference of supported variables and their default values.

- NOTION_TOKEN (required for pushing to notion)
  - description: integration token with access to your database.
  - default: (none)
- NOTION_DATABASE_ID (required)
  - description: the notion database id where pages will be created.
  - default: (none)
- NOTION_VERSION
  - description: api version header used for notion requests.
  - default: 2022-06-28
- GOOGLE_API_KEY
  - description: key used by google.genai (gemini). optional; if missing gemini features disabled.
  - default: (none)
- TAGS_ENABLED
  - description: enable tag extraction (gemini). true/false
  - default: true
- TAGS_MAX
  - description: max tags to request/attach
  - default: 4
- ENABLE_SUMMARY
  - description: enable bullet summaries. true/false
  - default: true
- SUMMARY_BULLETS
  - description: number of bullets to produce
  - default: 5
- SUMMARY_MAX_CHARS
  - description: max chars of article passed to llm summarizer
  - default: 6000
- SUMMARIZER
  - description: "google" to use Gemini, otherwise local fallback
  - default: google
- DAYS_BACK
  - description: drop items older than this many days
  - default: 3
- MAX_PER_FEED
  - description: per-feed cap on items processed
  - default: 10
- TOTAL_LIMIT
  - description: global limit over fetched & sorted items
  - default: 50
- LOG_LEVEL
  - description: logging (DEBUG/INFO/WARNING/ERROR)
  - default: INFO

example `.env`:
```
NOTION_TOKEN=secret_xxx
NOTION_DATABASE_ID=abcd1234-ef56-7890-gh12-ijklmnopqrst
NOTION_VERSION=2022-06-28

# optional gemini (google) api key for better summaries and tags
GOOGLE_API_KEY=AIza...
SUMMARIZER=google

# behavior tuning
DAYS_BACK=3
MAX_PER_FEED=10
TOTAL_LIMIT=50
TAGS_ENABLED=true
TAGS_MAX=4
ENABLE_SUMMARY=true
SUMMARY_BULLETS=5
SUMMARY_MAX_CHARS=6000

LOG_LEVEL=INFO
```

### examples
the `examples/` folder contains representative sample inputs and outputs to help understand the agent behavior without running it.
- `examples/sample_feed_urls.txt` — a list of feeds (example)
- `examples/sample_article.html` — sample raw html for extraction testing
- `examples/sample_output.json` — sample output of the agent's internal item list + bullets + tags
- `examples/expected_notion_page.md` — how the created notion page would look in markdown form

see the examples folder for exact files and contents.

### troubleshooting & tips
- notion permissions: make sure the integration token is shared with the database (or the database is in a workspace the integration can access).
- robots: the agent respects robots.txt; if extraction returns empty text it may be due to robots rules.
- rate limits: gemini and notion have rate limits. the agent uses retries but if you process many feeds consider adding backoff or rate limiting.
- caching: `.cache/feeds.json` stores etag/last-modified values. you can delete it to force full refetch.

### future improvements
- add multi-feed support via feeds.yml (most important)
- add automated scheduling with github actions
- extend summarization options (anthropic, openai)
- implement sqlite-based local cache to reduce notion api calls
- add cli interface with argparse (feed selection, dry-run flag)
- integrate notifications (e.g., discord, email)
- add pytest unit tests and coverage reports

### contributing
pr and issues welcome! if adding a feature that affects the notion schema, update README and examples accordingly.

#### license
this project is released under the mit license.  

### let's connect!   
[![linkedin](https://img.shields.io/badge/linkedin-000000?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/monika-burnejko-9301a1357/) [![kaggle](https://img.shields.io/badge/kaggle-000000?style=for-the-badge&logo=kaggle&logoColor=white)](https://www.kaggle.com/monikaburnejko) [![portfolio](https://img.shields.io/badge/portfolio-000000?style=for-the-badge&logo=notion&logoColor=white)](https://www.notion.so/monikaburnejko/Data-Analytics-Portfolio-2761bac67ca9807298aee038976f0085) [![email](https://img.shields.io/badge/email-000000?style=for-the-badge&logo=gmail&logoColor=white)](mailto:moniaburnejko@gmail.com)
