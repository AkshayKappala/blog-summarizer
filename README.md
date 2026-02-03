# Blog Summarizer

Automated workflow that fetches RSS feeds, summarizes articles using Gemini API, and generates Instagram-ready posts with gradient backgrounds. Runs for **free** on GitHub Actions.

## Features

- **RSS Feed Aggregation**: Fetches from multiple sources (Tech, Business, News)
- **AI Summarization**: Uses Gemini API to generate catchy titles, descriptions, and captions
- **Image Generation**: Creates 1080x1440 Instagram posts (4:5 ratio) with gradient backgrounds
- **Automated Scheduling**: Runs every 6 hours via GitHub Actions
- **Zero Cost**: Uses free tiers of Gemini API and GitHub Actions

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/blog-summarizer.git
cd blog-summarizer
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Keys

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Gemini API key
# Get your key from: https://aistudio.google.com/app/apikey
```

### 4. Run Locally

```bash
# Full workflow
python -m src.main

# Test components individually
python -m src.main --test-feeds    # Test RSS fetching
python -m src.main --test-summary  # Test Gemini summarization
python -m src.main --test-image    # Test image generation
```

## GitHub Actions Deployment

### Setup

1. Push this repository to GitHub
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Add secret: `GEMINI_API_KEY` = your Gemini API key

### Run

- **Automatic**: Runs every 6 hours
- **Manual**: Go to **Actions** tab → **Generate Instagram Posts** → **Run workflow**

### Get Results

Generated posts are available as:
- **Artifacts**: Download from Actions run page
- **posts.json**: Committed to repository with metadata

## Project Structure

```
blog-summarizer/
├── src/
│   ├── main.py              # Entry point & orchestrator
│   ├── config.py            # Configuration management
│   ├── feeds/               # RSS feed processing
│   ├── summarizer/          # Gemini API integration
│   ├── images/              # Image generation
│   ├── database/            # SQLite storage
│   └── utils/               # Logging utilities
├── config/
│   ├── feeds.yaml           # RSS feed sources
│   └── prompts.yaml         # Gemini prompts
├── data/
│   ├── generated/           # Output images
│   └── posts.json           # Post metadata
├── .github/workflows/       # GitHub Actions
├── requirements.txt
└── .env                     # API keys (not committed)
```

## Configuration

### RSS Feeds (`config/feeds.yaml`)

```yaml
feeds:
  - url: "https://techcrunch.com/feed/"
    category: "technology"
    priority: 1.2
    enabled: true
```

### Environment Variables (`.env`)

```bash
GEMINI_API_KEY=your_key_here   # Required
TOP_N_ITEMS=5                   # Posts per run
GEMINI_MODEL=gemini-2.0-flash-exp
```

## Output

### Generated Image (1080x1440)

- Gradient background based on category
- Foreground image from article (if available)
- AI-generated title and description
- Category badge

### posts.json

```json
{
  "generated_at": "2024-01-22T12:00:00Z",
  "posts": [
    {
      "generated_title": "AI Revolution Transforms Tech",
      "generated_description": "New breakthrough promises...",
      "caption": "The future is here! #AI #Tech",
      "image_path": "data/generated/post_123.png",
      "category": "technology"
    }
  ]
}
```

## Cost

| Service | Cost |
|---------|------|
| Gemini API | Free (1,500 requests/day) |
| GitHub Actions | Free (2,000 min/month) |
| **Total** | **$0/month** |

## Future Enhancements

- [ ] Instagram auto-posting
- [ ] Web-based approval queue
- [ ] Multiple image templates
- [ ] Multi-platform support (Twitter, LinkedIn)

## License

MIT
