# test_llm_analyzer.py — tests for app.services.llm_analyzer.
#
# Both LLM providers (Groq via the `groq` SDK, OpenRouter via raw httpx) are
# mocked. No real LLM call is made anywhere in this module.

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.llm_analyzer import (
    analyze_articles,
    _parse_llm_response,
    _build_prompt,
    LLMAnalysisError,
)


SAMPLE_ARTICLES = [
    {"title": "Bitcoin rallies", "description": "Price up 5%."},
    {"title": "Regulators eye crypto", "description": "New rules proposed."},
]

VALID_LLM_JSON = {
    "sentiment_score": 0.4,
    "sentiment_label": "positive",
    "summary": "Bitcoin is up, regulation is coming.",
    "key_events": ["Bitcoin rallies", "Regulators eye crypto"],
}


class TestParseLLMResponse:
    def test_parses_clean_json(self):
        result = _parse_llm_response(json.dumps(VALID_LLM_JSON))
        assert result == VALID_LLM_JSON

    def test_strips_markdown_code_fences(self):
        wrapped = f"```json\n{json.dumps(VALID_LLM_JSON)}\n```"
        result = _parse_llm_response(wrapped)
        assert result == VALID_LLM_JSON

    def test_ignores_trailing_text_after_the_json_object(self):
        # Regression guard for the "Extra data" JSONDecodeError we hit in production
        # when the model added explanatory text after the JSON object.
        chatty = json.dumps(VALID_LLM_JSON) + "\nHope this helps!"
        result = _parse_llm_response(chatty)
        assert result == VALID_LLM_JSON

    def test_raises_when_no_json_object_present(self):
        with pytest.raises(LLMAnalysisError, match="No JSON object found"):
            _parse_llm_response("Sorry, I cannot help with that.")


class TestBuildPrompt:
    def test_truncates_to_first_15_articles(self):
        many_articles = [
            {"title": f"Article {i}", "description": f"Desc {i}"} for i in range(30)
        ]

        prompt = _build_prompt(topic="Bitcoin", articles=many_articles)

        # Only the first 15 titles (indices 0-14) should appear in the rendered prompt.
        assert "Article 14" in prompt
        assert "Article 15" not in prompt

    def test_includes_topic_in_prompt(self):
        prompt = _build_prompt(topic="Bitcoin", articles=SAMPLE_ARTICLES)
        assert "Bitcoin" in prompt


class TestAnalyzeArticles:
    @pytest.mark.asyncio
    async def test_uses_groq_when_it_succeeds(self, mocker):
        mocker.patch(
            "app.services.llm_analyzer._call_groq",
            new=AsyncMock(return_value=json.dumps(VALID_LLM_JSON)),
        )
        mock_openrouter = mocker.patch(
            "app.services.llm_analyzer._call_openrouter",
            new=AsyncMock(),
        )

        result = await analyze_articles(topic="Bitcoin", articles=SAMPLE_ARTICLES)

        assert result["sentiment_score"] == 0.4
        assert result["sentiment_label"] == "positive"
        assert result["ai_provider_used"] == "groq"
        # raw_response must hold the parsed payload for auditing.
        assert result["raw_response"] == VALID_LLM_JSON
        # OpenRouter is the fallback — it must not be called when Groq succeeds.
        mock_openrouter.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_openrouter_when_groq_fails(self, mocker):
        mocker.patch(
            "app.services.llm_analyzer._call_groq",
            new=AsyncMock(side_effect=Exception("groq is down")),
        )
        mocker.patch(
            "app.services.llm_analyzer._call_openrouter",
            new=AsyncMock(return_value=json.dumps(VALID_LLM_JSON)),
        )

        result = await analyze_articles(topic="Bitcoin", articles=SAMPLE_ARTICLES)

        assert result["ai_provider_used"] == "openrouter"
        assert result["sentiment_label"] == "positive"

    @pytest.mark.asyncio
    async def test_raises_when_both_providers_fail(self, mocker):
        mocker.patch(
            "app.services.llm_analyzer._call_groq",
            new=AsyncMock(side_effect=Exception("groq is down")),
        )
        mocker.patch(
            "app.services.llm_analyzer._call_openrouter",
            new=AsyncMock(side_effect=Exception("openrouter is down")),
        )

        with pytest.raises(LLMAnalysisError, match="Both providers failed"):
            await analyze_articles(topic="Bitcoin", articles=SAMPLE_ARTICLES)

    @pytest.mark.asyncio
    async def test_raises_when_groq_returns_malformed_json(self, mocker):
        mocker.patch(
            "app.services.llm_analyzer._call_groq",
            new=AsyncMock(return_value="not json at all"),
        )
        mocker.patch(
            "app.services.llm_analyzer._call_openrouter",
            new=AsyncMock(return_value="also not json"),
        )

        with pytest.raises(LLMAnalysisError):
            await analyze_articles(topic="Bitcoin", articles=SAMPLE_ARTICLES)
