"""Gemini API client for content analysis"""
import json
import os
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List


class GeminiClient:
    """Wrapper for Gemini API operations"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini client"""
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def synthesize_content(self, query: str, contents: List[Dict[str, str]]) -> Dict[str, Any]:
        """Uses Gemini to synthesize an article from multiple sources."""
        if not self.api_key:
            return {'success': False, 'error': 'GEMINI_API_KEY not set'}

        # Prepare the source material for the prompt
        source_material = ""
        for i, doc in enumerate(contents):
            source_material += f"--- Source {i+1} ---\n"
            source_material += f"URL: {doc.get('url', 'N/A')}\n"
            source_material += f"Title: {doc.get('title', 'N/A')}\n"
            source_material += f"Content:\n{doc.get('markdown', '')[:2000]}\n\n" # Truncate to manage token size

        prompt = f"""
        You are a professional research analyst and content strategist for Outstaffer, a company that provides recruitment-led global hiring and Employer of Record (EOR) services to Australian companies, with a focus on technology and backoffice roles. Also harnessing teh power of Ai to make the process smoother and faster. 

        **Part 1: Research Article**
        Your first task is to write a comprehensive, well-structured mini-research article on the topic: "{query}".
        Use the following source materials to write your article. You must synthesize the information from these sources into a new, original piece of writing. Do not simply copy and paste.

        Your article should have:
        1.  An engaging title.
        2.  A brief introduction summarizing the topic.
        3.  Several paragraphs that explore the key themes, trends, and data points from the sources.
        4.  A concluding paragraph that summarizes the main takeaways.

        Here is the source material you must use:
        {source_material}

        ---

        **Part 2: Outstaffer Strategic Analysis**
        After writing the article, provide a brief analysis for the Outstaffer team. Answer the following:
        - **Relevance & Opportunity:** How does this topic relate to Outstaffer's business? What opportunities or challenges does it highlight for your clients (US staffing firms, Australian B2B companies)?
        - **Key Talking Point:** What is the single most important insight from this research that the Outstaffer sales or marketing team should use?

        ---

        **Part 3: LinkedIn Content Idea**
        Finally, create a ready-to-use LinkedIn post idea based on the research. Provide the following:
        - **LinkedIn Angle:** A short, compelling angle for the post.
        - **Post Text:** A draft of the LinkedIn post (2-3 paragraphs).
        - **Hashtags:** A list of 3-5 relevant hashtags.

        Structure your entire response as a single JSON object with two keys: "article" and "outstaffer_analysis". The "outstaffer_analysis" key should contain the strategic analysis and the LinkedIn idea.
        
        Example JSON output format:
        {{
          "article": "Your full research article text here...",
          "outstaffer_analysis": "### Strategic Analysis\\n**Relevance & Opportunity:** ...\\n**Key Talking Point:** ...\\n\\n### LinkedIn Post Idea\\n**LinkedIn Angle:** ...\\n**Post Text:** ...\\n**Hashtags:** #hashtag1 #hashtag2"
        }}
        """

        # This reuses the same API call structure as analyze_content
        # In a real app, you might refactor this into a shared helper method
        url = f"{self.base_url}/gemini-1.5-flash-latest:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': self.api_key}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            # Clean the response and parse the JSON
            raw_text = result['candidates'][0]['content']['parts'][0]['text']
            # Find the JSON part of the response
            json_text = raw_text[raw_text.find('{'):raw_text.rfind('}')+1]

            parsed_result = json.loads(json_text)

            if parsed_result.get("article"):
                return {
                    'success': True,
                    'article': parsed_result.get("article"),
                    'outstaffer_analysis': parsed_result.get("outstaffer_analysis")
                }
            else:
                return dict(success=False, error='No article was generated by the AI.')
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Gemini API error: {str(e)}',
            }


    def analyze_content(self, content: str, prompt: str = None, model: str = "gemini-2.0-flash") -> Dict[str, Any]:
        """Analyze content with Gemini"""
        if not self.api_key:
            return {
                'success': False,
                'error': 'GEMINI_API_KEY not set',
                'analyzed_at': datetime.now().strftime("%Y%m%d_%H%M%S")
            }
        
        # Default analysis prompt tailored for Outstaffer
        if prompt is None:
            prompt = f"""
            Analyze this scraped web content and provide:

            1. **Executive Summary** (2-3 sentences): What's the core message?
            
            2. **Key Insights** (3-5 bullet points): Main takeaways relevant to recruitment/EOR industry
            
            3. **Outstaffer Relevance** (paragraph): How does this content relate to Outstaffer's business model (recruitment-led global hiring + EOR platform serving US staffing firms and Australian B2B companies)?
            
            4. **Content Angle Ideas** (3 suggestions): How could this be adapted into blog posts or thought leadership for Outstaffer?
            
            5. **Action Items** (2-3 points): Specific ways Outstaffer could leverage these insights
            
            Keep analysis concise, practical, and focused on business applications. Avoid fluff.
            
            CONTENT TO ANALYZE:
            {content}
            """
        
        url = f"{self.base_url}/{model}:generateContent"
        
        headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': self.api_key
        }
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract generated text
            generated_text = None
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    generated_text = candidate['content']['parts'][0]['text']
                elif 'parts' in candidate:
                    generated_text = candidate['parts'][0]['text']
            
            if generated_text:
                return {
                    'success': True,
                    'analysis': generated_text,
                    'raw_response': result,
                    'analyzed_at': datetime.now().strftime("%Y%m%d_%H%M%S"),
                    'model': model
                }
            else:
                return {
                    'success': False,
                    'error': 'No content generated by Gemini',
                    'raw_response': result,
                    'analyzed_at': datetime.now().strftime("%Y%m%d_%H%M%S")
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Gemini API error: {str(e)}',
                'analyzed_at': datetime.now().strftime("%Y%m%d_%H%M%S")
            }
