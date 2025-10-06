"""High-level Gemini client used across the intelligence pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Type

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from models.schemas import ArticleAnalysis, MultiArticleAnalysis


class GeminiClientError(RuntimeError):
    """Raised when the Gemini API cannot return a usable response."""


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeminiJsonResponse:
    """Container for a parsed Gemini JSON response."""

    raw_text: str
    data: Any


class GeminiClient:
    """Shared Gemini wrapper that provides consistent prompt + JSON handling."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        prompt_dir: Optional[Path | str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.default_model = default_model or os.environ.get("MODEL", "gemini-2.5-flash")
        self.prompt_dir = Path(
            prompt_dir
            or Path(__file__).resolve().parent.parent
            / "intelligence"
            / "config"
            / "prompts"
        )
        self._client: Optional[genai.Client] = None
        self._structured_models: Dict[str, Any] = {}

    # ---------------------------------------------------------------------
    # Core helpers
    # ---------------------------------------------------------------------
    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise GeminiClientError("GEMINI_API_KEY not configured.")

        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _get_structured_model(self, model_name: str) -> Any:
        """Return a model handle for structured responses.
        
        Note: This is now a no-op since we handle structured responses
        directly in generate_structured_response using response_schema.
        """
        # Not actually used anymore, but kept for backwards compatibility
        return None

    def _load_prompt(self, template_name: str) -> str:
        template_path = self.prompt_dir / template_name
        if not template_path.exists():
            raise GeminiClientError(f"Prompt template not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    @staticmethod
    def _clean_json_payload(raw_text: str) -> str:
        cleaned = raw_text.strip()
        if not cleaned:
            raise GeminiClientError("Gemini returned an empty response.")

        # Remove Markdown code fences.
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()

        if cleaned.startswith("{") or cleaned.startswith("["):
            return cleaned

        # Try to extract the first JSON object/array from the text.
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if not match:
            raise GeminiClientError("Unable to locate JSON payload in Gemini response.")
        return match.group(1)

    @staticmethod
    def parse_json_response(raw_text: str) -> Any:
        """Parse Gemini text into JSON with improved resilience."""

        payload = GeminiClient._clean_json_payload(raw_text)
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:  # noqa: BLE001 - expose parsing issues
            raise GeminiClientError(f"Gemini returned invalid JSON: {exc}") from exc
        return parsed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_json_response(
        self,
        template_name: str,
        context: Dict[str, Any],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> GeminiJsonResponse:
        """Render a prompt template and request a JSON response from Gemini."""

        prompt_template = self._load_prompt(template_name)
        try:
            prompt = prompt_template.format(**context)
        except KeyError as exc:  # noqa: BLE001 - configuration level error
            missing = exc.args[0]
            raise GeminiClientError(
                f"Prompt context missing required key '{missing}' for template '{template_name}'."
            ) from exc

        if system_prompt:
            contents: Any = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(system_prompt.strip())],
                ),
                types.Content(role="user", parts=[types.Part.from_text(prompt.strip())]),
            ]
        else:
            contents = prompt

        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "response_mime_type": "application/json",
        }

        if response_schema is not None:
            schema_config: Any = response_schema
            if isinstance(response_schema, dict) and hasattr(types, "Schema"):
                try:
                    schema_config = types.Schema(response_schema)
                except TypeError:
                    try:
                        schema_config = types.Schema.from_dict(response_schema)  # type: ignore[attr-defined]
                    except Exception:
                        schema_config = response_schema
            config_kwargs["response_schema"] = schema_config

        try:
            response = self._get_client().models.generate_content(
                model=model or self.default_model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:  # noqa: BLE001 - surface API issues with context
            raise GeminiClientError(f"Gemini API error: {exc}") from exc

        parsed = self.parse_json_response(response.text or "")
        return GeminiJsonResponse(raw_text=response.text or "", data=parsed)

    def generate_structured_response(
        self,
        template_name: str,
        context: Dict[str, Any],
        *,
        response_model: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> BaseModel:
        """Render a prompt template and request a structured response from Gemini."""

        prompt_template = self._load_prompt(template_name)
        try:
            prompt = prompt_template.format(**context)
        except KeyError as exc:  # noqa: BLE001
            missing = exc.args[0]
            raise GeminiClientError(
                f"Prompt context missing required key '{missing}' for template '{template_name}'."
            ) from exc

        if system_prompt:
            contents: Any = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(system_prompt.strip())],
                ),
                types.Content(role="user", parts=[types.Part.from_text(prompt.strip())]),
            ]
        else:
            contents = prompt

        # Get the JSON schema and convert it to the format Gemini expects
        json_schema = response_model.model_json_schema()
        
        # The new SDK requires wrapping the schema properly
        # See: https://ai.google.dev/gemini-api/docs/json-mode
        try:
            response_schema = types.Schema.from_dict(json_schema)
        except Exception:
            # Fallback: try using the schema directly
            response_schema = json_schema

        generation_config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        try:
            response = self._get_client().models.generate_content(
                model=model or self.default_model,
                contents=contents,
                config=generation_config,
            )
        except Exception as exc:  # noqa: BLE001
            raise GeminiClientError(f"Gemini API error: {exc}") from exc

        raw_text = (response.text or "").strip()
        if not raw_text:
            logger.error(
                "Gemini returned an empty structured response.",
                extra={"operation": "gemini_structured_response", "model": model or self.default_model},
            )
            raise GeminiClientError("Gemini returned an empty structured response.")

        try:
            return response_model.model_validate_json(raw_text)
        except ValidationError as exc:
            error_types = {
                err.get("type")
                for err in exc.errors()
                if isinstance(err, dict)
            }
            truncated = raw_text[:500]
            if "json_invalid" in error_types:
                logger.error(
                    "Gemini returned non-JSON payload.",
                    extra={
                        "operation": "gemini_structured_response",
                        "model": model or self.default_model,
                        "response_preview": truncated,
                    },
                )
                raise GeminiClientError(
                    "Gemini returned a non-JSON payload when structured output was required. "
                    f"Raw response: {raw_text}"
                ) from exc

            logger.error(
                "Gemini structured response failed validation.",
                extra={
                    "operation": "gemini_structured_response",
                    "model": model or self.default_model,
                    "response_preview": truncated,
                    "validation_errors": exc.errors(),
                },
            )
            raise GeminiClientError(
                "Gemini structured response failed Pydantic validation. "
                f"Errors: {exc} Raw response: {raw_text}"
            ) from exc

    def generate_text(
        self,
        *,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        response_mime_type: str = "text/plain",
    ) -> str:
        """Generate raw text from Gemini while reusing configuration plumbing."""

        if system_prompt:
            contents: Any = [
                types.Content(role="user", parts=[types.Part.from_text(system_prompt.strip())]),
                types.Content(role="user", parts=[types.Part.from_text(prompt.strip())]),
            ]
        else:
            contents = prompt

        try:
            response = self._get_client().models.generate_content(
                model=model or self.default_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_mime_type=response_mime_type,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise GeminiClientError(f"Gemini API error: {exc}") from exc

        return (response.text or "").strip()

    # ------------------------------------------------------------------
    # Legacy helpers retained for backwards compatibility
    # ------------------------------------------------------------------
    def analyze_article_structured(
        self,
        content: str,
        *,
        additional_instructions: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ArticleAnalysis:
        """Return a structured analysis for a single article."""

        context = {
            "content": content,
            "additional_instructions": additional_instructions or "No additional direction provided.",
        }

        return self.generate_structured_response(
            "article_analysis_prompt.txt",
            context,
            response_model=ArticleAnalysis,
            model=model,
            temperature=0.4,
            max_output_tokens=2048,
        )

    def synthesize_multi_article_analysis(
        self,
        query: str,
        contents: list[dict[str, str]],
        *,
        model: Optional[str] = None,
    ) -> MultiArticleAnalysis:
        """Generate a structured synthesis across multiple articles."""

        source_material = []
        for idx, doc in enumerate(contents, start=1):
            chunk = [f"--- Source {idx} ---"]
            chunk.append(f"URL: {doc.get('url', 'N/A')}")
            chunk.append(f"Title: {doc.get('title', 'N/A')}")
            markdown = doc.get("markdown", "")
            chunk.append(f"Content:\n{markdown[:2000]}")
            source_material.append("\n".join(chunk))

        context = {
            "query": query,
            "source_material": "\n\n".join(source_material),
        }

        return self.generate_structured_response(
            "synthesize_article_prompt.txt",
            context,
            response_model=MultiArticleAnalysis,
            model=model,
            temperature=0.6,
            max_output_tokens=4096,
        )

    def synthesize_content(
        self,
        query: str,
        contents: list[dict[str, str]],
        *,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compose an article synthesis response leveraging the template system."""

        source_material = []
        for idx, doc in enumerate(contents, start=1):
            chunk = [f"--- Source {idx} ---"]
            chunk.append(f"URL: {doc.get('url', 'N/A')}")
            chunk.append(f"Title: {doc.get('title', 'N/A')}")
            markdown = doc.get("markdown", "")
            chunk.append(f"Content:\n{markdown[:2000]}")
            source_material.append("\n".join(chunk))

        response = self.generate_json_response(
            "synthesize_article_prompt.txt",
            {"query": query, "source_material": "\n\n".join(source_material)},
            model=model,
            temperature=0.7,
            max_output_tokens=4096,
        )

        return {
            "success": True,
            **response.data,
        }

    def analyze_content(
        self,
        content: str,
        prompt: Optional[str] = None,
        *,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze a block of content with an optional custom prompt."""

        analysis_prompt = prompt or (
            "Analyze this scraped web content and provide:\n\n"
            "1. Executive summary (2-3 sentences).\n"
            "2. Key insights (3-5 bullets).\n"
            "3. Outstaffer relevance (paragraph).\n"
            "4. Content angle ideas (3 suggestions).\n"
            "5. Action items (2-3 points).\n\n"
            "CONTENT TO ANALYSE:\n{content}"
        )

        rendered_prompt = analysis_prompt.format(content=content)

        generated = self.generate_text(
            prompt=rendered_prompt,
            model=model,
            temperature=0.7,
            max_output_tokens=2048,
        )

        return {
            "success": bool(generated),
            "analysis": generated,
        }


__all__ = ["GeminiClient", "GeminiClientError", "GeminiJsonResponse"]

