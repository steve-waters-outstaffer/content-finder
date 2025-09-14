"""Firecrawl client wrapper for search, scraping, and extraction"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from firecrawl import Firecrawl


class FirecrawlClient:
    """Wrapper for Firecrawl operations"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Firecrawl client"""
        self.client = Firecrawl(api_key=api_key)
    
    def search(self, query: str, limit: int = 15) -> Dict[str, Any]:
        """Search web for content"""
        result = self.client.search(query=query, limit=limit)
        
        # Convert Pydantic models to dicts for JSON serialization
        results_list = []
        if hasattr(result, 'web') and result.web:
            for item in result.web:
                if hasattr(item, 'model_dump'):
                    results_list.append(item.model_dump())
                elif hasattr(item, '__dict__'):
                    results_list.append(item.__dict__)
                else:
                    # Fallback for simple objects
                    results_list.append({
                        'url': getattr(item, 'url', ''),
                        'title': getattr(item, 'title', ''),
                        'description': getattr(item, 'description', ''),
                    })
        
        return {
            'query': query,
            'results': results_list,
            'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S")
        }
    
    def scrape_urls(self, urls: List[str], formats: List[str] = None) -> List[Dict[str, Any]]:
        """Scrape multiple URLs"""
        if formats is None:
            formats = ["markdown", "html"]
        
        results = []
        for url in urls:
            try:
                doc = self.client.scrape(url, formats=formats)
                
                result = {
                    'url': url,
                    'scraped_at': datetime.now().strftime("%Y%m%d_%H%M%S"),
                    'success': True
                }
                
                if hasattr(doc, 'markdown') and doc.markdown:
                    result['markdown'] = doc.markdown
                if hasattr(doc, 'html') and doc.html:
                    result['html'] = doc.html
                if hasattr(doc, 'title'):
                    result['title'] = doc.title
                if hasattr(doc, 'description'):
                    result['description'] = doc.description
                
                results.append(result)
                
            except Exception as e:
                results.append({
                    'url': url,
                    'scraped_at': datetime.now().strftime("%Y%m%d_%H%M%S"),
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def extract_structured(self, urls: List[str], prompt: str = None, schema: Dict = None) -> Dict[str, Any]:
        """Extract structured data from URLs"""
        if prompt is None:
            prompt = "Extract key insights about hiring trends, challenges, and strategies for SMBs"
        
        if schema is None:
            schema = {
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
                    "relevance_to_eor": {"type": "string", "description": "How this content relates to EOR/global hiring services"}
                },
                "required": ["title", "summary", "key_insights"]
            }
        
        try:
            result = self.client.extract(urls=urls, prompt=prompt, schema=schema)
            return {
                'success': True,
                'data': result.model_dump() if hasattr(result, 'model_dump') else result,
                'extracted_at': datetime.now().strftime("%Y%m%d_%H%M%S")
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extracted_at': datetime.now().strftime("%Y%m%d_%H%M%S")
            }
