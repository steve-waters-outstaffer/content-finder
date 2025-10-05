"""High-level Gemini client used across the intelligence pipeline."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.generativeai import types


class GeminiClientError(RuntimeError):
    """Raised when the Gemini API cannot return a usable response."""


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

    # ---------------------------------------------------------------------
    # Core helpers
    # ---------------------------------------------------------------------
    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise GeminiClientError("GEMINI_API_KEY not configured.")

        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

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

        try:
            response = self._get_client().models.generate_content(
                model=model or self.default_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:  # noqa: BLE001 - surface API issues with context
            raise GeminiClientError(f"Gemini API error: {exc}") from exc

        parsed = self.parse_json_response(response.text or "")
        return GeminiJsonResponse(raw_text=response.text or "", data=parsed)

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

