# Blog Summarizer - Implementation Plan

## Quick Summary
Automated workflow that fetches RSS feeds, summarizes articles using Gemini API, and generates Instagram-ready posts with gradient backgrounds. Deployed via **GitHub Actions** (free).

## Project Status - PHASE 1 COMPLETE

- [x] Project structure created
- [x] Config files created (feeds.yaml, prompts.yaml)
- [x] Environment files created (.env, .env.example)
- [x] config.py - Configuration management
- [x] database/models.py - SQLAlchemy models
- [x] database/repository.py - Data access layer
- [x] feeds/models.py - Pydantic models
- [x] feeds/manager.py - RSS feed fetching
- [x] feeds/selector.py - News ranking/selection
- [x] summarizer/gemini_client.py - Gemini API integration
- [x] images/background_generator.py - Gradient backgrounds
- [x] images/compositor.py - Image composition
- [x] images/text_renderer.py - Text overlay
- [x] main.py - Orchestrator
- [x] .github/workflows/generate-posts.yml - GitHub Actions workflow
- [x] .gitignore - Git ignore patterns
- [x] README.md - Documentation

## Phased Approach

### Phase 1 (Current): Content Generation Pipeline
RSS Feeds → Gemini Summarization → Image Generation → Save locally

### Phase 2 (Future/Optional): Instagram Integration
Approval Queue → Instagram Publishing

---

## Architecture

### Workflow Diagram
```
┌─────────────────────────────────────────────────────────────┐
│           GitHub Actions (Scheduled: every 6 hours)          │
└────────────┬────────────────────────────────────────────────┘
             │
             ├─► 1. RSS Feed Manager
             │      ├─► Fetch feeds (Tech/Business/News)
             │      └─► Parse & deduplicate items
             │
             ├─► 2. News Selector
             │      ├─► Filter new items (since last run)
             │      ├─► Rank by recency/quality/diversity
             │      └─► Select top 5 items
             │
             ├─► 3. For each selected item:
             │      ├─► Gemini Summarizer → title/description/caption
             │      ├─► Background Generator → gradient image
             │      └─► Image Compositor → 1080x1440 post
             │
             ├─► 4. Save outputs
             │      ├─► Images → data/generated/
             │      ├─► Metadata → data/posts.json
             │      └─► Commit to repo (optional)
             │
             └─► 5. Database (SQLite)
                    └─► Track processed items
```

### Project Structure
```
blog-summarizer/
├── .github/
│   └── workflows/
│       └── generate-posts.yml    # GitHub Actions workflow
│
├── src/
│   ├── __init__.py
│   ├── main.py                   # Entry point & orchestrator
│   ├── config.py                 # Configuration (pydantic)
│   │
│   ├── feeds/
│   │   ├── __init__.py
│   │   ├── manager.py            # RSS fetching & parsing
│   │   ├── selector.py           # Ranking & selection
│   │   └── models.py             # Pydantic models
│   │
│   ├── summarizer/
│   │   ├── __init__.py
│   │   └── gemini_client.py      # Gemini API integration
│   │
│   ├── images/
│   │   ├── __init__.py
│   │   ├── background_generator.py
│   │   ├── compositor.py         # Main image creation
│   │   └── text_renderer.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py             # SQLAlchemy models
│   │   └── repository.py         # Data access
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py
│
├── config/
│   ├── feeds.yaml                # RSS feed sources
│   └── prompts.yaml              # Gemini prompts
│
├── data/
│   ├── database.db               # SQLite (gitignored)
│   ├── generated/                # Output images
│   └── posts.json                # Generated post metadata
│
├── fonts/                        # Custom fonts (if needed)
├── .env                          # Local secrets (gitignored)
├── .env.example                  # Template for secrets
├── .gitignore
├── requirements.txt
├── PLAN.md                       # This file
└── README.md
```

---

## Technology Stack

