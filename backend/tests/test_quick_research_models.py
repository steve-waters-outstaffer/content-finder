from __future__ import annotations

import json
import pathlib
import sys

import pytest
from pydantic import ValidationError

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PROJECT_ROOT), str(PROJECT_ROOT / "backend")]

from core.pipeline import ContentPipeline
from models.schemas import ArticleAnalysis, MultiArticleAnalysis


def _validate_schema(model, payload, extra_key) -> None:
    model.model_validate_json(json.dumps(payload))
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps({**payload, extra_key: True}))


def test_article_analysis_schema_contract() -> None:
    _validate_schema(
        ArticleAnalysis,
        {"overview": "Article overview.", "key_insights": ["Insight A", "Insight B", "Insight C"], "outstaffer_opportunity": "Opportunity note."},
        "unexpected",
    )


def test_multi_article_analysis_schema_contract() -> None:
    _validate_schema(
        MultiArticleAnalysis,
        {"overview": "Multi-source overview.", "key_insights": ["Theme A", "Theme B", "Theme C", "Theme D", "Theme E"], "outstaffer_opportunity": "Multi opportunity.", "cross_article_themes": ["Pattern 1", "Pattern 2", "Pattern 3"]},
        "extra_field",
    )


class DummyGemini:
    def __init__(self, article_payload: dict, multi_payload: dict) -> None:
        self.article = ArticleAnalysis.model_validate(article_payload)
        self.multi = MultiArticleAnalysis.model_validate(multi_payload)

    def analyze_article_structured(self, *_args, **_kwargs) -> ArticleAnalysis: return self.article  # noqa: D401

    def synthesize_multi_article_analysis(self, *_args, **_kwargs) -> MultiArticleAnalysis: return self.multi


def _pipeline_with(dummy: DummyGemini) -> ContentPipeline:
    pipeline = ContentPipeline.__new__(ContentPipeline)  # type: ignore[call-arg]
    pipeline.gemini = dummy  # type: ignore[attr-defined]
    return pipeline


def test_pipeline_returns_structured_dicts() -> None:
    article_payload = {"overview": "", "key_insights": [], "outstaffer_opportunity": ""}
    multi_payload = {"overview": "Cross-source perspective.", "key_insights": ["Insight one", "Insight two"], "outstaffer_opportunity": "Clear opportunity.", "cross_article_themes": ["Theme"]}
    dummy = DummyGemini(article_payload, multi_payload)
    pipeline = _pipeline_with(dummy)
    assert pipeline.analyze_content("partial content") == article_payload
    result = pipeline.synthesize_article("remote hiring", [{"url": "https://example.com", "title": "", "markdown": ""}])
    assert result == multi_payload
