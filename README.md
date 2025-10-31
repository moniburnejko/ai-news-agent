# 📰 ai news agent
ai news agent is a lightweight python tool that automatically fetches the latest ai-related articles from rss/atom feeds, extracts the main content, summarizes each article into short bullet points, generates keyword tags, and pushes the structured results directly to a notion database.

## ⚙️ features
- fetches ai news from rss/atom feeds (etag and last-modified caching)
- extracts article content using `trafilatura` or `beautifulsoup`
- summarizes text using google gemini (optional) or local heuristics
- extracts keyword tags to simplify filtering and organization
- pushes structured entries (title, tags, source, url, date, uid, summary) to a notion database
- respects `robots.txt` and polite rate-limiting
- configurable behavior via `.env`

## 🚀 quick start
```bash
# clone the repository
git clone https://github.com/moniburnejko/ai-news-agent.git
cd ai-news-agent

# create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# create a `.env` file (or copy from `.env.example`) and add your credentials

# run
python ai_news_agent.py
```

## 🗂️ notion database
notion is my fav platform for organizing research and reading materials.  
using notion’s database view, each fetched article becomes a page - with tags, urls, and bullet summaries.  
this setup allows:
- filtering and sorting articles by tags, source, or date  
- adding your own notes, images, or screenshots under each entry  
- moving articles between folders (e.g., *read later*, *research*, *projects*)  
- connecting articles to other notion pages or dashboards  

in short, it’s not just an archive - it’s a growing, editable ai knowledge hub.

### database schema
| property | type | description |
|-----------|------|-------------|
| **Title** | title | article title |
| **Tags** | multi-select | extracted keywords |
| **Source** | select | feed source name |
| **URL** | url | canonical article url |
| **Published** | date | publication timestamp |
| **UID** | rich text | unique id (hash of url) |
| **Summary** | bulleted list (blocks) | ai-generated summary |

*(you can rename properties in notion, but keep the same types for compatibility)*

## configuration
all main options are set in `.env.example` - below are the most relevant ones:

| variable | description | default |
|-----------|--------------|----------|
| `DAYS_BACK` | number of days back to fetch articles | 3 |
| `MAX_PER_FEED` | max items per feed | 10 |
| `TOTAL_LIMIT` | global cap on items | 50 |
| `ENABLE_SUMMARY` | generate bullet summaries | true |
| `SUMMARY_BULLETS` | number of summary bullets | 5 |
| `SUMMARY_MAX_CHARS` | max text length for summarization | 6000 |
| `SUMMARIZER` | `google` or `local` | google |
| `TAGS_ENABLED` | extract keyword tags | true |
| `TAGS_MAX` | max number of tags | 4 |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | INFO |

## requirements
```
requests
feedparser
notion-client
python-dotenv
python-dateutil
certifi

# optional (recommended)
trafilatura
beautifulsoup4
google-genai
```

## notes
- `.cache/feeds.json` stores feed etag and last-modified headers to avoid refetching unchanged feeds.
- `.env` must never be committed to git (contains private keys).
- the agent respects `robots.txt` rules and uses polite delays.
- notion writes use official api with version `2022-06-28`.
- for testing, you can clear cache with:
  ```bash
  rm -rf .cache/feeds.json
  ```

## ✨ future improvements
- add multi-feed support via feeds.yml (most important)
- add automated scheduling with github actions
- extend summarization options (anthropic, openai)
- implement sqlite-based local cache to reduce notion api calls
- add cli interface with argparse (feed selection, dry-run flag)
- integrate notifications (e.g., discord, email)
- add pytest unit tests and coverage reports

### license
this project is released under the **mit license**.  

## let's connect!   
[![linkedin](https://img.shields.io/badge/linkedin-000000?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/monika-burnejko-9301a1357/) [![kaggle](https://img.shields.io/badge/kaggle-000000?style=for-the-badge&logo=kaggle&logoColor=white)](https://www.kaggle.com/monikaburnejko) [![portfolio](https://img.shields.io/badge/portfolio-000000?style=for-the-badge&logo=notion&logoColor=white)](https://www.notion.so/monikaburnejko/Data-Analytics-Portfolio-2761bac67ca9807298aee038976f0085) [![email](https://img.shields.io/badge/email-000000?style=for-the-badge&logo=gmail&logoColor=white)](mailto:moniaburnejko@gmail.com)
