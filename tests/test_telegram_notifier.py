# test_telegram_notifier.py — tests for app.services.telegram_notifier.

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.telegram_notifier import send_telegram_message


def _make_response(status_code: int):
    response = MagicMock()
    response.status_code = status_code
    return response


@pytest.mark.asyncio
async def test_returns_true_on_successful_send(mocker):
    mocker.patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(return_value=_make_response(200)),
    )

    result = await send_telegram_message("Hello from tests")

    assert result is True


@pytest.mark.asyncio
async def test_returns_false_on_telegram_error_response(mocker):
    # E.g. bot not started, invalid chat_id, etc. Telegram API errors must NOT
    # raise — they degrade gracefully so the rest of the pipeline (the analysis,
    # the already-persisted alert) is unaffected. The next send_pending_alerts
    # tick will simply retry.
    mocker.patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(return_value=_make_response(404)),
    )

    result = await send_telegram_message("Hello from tests")

    assert result is False


@pytest.mark.asyncio
async def test_propagates_network_level_exceptions(mocker):
    # NOTE: the current implementation only catches non-200 status codes,
    # not network-level exceptions (e.g. connection errors, timeouts).
    # This test documents that current behavior rather than asserting it is
    # ideal — see the "Suggested follow-ups" note left for the developer.
    mocker.patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=Exception("network unreachable")),
    )

    with pytest.raises(Exception, match="network unreachable"):
        await send_telegram_message("Hello from tests")
