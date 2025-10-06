"""Shared data models for intelligence workflows."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class PreScoreResult(BaseModel):
    """Validated Gemini response for Reddit pre-scoring."""

    model_config = ConfigDict(extra="ignore")

    post_id: str
    score: float
    priority: bool
    reason: Optional[str] = None


class RedditAnalysis(BaseModel):
    """Structured Reddit enrichment payload."""

    model_config = ConfigDict(extra="ignore")

    relevance_score: float
    reasoning: str
    identified_pain_point: str
    outstaffer_solution_angle: str


PRESCORE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "post_id": {"type": "string"},
        "score": {"type": "number"},
        "priority": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["post_id", "score", "priority"],
}


REDDIT_ANALYSIS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance_score": {"type": "number"},
        "reasoning": {"type": "string"},
        "identified_pain_point": {"type": "string"},
        "outstaffer_solution_angle": {
            "type": "string",
            "enum": ["Recruitment", "EOR", "AI Screening", "HRIS", "None"],
        },
    },
    "required": [
        "relevance_score",
        "reasoning",
        "identified_pain_point",
        "outstaffer_solution_angle",
    ],
}
