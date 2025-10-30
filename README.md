# 🤖 ai news agent

fetches ai-related rss/atom feeds, extracts article text, generates concise
bullet-point summaries and topical tags, and pushes structured entries to a
notion database.

### features
- fetches feeds with etag/last-modified caching  
- extracts full article text (trafilatura or beautifulsoup fallback)  
- summarizes with google gemini or local fallback  
- extracts keyword tags for notion filtering  
- deduplicates by uid/url and respects robots.txt  

### quick start
```bash
# clone repo and enter directory
git clone https://github.com/moniburnejko/ai-news-agent.git
cd ai-news-agent

# create and activate virtualenv
python -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt
```

### environment setup
create `.env`
```bash
NOTION_TOKEN=secret_xxx
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LOG_LEVEL=INFO
ENABLE_SUMMARY=true
SUMMARIZER=google
GOOGLE_API_KEY=AIza...     # only if using gemini summarizer
```

### run
```bash
python ai_news_agent.py
```

**example output**
```

```

### notion database schema
| property | type |
|-----------|------|
| Title | title |
| Tags | multi-select |
| Source | select |
| URL | url | 
| Published | date |
| UID | rich text |


### configuration
| variable | description | default |
|-----------|--------------|----------|
| `DAYS_BACK` | how many days back to fetch | 7 |
| `MAX_PER_FEED` | per-feed limit | 10 |
| `TOTAL_LIMIT` | total items cap | 50 |
| `ENABLE_SUMMARY` | generate summaries | true |
| `SUMMARY_BULLETS` | number of bullets | 5 |
| `SUMMARY_MAX_CHARS` | max text length | 6000 |
| `TAGS_ENABLED` | extract tags | true |
| `TAGS_MAX` | hnumber of tags | 4 |

### requirements
```
# core:
requests>=2.28.0
feedparser>=6.0.8
python-dateutil>=2.8.2
python-dotenv>=1.0.0
certifi>=2023.5.7
notion-client>=0.14.1

# optional but recommended:
beautifulsoup4>=4.12.2
trafilatura>=1.0.5

# optional for google gemini summarizer and keywords:
google-generativeai>=1.0.0
```

### notes
- `.cache/feeds.json` stores ETag and Last-Modified info  
- `.env` is ignored by git
- respects site robots.txt and polite rate-limiting  

### license
this project is released under the **mit license**.  

## connect
👩‍💻 **Monika Burnejko**  
junior data analyst       
📧 [monikaburnejko@gmail.com](mailto:monikaburnejko@gmail.com)  
💼 [linkedin](https://www.linkedin.com/in/monika-burnejko-9301a1357)  
🌐 [portfolio](https://www.notion.so/monikaburnejko/Data-Analytics-Portfolio-2761bac67ca9807298aee038976f0085?pvs=9)