### Core Dependencies (requirements.txt)
```
feedparser==6.0.10      # RSS parsing
aiohttp==3.9.1          # Async HTTP
google-generativeai>=0.8.0  # Gemini API
Pillow==10.1.0          # Image processing
requests==2.31.0        # HTTP requests
sqlalchemy==2.0.23      # Database ORM
pydantic==2.5.0         # Data validation
pydantic-settings==2.1.0
python-dotenv==1.0.0    # Env vars
pyyaml==6.0.1           # YAML config
loguru==0.7.2           # Logging
rich==13.7.0            # CLI output
aiofiles==23.2.1        # Async file ops
```

### External Services
| Service | Cost | Usage |
|---------|------|-------|
| Gemini API | FREE | 15 RPM, 1,500/day |
| GitHub Actions | FREE | 2,000 min/month |
| SQLite | FREE | Local database |

---

## Configuration

### Environment Variables (.env)
```bash
# Required
GEMINI_API_KEY=your_key_here

# Optional
DATABASE_URL=sqlite:///data/database.db
TOP_N_ITEMS=5
GEMINI_MODEL=gemini-2.0-flash-exp
LOG_LEVEL=INFO
```

### GitHub Actions Secrets
Add these in repo Settings → Secrets → Actions:
- `GEMINI_API_KEY` - Your Gemini API key

### RSS Feeds (config/feeds.yaml)
```yaml
feeds:
  - url: "https://techcrunch.com/feed/"
    category: "technology"
    priority: 1.2
    enabled: true
  # ... more feeds

categories:
  technology:
    gradient_colors: ["#667eea", "#764ba2"]
  business:
    gradient_colors: ["#f093fb", "#f5576c"]
  news:
    gradient_colors: ["#4facfe", "#00f2fe"]
```

---

## Implementation Details

### 1. Config Management (src/config.py)
- Load .env variables using pydantic-settings
- Load YAML configs (feeds.yaml, prompts.yaml)
- Provide typed access to all settings

### 2. Database Models (src/database/models.py)
Tables:
- **feeds**: id, url, category, priority, enabled, last_fetched
- **feed_items**: id (hash), feed_id, title, link, description, published_date, image_url, status
- **summaries**: id, feed_item_id, title, description, caption, hashtags
- **posts**: id, summary_id, image_path, status, created_at
- **processing_runs**: id, started_at, completed_at, items_processed, status

### 3. RSS Feed Manager (src/feeds/manager.py)
- Async fetch all enabled feeds
- Parse with feedparser
- Deduplicate by hashing title+link
- Store new items in database

### 4. News Selector (src/feeds/selector.py)
- Filter items not yet processed
- Score by: recency, source priority, category diversity
- Select top N items
- Mark as selected in database

### 5. Gemini Summarizer (src/summarizer/gemini_client.py)
- Initialize Gemini client with API key
- Send article to Gemini with prompt from prompts.yaml
- Parse JSON response (title, description, caption, hashtags)
- Retry on failure with exponential backoff

### 6. Image Generation (src/images/)

**background_generator.py**:
- Create 1080x1080 gradient image
- Use category colors from feeds.yaml
- Support linear gradients (top to bottom)

**text_renderer.py**:
- Render title (bold, 60px, centered)
- Render description (regular, 36px, centered)
- Add text shadow for readability
- Handle text wrapping

**compositor.py**:
- Combine background + foreground image (if available) + text
- Layout: 1080x1440 (4:5 Instagram portrait ratio)
  ```
  ┌─────────────────────────┐
  │     [60px margin]       │
  │  ┌─────────────────┐    │
  │  │ Foreground Img  │    │  ← Max 750px height
  │  │                 │    │
  │  └─────────────────┘    │
  │    Glass Card with:     │
  │      TITLE TEXT         │
  │   Description text      │
  │     Source badge        │
  │     [bottom margin]     │
  └─────────────────────────┘
  ```
- Save to data/generated/post_{timestamp}.png

