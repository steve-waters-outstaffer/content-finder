import pathlib
import sys
import time
from typing import Any, Dict

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.gemini_client import GeminiClientError
from intelligence import voc_synthesis
from intelligence.models import PreScoreResult


class DummyResponse:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.raw_text = "{}"


class DummyGemini:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload
        self.default_model = "test-model"

    def generate_json_response(self, *args: Any, **kwargs: Any) -> DummyResponse:
        return DummyResponse(self._payload)


def test_pre_score_post_success() -> None:
    post = {"id": "abc123", "title": "Hiring help", "content_snippet": "We need EOR"}
    gemini = DummyGemini({
        "post_id": "abc123",
        "score": 0.85,
        "priority": True,
        "reason": "Direct hiring challenge",
    })

    result = voc_synthesis.pre_score_post(
        post,
        "Segment",
        gemini_client=gemini,
        segment_config={"audience": "HR", "priorities": ["Global hiring"]},
    )

    assert isinstance(result, PreScoreResult)
    assert result.post_id == "abc123"
    assert result.score == pytest.approx(0.85)
    assert result.priority is True
    assert result.reason == "Direct hiring challenge"


def test_pre_score_post_invalid_payload_raises() -> None:
    post = {"id": "abc123", "title": "Hiring help", "content_snippet": "We need EOR"}
    gemini = DummyGemini({"post_id": "abc123", "priority": True})

    with pytest.raises(GeminiClientError):
        voc_synthesis.pre_score_post(
            post,
            "Segment",
            gemini_client=gemini,
        )


def test_pre_score_posts_collects_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = [{"id": "1"}, {"id": "2"}]

    def fake_pre_score_post(post: Dict[str, Any], *_args: Any, **_kwargs: Any) -> PreScoreResult:
        if post["id"] == "1":
            return PreScoreResult(post_id="1", score=0.6, priority=True, reason="Good fit")
        raise GeminiClientError("boom")

    monkeypatch.setattr(voc_synthesis, "pre_score_post", fake_pre_score_post)

    scored, warnings = voc_synthesis.pre_score_posts(
        posts,
        "Segment",
        gemini_client=DummyGemini({}),
    )

    assert len(scored) == 1
    assert scored[0]["prescore"]["relevance_score"] == pytest.approx(0.6)
    assert warnings and "boom" in warnings[0]


def test_pre_score_posts_preserves_input_order(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = [{"id": "1"}, {"id": "2"}]

    def fake_pre_score_post(post: Dict[str, Any], *_args: Any, **_kwargs: Any) -> PreScoreResult:
        if post["id"] == "1":
            time.sleep(0.05)
        return PreScoreResult(post_id=post["id"], score=float(post["id"]), priority=False, reason="")

    monkeypatch.setattr(voc_synthesis, "pre_score_post", fake_pre_score_post)

    scored, warnings = voc_synthesis.pre_score_posts(
        posts,
        "Segment",
        gemini_client=DummyGemini({}),
    )

    assert not warnings
    assert [post["id"] for post in scored] == ["1", "2"]
