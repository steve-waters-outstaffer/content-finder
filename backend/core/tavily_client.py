"""Typed Tavily client wrapper used by the intelligence stack."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

from tavily import TavilyClient as TavilySDK


class TavilyClientError(RuntimeError):
    """Raised when Tavily returns an invalid response."""


@dataclass(slots=True)
class TavilyResult:
    """Structured Tavily search result."""

    title: str
    url: str
    snippet: str
    score: float

    @classmethod
    def from_payload(cls, payload: dict) -> "TavilyResult":
        return cls(
            title=str(payload.get("title") or ""),
            url=str(payload.get("url") or ""),
            snippet=str(payload.get("content") or payload.get("snippet") or ""),
            score=float(payload.get("score") or payload.get("relevance_score") or 0.0),
        )

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "score": self.score,
        }


class TavilyClient:
    """Lightweight Tavily API wrapper with consistent error handling."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        if not self.api_key:
            raise TavilyClientError("TAVILY_API_KEY not configured.")
        self._client = TavilySDK(api_key=self.api_key)

    def search(
        self,
        query: str,
        *,
        search_depth: str = "advanced",
        max_results: int = 7,
        include_domains: Optional[Iterable[str]] = None,
        exclude_domains: Optional[Iterable[str]] = None,
    ) -> List[TavilyResult]:
        try:
            response = self._client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_domains=list(include_domains or []),
                exclude_domains=list(exclude_domains or []),
            )
        except Exception as exc:  # noqa: BLE001 - network/SDK errors should surface clearly
            raise TavilyClientError(f"Tavily API error: {exc}") from exc

        raw_results = response.get("results") if isinstance(response, dict) else None
        if not raw_results:
            return []

        parsed: List[TavilyResult] = []
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            parsed.append(TavilyResult.from_payload(raw))
        return parsed


# Backwards compatible alias used by older modules
TavilyApiClient = TavilyClient


__all__ = ["TavilyClient", "TavilyApiClient", "TavilyResult", "TavilyClientError"]

