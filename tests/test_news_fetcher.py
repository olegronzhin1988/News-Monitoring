# test_news_fetcher.py — tests for app.services.news_fetcher.fetch_news.
#
# NewsAPI is always mocked here via pytest-mock's `mocker.patch`, targeting
# httpx.AsyncClient.get (the actual HTTP call site inside fetch_news).
# No real network request is made in this test module.

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.news_fetcher import fetch_news, NewsAPIError


def _make_response(status_code: int, json_data: dict, text: str = ""):
    """Builds a minimal stand-in for an httpx.Response used by the mocked client."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.text = text or str(json_data)
    return response


@pytest.mark.asyncio
async def test_fetch_news_returns_parsed_articles_on_success(mocker):
    api_payload = {
        "status": "ok",
        "articles": [
            {
                "title": "Bitcoin hits new high",
                "description": "Price surge described.",
                "url": "https://example.com/a1",
                "publishedAt": "2026-01-01T00:00:00Z",
                "source": {"name": "Example News"},
            },
            {
                "title": "Bitcoin regulation update",
                "description": None,
                "url": "https://example.com/a2",
                "publishedAt": "2026-01-02T00:00:00Z",
                "source": {"name": "Crypto Daily"},
            },
        ],
    }
    mock_response = _make_response(200, api_payload)
    mocker.patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(return_value=mock_response),
    )

    articles = await fetch_news(topic="Bitcoin", language="en")

    assert len(articles) == 2
    assert articles[0]["title"] == "Bitcoin hits new high"
    assert articles[0]["source"] == "Example News"
    # description falls back to "" both when the key is missing AND when
    # NewsAPI explicitly sends "description": null (via `article.get(...) or ""`).
    assert articles[1]["description"] == ""


@pytest.mark.asyncio
async def test_fetch_news_filters_out_removed_articles(mocker):
    api_payload = {
        "status": "ok",
        "articles": [
            {"title": "[Removed]", "description": "x", "url": "u", "publishedAt": "t",
             "source": {"name": "s"}},
            {"title": "", "description": "x", "url": "u", "publishedAt": "t",
             "source": {"name": "s"}},
            {"title": "Real article", "description": "x", "url": "u", "publishedAt": "t",
             "source": {"name": "s"}},
        ],
    }
    mock_response = _make_response(200, api_payload)
    mocker.patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response))

    articles = await fetch_news(topic="Bitcoin")

    assert len(articles) == 1
    assert articles[0]["title"] == "Real article"


@pytest.mark.asyncio
async def test_fetch_news_raises_on_invalid_api_key(mocker):
    mock_response = _make_response(401, {}, text="Unauthorized")
    mocker.patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response))

    with pytest.raises(NewsAPIError, match="key error"):
        await fetch_news(topic="Bitcoin")


@pytest.mark.asyncio
async def test_fetch_news_raises_on_rate_limit(mocker):
    mock_response = _make_response(429, {}, text="Too Many Requests")
    mocker.patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response))

    with pytest.raises(NewsAPIError, match="rate limit"):
        await fetch_news(topic="Bitcoin")


@pytest.mark.asyncio
async def test_fetch_news_raises_on_unexpected_status_code(mocker):
    mock_response = _make_response(500, {}, text="Internal Server Error")
    mocker.patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response))

    with pytest.raises(NewsAPIError):
        await fetch_news(topic="Bitcoin")


@pytest.mark.asyncio
async def test_fetch_news_raises_when_api_status_field_is_not_ok(mocker):
    # NewsAPI can return HTTP 200 but still signal an application-level error
    # via the "status"/"message" fields in the JSON body.
    api_payload = {"status": "error", "message": "parametersMissing"}
    mock_response = _make_response(200, api_payload)
    mocker.patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response))

    with pytest.raises(NewsAPIError, match="parametersMissing"):
        await fetch_news(topic="Bitcoin")


@pytest.mark.asyncio
async def test_fetch_news_returns_empty_list_when_no_articles_found(mocker):
    api_payload = {"status": "ok", "articles": []}
    mock_response = _make_response(200, api_payload)
    mocker.patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response))

    articles = await fetch_news(topic="SomeObscureTopicWithNoNews")

    assert articles == []
