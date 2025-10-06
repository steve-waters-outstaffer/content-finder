"""Pydantic models shared across intelligence modules."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class SearchQuery(BaseModel):
    """A precise, actionable web search query tailored to the research mission."""

    query: str = Field(
        ...,
        description="A precise, actionable web search query tailored to the research mission.",
    )


class QueryPlan(BaseModel):
    """Structured set of search queries returned by the planner."""

    queries: List[SearchQuery] = Field(
        ...,
        description="A list of 3-5 high-quality, targeted search queries.",
    )


class TalkingPoint(BaseModel):
    """Insight derived from the research corpus."""

    point: str = Field(
        ...,
        description="A key insight or talking point derived from the content.",
    )
    supporting_urls: List[str] = Field(
        default_factory=list,
        description="URLs of sources that support this point.",
    )


class CampaignIdea(BaseModel):
    """Creative activation derived from the research."""

    idea: str = Field(
        ...,
        description="A creative campaign idea or content angle.",
    )
    target_channels: List[str] = Field(
        default_factory=list,
        description="Recommended channels for this campaign (e.g., Blog, LinkedIn).",
    )


class ContentTheme(BaseModel):
    """High-level theme synthesized from the research corpus."""

    theme_title: str = Field(
        ...,
        description="A high-level theme or topic discovered in the research.",
    )
    summary: str = Field(
        ...,
        description="A brief summary of the theme, explaining its relevance to the target audience.",
    )
    talking_points: List[TalkingPoint]
    campaign_ideas: List[CampaignIdea]


class SynthesisResult(BaseModel):
    """Structured synthesis output returned by Gemini."""

    content_themes: List[ContentTheme]
