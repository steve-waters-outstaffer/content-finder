"""Google Trends helpers for the VOC discovery workflow."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pytrends.request import TrendReq

logger = logging.getLogger(__name__)


def _dataframe_to_records(dataframe: Any, *, rename_columns: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    if dataframe is None or getattr(dataframe, "empty", True):
        return []

    working_df = dataframe
    if rename_columns:
        working_df = working_df.rename(columns=rename_columns)

    records: List[Dict[str, Any]] = []
    for record in working_df.reset_index().to_dict(orient="records"):
        serialised: Dict[str, Any] = {}
        for key, value in record.items():
            if hasattr(value, "isoformat"):
                serialised[key] = value.isoformat()
            else:
                serialised[key] = value
        records.append(serialised)
    return records


def _extract_related_queries(related_queries: Dict[str, Any], keyword: str) -> Dict[str, List[Dict[str, Any]]]:
    keyword_data = related_queries.get(keyword, {}) if related_queries else {}
    return {
        "top": _dataframe_to_records(keyword_data.get("top")),
        "rising": _dataframe_to_records(keyword_data.get("rising")),
    }


def _extract_related_topics(related_topics: Dict[str, Any], keyword: str) -> Dict[str, List[Dict[str, Any]]]:
    keyword_data = related_topics.get(keyword, {}) if related_topics else {}
    return {
        "top": _dataframe_to_records(keyword_data.get("top")),
        "rising": _dataframe_to_records(keyword_data.get("rising")),
    }


def fetch_google_trends(segment_config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    trends_config = segment_config.get("google_trends", {})
    primary_keywords: Sequence[str] = trends_config.get("primary_keywords") or segment_config.get("search_keywords", [])
    comparison_keyword: Optional[str] = trends_config.get("comparison_keyword")
    timeframe: str = trends_config.get("timeframe", "today 12-m")
    geo: str = trends_config.get("geo", "")

    if not primary_keywords:
        return [], ["No Google Trends keywords configured for this segment."]

    pytrends = TrendReq(hl="en-US", tz=360)
    curated_trends: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for keyword in primary_keywords:
        query_terms = [keyword]
        if comparison_keyword and comparison_keyword.lower() != keyword.lower():
            query_terms.append(comparison_keyword)

        try:
            pytrends.build_payload(query_terms, timeframe=timeframe, geo=geo)
            interest_over_time = pytrends.interest_over_time()
            related_queries = pytrends.related_queries()
            related_topics = pytrends.related_topics()
        except Exception as exc:  # noqa: BLE001
            warning = f"Google Trends lookup failed for '{keyword}': {exc}"
            logger.warning(warning)
            warnings.append(warning)
            continue

        curated_trends.append(
            {
                "query": keyword,
                "comparison_keyword": comparison_keyword,
                "interest_over_time": _dataframe_to_records(
                    interest_over_time,
                    rename_columns={keyword: "primary_interest"},
                ),
                "related_queries": _extract_related_queries(related_queries, keyword),
                "related_topics": _extract_related_topics(related_topics, keyword),
            }
        )

    return curated_trends, warnings


__all__ = ["fetch_google_trends"]

