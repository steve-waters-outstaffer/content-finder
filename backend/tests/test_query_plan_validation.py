"""Unit tests for QueryPlan validation and JSON handling."""

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

from intelligence.models import QueryPlan


def test_query_plan_valid_payload() -> None:
    payload = {
        "queries": [
            {
                "query": "Outstaffer global hiring strategy 2025 trends",
                "source": "web",
                "qdf": 4,
                "rationale": "Ensures we capture the latest hiring narratives.",
            }
        ],
        "notes": "Focus on high-authority reports first.",
    }

    plan = QueryPlan.model_validate_json(json.dumps(payload))

    assert len(plan.queries) == 1
    assert plan.queries[0].query == payload["queries"][0]["query"]
    assert plan.queries[0].source.value == payload["queries"][0]["source"]
    assert plan.notes == payload["notes"]


def test_query_plan_missing_required_field() -> None:
    payload = {
        "queries": [
            {
                "query": "Outstaffer internal onboarding automation",
                "qdf": 2,
            }
        ]
    }

    with pytest.raises(ValidationError):
        QueryPlan.model_validate_json(json.dumps(payload))


def test_query_plan_invalid_source_enum() -> None:
    payload = {
        "queries": [
            {
                "query": "Remote workforce compliance updates",
                "source": "news",
                "qdf": 1,
            }
        ]
    }

    with pytest.raises(ValidationError):
        QueryPlan.model_validate_json(json.dumps(payload))
