import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.intelligence.voc_synthesis import PostScore, batch_prescore_posts


class DummyGeminiClient:
    def _get_client(self):
        return object()


def test_batch_prescore_posts_handles_duplicate_and_missing_ids(monkeypatch):
    posts = [
        {"id": "dup", "title": "First duplicate", "content": "A"},
        {"id": "dup", "title": "Second duplicate", "content": "B"},
        {"title": "Missing id", "content": "C"},
    ]

    fake_results = {
        0: (PostScore(post_index=0, relevance_score=8.5, quick_reason="Relevant"), None),
        1: (PostScore(post_index=1, relevance_score=7.0, quick_reason="Still relevant"), None),
        2: (PostScore(post_index=2, relevance_score=6.0, quick_reason="Good context"), None),
    }

    async def fake_score_single_post_async(*args, **kwargs):
        post_index = args[2]
        return fake_results[post_index]

    monkeypatch.setattr(
        "backend.intelligence.voc_synthesis.score_single_post_async",
        fake_score_single_post_async,
    )
    monkeypatch.setattr(
        "backend.intelligence.voc_synthesis.instructor.from_gemini",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "backend.intelligence.voc_synthesis.instructor.Mode",
        SimpleNamespace(GEMINI_JSON="json"),
    )

    async def run_test():
        gemini_client = DummyGeminiClient()

        enriched_posts, warnings = await batch_prescore_posts(
            posts, {"audience": "Test", "priorities": []}, "segment", gemini_client
        )

        assert warnings == []
        assert len(enriched_posts) == len(posts)
        titles = [post["title"] for post in enriched_posts]
        assert titles == ["First duplicate", "Second duplicate", "Missing id"]
        for idx, post in enumerate(enriched_posts):
            assert "prescore" in post
            assert post["prescore"]["relevance_score"] == fake_results[idx][0].relevance_score
            assert post["prescore"]["quick_reason"] == fake_results[idx][0].quick_reason

    asyncio.run(run_test())


def test_batch_prescore_posts_falls_back_to_loop_index(monkeypatch):
    posts = [
        {"id": "alpha", "title": "Alpha", "content": "Content"},
    ]

    async def fake_score_single_post_async(*args, **kwargs):
        # Return an out-of-range index to trigger the fallback logic
        return PostScore(post_index=999, relevance_score=5.0, quick_reason="Oops"), None

    monkeypatch.setattr(
        "backend.intelligence.voc_synthesis.score_single_post_async",
        fake_score_single_post_async,
    )
    monkeypatch.setattr(
        "backend.intelligence.voc_synthesis.instructor.from_gemini",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "backend.intelligence.voc_synthesis.instructor.Mode",
        SimpleNamespace(GEMINI_JSON="json"),
    )

    async def run_test():
        gemini_client = DummyGeminiClient()

        enriched_posts, warnings = await batch_prescore_posts(
            posts, {"audience": "Test", "priorities": []}, "segment", gemini_client
        )

        assert len(enriched_posts) == 1
        assert enriched_posts[0]["title"] == "Alpha"
        assert enriched_posts[0]["prescore"]["quick_reason"] == "Oops"
        assert any("falling back to loop index" in warning for warning in warnings)

    asyncio.run(run_test())
