import sys
from pathlib import Path
import types

import pytest

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

google_module = sys.modules.setdefault("google", types.ModuleType("google"))
if not hasattr(google_module, "genai"):
    google_module.genai = types.ModuleType("genai")
sys.modules.setdefault("google.genai", google_module.genai)
if not hasattr(google_module.genai, "types"):
    google_module.genai.types = types.ModuleType("types")
sys.modules.setdefault("google.genai.types", google_module.genai.types)
if not hasattr(google_module.genai, "Client"):
    class _DummyGenaiClient:  # pragma: no cover - simple stub
        def __init__(self, *args, **kwargs):
            pass

    google_module.genai.Client = _DummyGenaiClient

google_cloud_module = sys.modules.setdefault("google.cloud", types.ModuleType("cloud"))
google_module.cloud = google_cloud_module
if not hasattr(google_cloud_module, "firestore"):
    google_cloud_module.firestore = types.ModuleType("firestore")
sys.modules.setdefault("google.cloud.firestore", google_cloud_module.firestore)
if not hasattr(google_cloud_module.firestore, "Client"):
    class _DummyFirestoreClient:  # pragma: no cover - simple stub
        def __init__(self, *args, **kwargs):
            pass

    google_cloud_module.firestore.Client = _DummyFirestoreClient

tavily_module = sys.modules.setdefault("tavily", types.ModuleType("tavily"))
if not hasattr(tavily_module, "TavilyClient"):
    class _DummyTavilyClient:  # pragma: no cover - simple stub
        def __init__(self, *args, **kwargs):
            pass

    tavily_module.TavilyClient = _DummyTavilyClient

from backend.app import create_app  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_generate_queries_includes_warnings(client, monkeypatch):
    monkeypatch.setattr(
        "api.intelligence_stages.load_segment_config",
        lambda segment_name: {"audience": "Test Audience"},
    )
    monkeypatch.setattr(
        "api.intelligence_stages.GeminiClient",
        lambda: object(),
    )

    def fake_generate_curated_queries(**kwargs):
        assert kwargs["segment_name"] == "alpha"
        return ["query one", "query two"], ["a warning"]

    monkeypatch.setattr(
        "api.intelligence_stages.generate_curated_queries",
        fake_generate_curated_queries,
    )

    response = client.post(
        "/api/intelligence/voc-discovery/generate-queries",
        json={
            "segment_name": "alpha",
            "filtered_posts": [{"id": "1"}],
            "trends": [{"query": "topic"}],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["queries"] == ["query one", "query two"]
    assert payload["warnings"] == ["a warning"]
    assert payload["count"] == 2
    assert "duration_ms" in payload


def test_generate_queries_returns_empty_lists(client, monkeypatch):
    monkeypatch.setattr(
        "api.intelligence_stages.load_segment_config",
        lambda segment_name: {},
    )
    monkeypatch.setattr(
        "api.intelligence_stages.GeminiClient",
        lambda: object(),
    )
    monkeypatch.setattr(
        "api.intelligence_stages.generate_curated_queries",
        lambda **kwargs: ([], []),
    )

    response = client.post(
        "/api/intelligence/voc-discovery/generate-queries",
        json={"segment_name": "beta", "filtered_posts": [], "trends": []},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["queries"] == []
    assert payload["warnings"] == []
    assert payload["count"] == 0
    assert "duration_ms" in payload
