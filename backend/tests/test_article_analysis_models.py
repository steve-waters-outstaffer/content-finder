from __future__ import annotations

import json
import pathlib
import sys

import pytest
from pydantic import ValidationError

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from intelligence.models import ArticleAnalysis, MultiArticleAnalysis  # noqa: E402


def test_article_analysis_valid_payload() -> None:
    payload = {
        "overview": "This article summarises key hiring trends in APAC.",
        "key_insights": [
            "SMBs expect remote-first policies to continue.",
            "Compliance automation is accelerating adoption.",
            "Hybrid models require better onboarding support.",
        ],
        "outstaffer_opportunity": "Outstaffer can position flexible EOR packages to solve compliance gaps.",
    }

    model = ArticleAnalysis.model_validate_json(json.dumps(payload))

    assert model.overview == payload["overview"]
    assert model.key_insights == payload["key_insights"]
    assert model.outstaffer_opportunity == payload["outstaffer_opportunity"]


def test_article_analysis_rejects_extra_fields() -> None:
    payload = {
        "overview": "Summary",
        "key_insights": ["Insight"],
        "outstaffer_opportunity": "Opportunity",
        "extra": "not allowed",
    }

    with pytest.raises(ValidationError):
        ArticleAnalysis.model_validate_json(json.dumps(payload))


def test_multi_article_analysis_defaults_to_empty_themes() -> None:
    payload = {
        "overview": "Combined overview across sources.",
        "key_insights": [
            "Automation investment is rising.",
            "Leaders want consistent onboarding.",
            "Budget is shifting to remote enablement.",
            "APAC needs more compliance partners.",
            "Retention hinges on wellbeing benefits.",
        ],
        "outstaffer_opportunity": "Bundle advisory plus EOR rollouts for rapid expansions.",
    }

    model = MultiArticleAnalysis.model_validate_json(json.dumps(payload))

    assert model.cross_article_themes == []


def test_multi_article_analysis_invalid_theme_type() -> None:
    payload = {
        "overview": "Summary",
        "key_insights": ["Insight 1"],
        "outstaffer_opportunity": "Opportunity",
        "cross_article_themes": ["Theme A", 42],
    }

    with pytest.raises(ValidationError):
        MultiArticleAnalysis.model_validate_json(json.dumps(payload))
