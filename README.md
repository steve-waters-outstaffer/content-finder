# Content Finder

AI-powered content discovery and analysis pipeline for recruitment and EOR industry intelligence.

## Project Structure

```
content-finder/
├── backend/
│   ├── api/               # Flask API endpoints
│   │   ├── search.py      # Search endpoints
│   │   ├── scrape.py      # Scraping endpoints
│   │   └── analyze.py     # Analysis endpoints
│   ├── core/              # Core business logic
│   │   ├── firecrawl_client.py   # Firecrawl API wrapper
│   │   ├── gemini_client.py      # Gemini AI wrapper
│   │   └── pipeline.py           # Main pipeline orchestrator
│   ├── models/            # Data models and schemas
│   │   └── schemas.py
│   ├── utils/             # Utility functions
│   │   └── helpers.py
│   ├── app.py             # Flask application
│   └── requirements.txt   # Python dependencies
├── finder/                # Legacy scripts (to be deprecated)
├── cli.py                 # Command-line interface
└── README.md
```

## Features

- **Web Search**: Find relevant content using Firecrawl search API
- **Content Scraping**: Extract full content from web pages
- **Structured Extraction**: Extract structured data with custom schemas
- **AI Analysis**: Analyze content with Gemini AI for business insights
- **Pipeline Mode**: Run complete search → scrape → extract → analyze workflow
- **API Endpoints**: RESTful API for integration with frontend applications

## Quick Start

### Prerequisites

1. **Firecrawl API Key**: Get from [firecrawl.dev](https://firecrawl.dev)
2. **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/)

### Setup

```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export FIRECRAWL_API_KEY=your_firecrawl_key
export GEMINI_API_KEY=your_gemini_key
# Optional: override default Gemini models
export MODEL=gemini-2.5-flash
# export MODEL_PRO=gemini-2.5-pro
```

### Running the API Server

```bash
python app.py
```

The API will be available at `http://localhost:5000`

### Using the CLI

```bash
# Search only
python cli.py search --query "SMB hiring trends 2025" --limit 10

# Scrape specific URLs
python cli.py scrape --urls "https://example.com/article1" "https://example.com/article2"

# Analyze content
python cli.py analyze --content "Your content here"

# Run full pipeline
python cli.py pipeline --query "global talent acquisition" --max-urls 3
```

## API Endpoints

### Search
- `POST /api/search` - Search for content
- `POST /api/pipeline` - Run full content pipeline

### Scraping
- `POST /api/scrape` - Scrape URLs for content

### Analysis
- `POST /api/analyze` - Analyze content with AI

## Example API Usage

### Search for Content
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "SMB hiring trends 2025", "limit": 5}'
```

### Run Full Pipeline
```bash
curl -X POST http://localhost:5000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"query": "global talent acquisition", "max_urls": 3}'
```

## Configuration

Environment variables:
- `FIRECRAWL_API_KEY` - Required for search and scraping
- `GEMINI_API_KEY` - Required for AI analysis
- `MODEL` - Optional override for the default Gemini model (defaults to `gemini-2.5-flash`)
- `MODEL_PRO` - Optional override for tasks that require `gemini-2.5-pro`
- `FLASK_ENV` - Set to `development` for debug mode

## Development

The project is structured for easy extension:

1. **Add new extractors**: Create new clients in `core/`
2. **Add new endpoints**: Create new blueprints in `api/`  
3. **Extend schemas**: Modify `models/schemas.py`
4. **Add utilities**: Extend `utils/helpers.py`

## Next Steps

- [ ] React frontend integration
- [ ] Firestore data persistence
- [ ] Search term injection and curation
- [ ] Advanced filtering and categorization
- [ ] Automated scheduling and monitoring
