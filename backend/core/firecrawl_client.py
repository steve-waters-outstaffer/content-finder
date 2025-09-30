"""Typed Firecrawl client wrappers for synchronous and async workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from firecrawl import AsyncFirecrawl, Firecrawl


class FirecrawlClientError(RuntimeError):
    """Raised when Firecrawl fails to return a usable response."""


@dataclass(slots=True)
class WebDocument:
    """Normalised representation of web content returned by Firecrawl."""

    url: str
    title: str = ""
    description: str = ""
    markdown: str = ""
    html: str = ""

    @classmethod
    def from_payload(cls, payload: Any) -> "WebDocument":
        if hasattr(payload, "model_dump"):
            raw = payload.model_dump()
        elif isinstance(payload, dict):
            raw = payload
        else:
            raw = getattr(payload, "__dict__", {})

        return cls(
            url=str(raw.get("url") or ""),
            title=str(raw.get("title") or ""),
            description=str(raw.get("description") or ""),
            markdown=str(raw.get("markdown") or ""),
            html=str(raw.get("html") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "markdown": self.markdown,
            "html": self.html,
        }


@dataclass(slots=True)
class ScrapeResult:
    """Structured result for a scraped page."""

    url: str
    success: bool
    markdown: str = ""
    html: str = ""
    title: str = ""
    description: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "success": self.success,
            "markdown": self.markdown,
            "html": self.html,
            "title": self.title,
            "description": self.description,
            "error": self.error,
            "scraped_at": datetime.utcnow().isoformat(),
        }


class FirecrawlClient:
    """Synchronous Firecrawl client used by batch pipelines."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise FirecrawlClientError("FIRECRAWL_API_KEY not configured.")
        self._client = Firecrawl(api_key=self.api_key)

    def search(self, query: str, limit: int = 15) -> Dict[str, Any]:
        try:
            response = self._client.search(query=query, limit=limit)
        except Exception as exc:  # noqa: BLE001
            raise FirecrawlClientError(f"Firecrawl search failed: {exc}") from exc

        items: Iterable[Any] = getattr(response, "web", [])
        results = [WebDocument.from_payload(item).to_dict() for item in items]
        return {
            "query": query,
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def scrape_urls(self, urls: Iterable[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for url in urls:
            try:
                doc = self._client.scrape(url, formats=["markdown", "html"])
                document = WebDocument.from_payload(doc)
                results.append(
                    ScrapeResult(
                        url=url,
                        success=True,
                        markdown=document.markdown,
                        html=document.html,
                        title=document.title,
                        description=document.description,
                    ).to_dict()
                )
            except Exception as exc:  # noqa: BLE001 - continue processing remaining URLs
                results.append(
                    ScrapeResult(
                        url=url,
                        success=False,
                        error=str(exc),
                    ).to_dict()
                )
        return results

    def extract_structured(self, urls: Iterable[str], *, prompt: Optional[str] = None, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        extraction_prompt = prompt or "Extract key insights about hiring trends, challenges, and strategies for SMBs"
        extraction_schema = schema or {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "key_insights": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "summary", "key_insights"],
        }

        try:
            response = self._client.extract(urls=list(urls), prompt=extraction_prompt, schema=extraction_schema)
        except Exception as exc:  # noqa: BLE001
            raise FirecrawlClientError(f"Firecrawl extract failed: {exc}") from exc

        payload = response.model_dump() if hasattr(response, "model_dump") else response
        return {
            "success": True,
            "data": payload,
            "extracted_at": datetime.utcnow().isoformat(),
        }


class AsyncFirecrawlClient:
    """Async Firecrawl client tailored for the research agent."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise FirecrawlClientError("FIRECRAWL_API_KEY not configured.")
        self._client = AsyncFirecrawl(api_key=self.api_key)

    async def scrape(
        self,
        url: str,
        *,
        only_main_content: bool = True,
    ) -> ScrapeResult:
        try:
            response = await self._client.scrape(
                url=url,
                params={"pageOptions": {"onlyMainContent": only_main_content}},
            )
        except Exception as exc:  # noqa: BLE001
            return ScrapeResult(url=url, success=False, error=str(exc))

        document = WebDocument.from_payload(response)
        return ScrapeResult(
            url=url,
            success=True,
            markdown=document.markdown,
            html=document.html,
            title=document.title,
            description=document.description,
        )


__all__ = [
    "FirecrawlClient",
    "AsyncFirecrawlClient",
    "FirecrawlClientError",
    "ScrapeResult",
    "WebDocument",
]

