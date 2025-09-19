"""Data models and schemas"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class SearchResult:
    """Search result data structure"""
    query: str
    results: List[Dict[str, Any]]
    timestamp: str
    total_results: int


@dataclass
class ScrapeResult:
    """Scraping result data structure"""
    url: str
    success: bool
    scraped_at: str
    title: Optional[str] = None
    description: Optional[str] = None
    markdown: Optional[str] = None
    html: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ExtractionResult:
    """Structured extraction result"""
    success: bool
    extracted_at: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class AnalysisResult:
    """AI analysis result"""
    success: bool
    analyzed_at: str
    source_url: Optional[str] = None
    analysis: Optional[str] = None
    model: str = "gemini-2.5-flash"
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Complete pipeline execution result"""
    query: str
    timestamp: str
    max_urls: int
    urls: List[str]
    steps: Dict[str, Any]
    error: Optional[str] = None


# Schema definitions for structured extraction
DEFAULT_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Article title"},
        "summary": {"type": "string", "description": "Executive summary of the content"},
        "key_insights": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of key insights and trends mentioned"
        },
        "challenges_mentioned": {
            "type": "array", 
            "items": {"type": "string"},
            "description": "Hiring challenges or pain points discussed"
        },
        "strategies_solutions": {
            "type": "array",
            "items": {"type": "string"}, 
            "description": "Strategies, solutions, or recommendations provided"
        },
        "statistics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Important statistics, percentages, or data points"
        },
        "relevance_to_eor": {
            "type": "string", 
            "description": "How this content relates to EOR/global hiring services"
        }
    },
    "required": ["title", "summary", "key_insights"]
}

# Default analysis prompt for Outstaffer context
DEFAULT_ANALYSIS_PROMPT = """
Analyze this scraped web content and provide:

1. **Executive Summary** (2-3 sentences): What's the core message?

2. **Key Insights** (3-5 bullet points): Main takeaways relevant to recruitment/EOR industry

3. **Outstaffer Relevance** (paragraph): How does this content relate to Outstaffer's business model (recruitment-led global hiring + EOR platform serving US staffing firms and Australian B2B companies)?

4. **Content Angle Ideas** (3 suggestions): How could this be adapted into blog posts or thought leadership for Outstaffer?

5. **Action Items** (2-3 points): Specific ways Outstaffer could leverage these insights

Keep analysis concise, practical, and focused on business applications. Avoid fluff.
"""
