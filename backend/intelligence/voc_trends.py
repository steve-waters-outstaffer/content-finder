"""Google Trends helpers for the VOC discovery workflow."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pytrends.request import TrendReq

logger = logging.getLogger(__name__)


def _dataframe_to_records(dataframe: Any, *, rename_columns: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    if dataframe is None or getattr(dataframe, "empty", True):
        logger.debug("DataFrame is None or empty, returning empty list")
        return []

    working_df = dataframe
    if rename_columns:
        working_df = working_df.rename(columns=rename_columns)

    # Fix pandas FutureWarning
    working_df = working_df.infer_objects(copy=False).fillna(False)

    records: List[Dict[str, Any]] = []
    for record in working_df.reset_index().to_dict(orient="records"):
        serialised: Dict[str, Any] = {}
        for key, value in record.items():
            if hasattr(value, "isoformat"):
                serialised[key] = value.isoformat()
            else:
                serialised[key] = value
        records.append(serialised)
    
    logger.debug(f"Converted DataFrame to {len(records)} records")
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

    logger.info(
        "Starting Google Trends fetch",
        extra={
            "keyword_count": len(primary_keywords),
            "keywords": list(primary_keywords),
            "comparison_keyword": comparison_keyword,
            "timeframe": timeframe,
            "geo": geo,
        }
    )

    if not primary_keywords:
        logger.warning("No Google Trends keywords configured")
        return [], ["No Google Trends keywords configured for this segment."]

    pytrends = TrendReq(hl="en-US", tz=360)
    curated_trends: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for idx, keyword in enumerate(primary_keywords, 1):
        keyword_start_time = time.perf_counter()
        
        logger.info(
            f"Processing keyword {idx}/{len(primary_keywords)}: '{keyword}'",
            extra={"keyword": keyword, "index": idx}
        )
        
        query_terms = [keyword]
        if comparison_keyword and comparison_keyword.lower() != keyword.lower():
            query_terms.append(comparison_keyword)

        # Retry logic with exponential backoff
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt + 1}/{max_retries} for '{keyword}'",
                        extra={"keyword": keyword, "attempt": attempt + 1, "delay_seconds": retry_delay}
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                
                logger.debug(f"Building payload for: {query_terms}")
                pytrends.build_payload(query_terms, timeframe=timeframe, geo=geo)
                
                logger.debug(f"Fetching interest over time for '{keyword}'")
                interest_over_time = pytrends.interest_over_time()
                
                logger.debug(f"Fetching related queries for '{keyword}'")
                related_queries = pytrends.related_queries()
                
                logger.debug(f"Fetching related topics for '{keyword}'")
                related_topics = pytrends.related_topics()
                
                # Validate that we got actual data
                interest_records = _dataframe_to_records(
                    interest_over_time,
                    rename_columns={keyword: "primary_interest"},
                )
                
                related_queries_data = _extract_related_queries(related_queries, keyword)
                related_topics_data = _extract_related_topics(related_topics, keyword)
                
                # Check if we got meaningful data
                has_interest_data = len(interest_records) > 0
                has_related_queries = len(related_queries_data.get("top", [])) > 0 or len(related_queries_data.get("rising", [])) > 0
                has_related_topics = len(related_topics_data.get("top", [])) > 0 or len(related_topics_data.get("rising", [])) > 0
                
                keyword_duration = round((time.perf_counter() - keyword_start_time) * 1000, 2)
                
                logger.info(
                    f"Successfully fetched trends for '{keyword}'",
                    extra={
                        "keyword": keyword,
                        "duration_ms": keyword_duration,
                        "interest_data_points": len(interest_records),
                        "related_queries_top": len(related_queries_data.get("top", [])),
                        "related_queries_rising": len(related_queries_data.get("rising", [])),
                        "related_topics_top": len(related_topics_data.get("top", [])),
                        "related_topics_rising": len(related_topics_data.get("rising", [])),
                        "has_interest_data": has_interest_data,
                        "has_related_queries": has_related_queries,
                        "has_related_topics": has_related_topics,
                    }
                )
                
                # Warn if we got no data at all
                if not has_interest_data and not has_related_queries and not has_related_topics:
                    warning = f"Google Trends returned no data for '{keyword}' - possible rate limit or no search volume"
                    logger.warning(warning, extra={"keyword": keyword})
                    warnings.append(warning)
                
                trend_data = {
                    "query": keyword,
                    "comparison_keyword": comparison_keyword,
                    "interest_over_time": interest_records,
                    "related_queries": related_queries_data,
                    "related_topics": related_topics_data,
                }
                
                curated_trends.append(trend_data)
                
                # Successfully processed, break retry loop
                break
                
            except Exception as exc:
                keyword_duration = round((time.perf_counter() - keyword_start_time) * 1000, 2)
                
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Google Trends lookup failed for '{keyword}', will retry",
                        extra={
                            "keyword": keyword,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                            "duration_ms": keyword_duration,
                        }
                    )
                else:
                    # Final attempt failed
                    warning = f"Google Trends lookup failed for '{keyword}' after {max_retries} attempts: {exc}"
                    logger.error(
                        warning,
                        extra={
                            "keyword": keyword,
                            "attempts": max_retries,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                            "duration_ms": keyword_duration,
                        },
                        exc_info=True,
                    )
                    warnings.append(warning)
    
    # Final validation
    total_trends = len(curated_trends)
    logger.info(
        "Google Trends fetch completed",
        extra={
            "total_keywords": len(primary_keywords),
            "successful_trends": total_trends,
            "warnings_count": len(warnings),
        }
    )
    
    # Raise error if we got no data at all
    if total_trends == 0 and primary_keywords:
        error_msg = "Google Trends returned no data for any keywords - likely rate limited or service issue"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return curated_trends, warnings


__all__ = ["fetch_google_trends"]