### 7. Main Orchestrator (src/main.py)
```python
async def main():
    # 1. Load config
    # 2. Initialize database
    # 3. Create processing run record
    # 4. Fetch RSS feeds
    # 5. Select top N items
    # 6. For each item:
    #    - Generate summary (Gemini)
    #    - Create image
    #    - Save to database
    # 7. Export posts.json with metadata
    # 8. Mark run complete
```

CLI usage:
```bash
python -m src.main              # Run full workflow
python -m src.main --test-feeds # Test RSS fetching only
python -m src.main --test-image # Generate test image
```

### 8. GitHub Actions Workflow (.github/workflows/generate-posts.yml)
```yaml
name: Generate Instagram Posts

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:        # Manual trigger

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run generator
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python -m src.main

      - name: Upload generated posts
        uses: actions/upload-artifact@v4
        with:
          name: generated-posts
          path: data/generated/

      - name: Commit results (optional)
        run: |
          git config user.name github-actions
          git config user.email github-actions@github.com
          git add data/posts.json
          git diff --quiet && git diff --staged --quiet || git commit -m "Update generated posts"
          git push
```

---

## Output Format

### Generated Image
- Filename: `data/generated/post_{timestamp}_{item_id}.png`
- Dimensions: 1080x1440 pixels (4:5 ratio - Instagram portrait)
- Format: PNG

### Posts Metadata (data/posts.json)
```json
{
  "generated_at": "2024-01-22T12:00:00Z",
  "run_id": 1,
  "posts": [
    {
      "id": 1,
      "source": "TechCrunch",
      "original_title": "...",
      "original_url": "...",
      "generated_title": "...",
      "generated_description": "...",
      "caption": "...",
      "hashtags": ["...", "..."],
      "image_path": "data/generated/post_123_abc.png",
      "category": "technology",
      "created_at": "2024-01-22T12:00:00Z"
    }
  ]
}
```

---

## Verification Steps

### Test RSS Fetching
```bash
python -m src.main --test-feeds
```
Expected: Prints fetched items from all enabled feeds

### Test Summarization
```bash
python -m src.main --test-summary
```
Expected: Generates summary for a sample article

### Test Image Generation
```bash
python -m src.main --test-image
```
Expected: Creates test image at data/generated/test.png

### Full Workflow Test
```bash
python -m src.main
```
Expected: Generates 5 posts in data/generated/

### GitHub Actions Test
1. Push code to GitHub
2. Go to Actions tab → "Generate Instagram Posts"
3. Click "Run workflow" (manual trigger)
4. Check artifacts for generated images

---

## Files to Create (Implementation Order)

1. **src/config.py** - Configuration management
2. **src/utils/logger.py** - Logging setup
3. **src/database/models.py** - SQLAlchemy models
4. **src/database/repository.py** - Data access layer
5. **src/feeds/models.py** - Pydantic models for feeds
6. **src/feeds/manager.py** - RSS fetching
7. **src/feeds/selector.py** - Item selection
8. **src/summarizer/gemini_client.py** - Gemini integration
9. **src/images/background_generator.py** - Gradients
10. **src/images/text_renderer.py** - Text overlay
11. **src/images/compositor.py** - Image composition
12. **src/main.py** - Orchestrator
13. **.github/workflows/generate-posts.yml** - GitHub Actions
14. **.gitignore** - Ignore patterns
15. **README.md** - User documentation

---

## Cost Summary

| Item | Cost |
|------|------|
| Gemini API | $0 (free tier) |
| GitHub Actions | $0 (free tier) |
| Hosting | $0 (GitHub) |
| **Total** | **$0/month** |

---

## Future Enhancements (Phase 2+)

- [ ] Instagram auto-posting via instagrapi
- [ ] Approval queue (web UI or CLI)
- [ ] Multiple image templates/layouts
- [ ] AI-generated backgrounds (Stability AI)
- [ ] Multi-platform support (Twitter, LinkedIn)
- [ ] Analytics dashboard
- [ ] Carousel post support
