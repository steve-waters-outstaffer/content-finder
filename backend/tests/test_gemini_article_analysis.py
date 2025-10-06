from __future__ import annotations

import pathlib
import sys

import pytest
from google.genai import types

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.gemini_client import GeminiClient, GeminiClientError  # noqa: E402
from intelligence.models import ArticleAnalysis  # noqa: E402


def test_analyze_article_structured_invokes_structured_generation(monkeypatch, tmp_path):
    prompt_dir = tmp_path
    prompt_dir.mkdir(exist_ok=True)

    client = GeminiClient(api_key="test-key", prompt_dir=prompt_dir)

    def fake_generate_structured_response(self, template_name, context, **kwargs):  # noqa: ANN001
        assert template_name == "article_analysis_prompt.txt"
        assert "content" in context
        return ArticleAnalysis(
            overview="Overview text",
            key_insights=["Insight A", "Insight B", "Insight C"],
            outstaffer_opportunity="Opportunity text",
        )

    monkeypatch.setattr(GeminiClient, "generate_structured_response", fake_generate_structured_response)

    result = client.analyze_article_structured("Example content")

    assert isinstance(result, ArticleAnalysis)
    assert len(result.key_insights) == 3


class _DummyModels:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def generate_content(self, **kwargs):  # noqa: ANN001
        class _Response:
            def __init__(self, text: str) -> None:
                self.text = text

        return _Response(self._response_text)


class _DummyClient:
    def __init__(self, response_text: str) -> None:
        self.models = _DummyModels(response_text)


def _patch_gemini_dependencies(monkeypatch, response_text: str):
    monkeypatch.setattr(GeminiClient, "_get_client", lambda self: _DummyClient(response_text))

    class _FakeSchema:  # noqa: D401 - simple stand-in schema object
        @staticmethod
        def from_dict(schema):  # noqa: ANN001
            return schema

    monkeypatch.setattr(types, "Schema", _FakeSchema)


def test_generate_structured_response_raises_on_non_json(monkeypatch, tmp_path):
    prompt_path = tmp_path / "article_analysis_prompt.txt"
    prompt_path.write_text("{content}", encoding="utf-8")

    client = GeminiClient(api_key="test-key", prompt_dir=tmp_path)

    _patch_gemini_dependencies(monkeypatch, "not-json")

    with pytest.raises(GeminiClientError) as excinfo:
        client.generate_structured_response(
            "article_analysis_prompt.txt",
            {"content": "data"},
            response_model=ArticleAnalysis,
        )

    assert "non-JSON" in str(excinfo.value)


def test_generate_structured_response_raises_on_validation_error(monkeypatch, tmp_path):
    prompt_path = tmp_path / "article_analysis_prompt.txt"
    prompt_path.write_text("{content}", encoding="utf-8")

    client = GeminiClient(api_key="test-key", prompt_dir=tmp_path)

    invalid_payload = "{\"overview\": \"Only overview\"}"
    _patch_gemini_dependencies(monkeypatch, invalid_payload)

    with pytest.raises(GeminiClientError) as excinfo:
        client.generate_structured_response(
            "article_analysis_prompt.txt",
            {"content": "data"},
            response_model=ArticleAnalysis,
        )

    assert "validation" in str(excinfo.value).lower()
