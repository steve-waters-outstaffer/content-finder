# Content Finder - Intelligence Engine

## Backend Structure (Clean & Organized)

```
backend/
├── api/                    # Flask API endpoints
│   ├── search.py          # Content search
│   ├── scrape.py          # URL scraping  
│   ├── analyze.py         # AI content analysis
│   └── intelligence.py    # Intelligence engine API
├── core/                  # Core pipeline components
│   ├── pipeline.py        # Main content pipeline
│   ├── firecrawl_client.py # Firecrawl integration
│   └── gemini_client.py   # Gemini AI integration
├── intelligence/          # Intelligence engine (MOVED HERE)
│   ├── intelligence_engine.py # Main intelligence engine
│   ├── enhanced_firecrawl_search.py # Enhanced search
│   └── config/
│       ├── intelligence_config.json # Clean config
│       └── prompts/       # Segment-specific prompts
├── models/               # Data models
├── utils/                # Utility functions
└── app.py               # Flask application entry point
```

## What Was Cleaned Up

### ✅ **Moved to Backend:**
- `intelligence/` → `backend/intelligence/`
- All intelligence logic now integrated with core pipeline
- Config files cleaned and simplified

### ✅ **Removed/Consolidated:**
- `finder/` directory (old duplicate code)
- Root-level processing scripts (now in backend)
- Malformed JSON configs

### ✅ **Improved Configuration:**
- Clean, consistent JSON structure
- Removed duplicate entries
- Added missing prompt files
- Standardized segment definitions

## Usage

### API Endpoints:
```
GET  /api/intelligence/config
POST /api/intelligence/process-segment
POST /api/intelligence/run-all
GET  /api/intelligence/logs
GET  /api/intelligence/results
```

### Command Line:
```bash
# Run all segments
python cli.py

# Run specific segment
python cli.py smb_leaders
python cli.py "SMB Leaders"
```

### Direct Import:
```python
from backend.intelligence.intelligence_engine import IntelligenceEngine

engine = IntelligenceEngine()
results = engine.run_all_segments()
```

## Configuration Structure

```json
{
  "defaults": {
    "scrape_limit": 3,
    "time_filter": "qdr:m"
  },
  "segments": {
    "smb_leaders": {
      "name": "SMB Leaders",
      "prompt_file": "segment_smb_leaders.json",
      "searches": [...]
    }
  }
}
```

## Next Steps

1. **Test the reorganized structure**
2. **Run intelligence engine via API**
3. **Verify all endpoints work**
4. **Add any missing segment configurations**
