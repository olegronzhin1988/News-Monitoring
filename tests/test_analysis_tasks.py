# test_analysis_tasks.py — integration tests for the async service functions
# behind the Celery tasks: _analyze_subscription_async, _dispatch_due_analyses_async,
# _send_pending_alerts_async.
#
# These functions create their own local SQLAlchemy engine from settings.DATABASE_URL
# instead of using the get_db FastAPI dependency (see analysis_tasks.py — this was a
# deliberate fix for asyncio event loop issues on Windows). conftest.py points
# settings.DATABASE_URL at the isolated test database before the app is imported,
# so these functions write to the test DB automatically without any extra wiring.
#
# External APIs (NewsAPI, Groq/OpenRouter, Telegram) are mocked; the database is real.

import pytest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from unittest.mock import AsyncMock

from app.models.models import SubscriptionsModel, NewsAnalysisModel, AlertsModel
from app.tasks.analysis_tasks import (
    _analyze_subscription_async,
    _dispatch_due_analyses_async,
    _send_pending_alerts_async,
)


async def _create_subscription(session, **overrides):
    defaults = {"topic": "Bitcoin", "language": "en", "check_interval_minutes": 60}
    defaults.update(overrides)
    subscription = SubscriptionsModel(**defaults)
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return subscription


class TestAnalyzeSubscriptionAsync:
    @pytest.mark.asyncio
    async def test_raises_when_subscription_does_not_exist(self, db_session):
        fake_id = "11111111-1111-1111-1111-111111111111"

        with pytest.raises(ValueError, match="not found"):
            await _analyze_subscription_async(fake_id)

    @pytest.mark.asyncio
    async def test_saves_neutral_analysis_when_no_articles_found(self, db_session, mocker):
        subscription = await _create_subscription(db_session)
        mocker.patch(
            "app.tasks.analysis_tasks.fetch_news",
            new=AsyncMock(return_value=[]),
        )
        mock_analyze = mocker.patch(
            "app.tasks.analysis_tasks.analyze_articles",
            new=AsyncMock(),
        )

        result = await _analyze_subscription_async(str(subscription.id))

        assert result["articles_count"] == 0
        assert result["sentiment_label"] == "neutral"
        assert result["ai_provider_used"] == "no_llm_call"
        # The LLM must never be called when there are no articles to analyze.
        mock_analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_saves_llm_result_when_articles_are_found(self, db_session, mocker):
        subscription = await _create_subscription(db_session)
        fake_articles = [{"title": "Bitcoin rallies", "description": "x"}] * 5
        llm_result = {
            "sentiment_score": 0.6,
            "sentiment_label": "positive",
            "summary": "Good news for Bitcoin.",
            "key_events": ["Bitcoin rallies"],
            "ai_provider_used": "groq",
            "raw_response": {"sentiment_score": 0.6},
        }
        mocker.patch(
            "app.tasks.analysis_tasks.fetch_news",
            new=AsyncMock(return_value=fake_articles),
        )
        mocker.patch(
            "app.tasks.analysis_tasks.analyze_articles",
            new=AsyncMock(return_value=llm_result),
        )

        result = await _analyze_subscription_async(str(subscription.id))

        assert result["articles_count"] == 5
        assert result["sentiment_score"] == 0.6
        assert result["ai_provider_used"] == "groq"

    @pytest.mark.asyncio
    async def test_creates_first_analysis_alert_on_first_run(self, db_session, mocker):
        subscription = await _create_subscription(db_session)
        mocker.patch(
            "app.tasks.analysis_tasks.fetch_news",
            new=AsyncMock(return_value=[]),
        )

        await _analyze_subscription_async(str(subscription.id))

        alerts = (
            await db_session.execute(
                select(AlertsModel).where(AlertsModel.subscription_id == subscription.id)
            )
        ).scalars().all()
        assert len(alerts) == 1
        assert alerts[0].alert_type == "first_analysis"
        assert alerts[0].is_sent is False

    @pytest.mark.asyncio
    async def test_does_not_create_alert_when_sentiment_is_stable(self, db_session, mocker):
        subscription = await _create_subscription(db_session)
        # Seed a previous analysis with a sentiment_score close to what's coming next.
        previous = NewsAnalysisModel(
            subscription_id=subscription.id,
            analyzed_at=datetime.now(timezone.utc) - timedelta(hours=1),
            articles_count=5,
            sentiment_score=0.2,
            sentiment_label="positive",
            summary="prev",
            key_events=[],
            ai_provider_used="groq",
            raw_response={},
        )
        db_session.add(previous)
        await db_session.commit()

        mocker.patch(
            "app.tasks.analysis_tasks.fetch_news",
            new=AsyncMock(return_value=[{"title": "t", "description": "d"}]),
        )
        mocker.patch(
            "app.tasks.analysis_tasks.analyze_articles",
            new=AsyncMock(return_value={
                "sentiment_score": 0.25,  # close to 0.2 -> no drift
                "sentiment_label": "positive",
                "summary": "still positive",
                "key_events": [],
                "ai_provider_used": "groq",
                "raw_response": {},
            }),
        )

        await _analyze_subscription_async(str(subscription.id))

        alerts = (
            await db_session.execute(
                select(AlertsModel).where(AlertsModel.subscription_id == subscription.id)
            )
        ).scalars().all()
        assert len(alerts) == 0


class TestDispatchDueAnalysesAsync:
    @pytest.mark.asyncio
    async def test_dispatches_subscription_with_no_prior_analysis(self, db_session, mocker):
        subscription = await _create_subscription(db_session)
        mock_delay = mocker.patch(
            "app.tasks.analysis_tasks.analyze_subscription_task.delay"
        )

        dispatched = await _dispatch_due_analyses_async()

        assert str(subscription.id) in dispatched
        mock_delay.assert_called_once_with(str(subscription.id))

    @pytest.mark.asyncio
    async def test_dispatches_subscription_when_interval_has_elapsed(self, db_session, mocker):
        subscription = await _create_subscription(db_session, check_interval_minutes=30)
        old_analysis = NewsAnalysisModel(
            subscription_id=subscription.id,
            analyzed_at=datetime.now(timezone.utc) - timedelta(minutes=45),
            articles_count=1,
            sentiment_score=0.0,
            sentiment_label="neutral",
            summary="old",
            key_events=[],
            ai_provider_used="groq",
            raw_response={},
        )
        db_session.add(old_analysis)
        await db_session.commit()
        mocker.patch("app.tasks.analysis_tasks.analyze_subscription_task.delay")

        dispatched = await _dispatch_due_analyses_async()

        assert str(subscription.id) in dispatched

    @pytest.mark.asyncio
    async def test_skips_subscription_analyzed_recently(self, db_session, mocker):
        subscription = await _create_subscription(db_session, check_interval_minutes=60)
        recent_analysis = NewsAnalysisModel(
            subscription_id=subscription.id,
            analyzed_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            articles_count=1,
            sentiment_score=0.0,
            sentiment_label="neutral",
            summary="recent",
            key_events=[],
            ai_provider_used="groq",
            raw_response={},
        )
        db_session.add(recent_analysis)
        await db_session.commit()
        mock_delay = mocker.patch("app.tasks.analysis_tasks.analyze_subscription_task.delay")

        dispatched = await _dispatch_due_analyses_async()

        assert str(subscription.id) not in dispatched
        mock_delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_inactive_subscriptions(self, db_session, mocker):
        await _create_subscription(db_session, is_active=False)
        mock_delay = mocker.patch("app.tasks.analysis_tasks.analyze_subscription_task.delay")

        dispatched = await _dispatch_due_analyses_async()

        assert dispatched == []
        mock_delay.assert_not_called()


class TestSendPendingAlertsAsync:
    @pytest.mark.asyncio
    async def test_sends_unsent_alert_and_marks_it_sent(self, db_session, mocker):
        subscription = await _create_subscription(db_session)
        analysis = NewsAnalysisModel(
            subscription_id=subscription.id,
            analyzed_at=datetime.now(timezone.utc),
            articles_count=1,
            sentiment_score=0.0,
            sentiment_label="neutral",
            summary="s",
            key_events=[],
            ai_provider_used="groq",
            raw_response={},
        )
        db_session.add(analysis)
        await db_session.commit()
        await db_session.refresh(analysis)

        alert = AlertsModel(
            subscription_id=subscription.id,
            analysis_id=analysis.id,
            alert_type="first_analysis",
            text="First analysis created.",
            is_sent=False,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        mocker.patch(
            "app.tasks.analysis_tasks.send_telegram_message",
            new=AsyncMock(return_value=True),
        )

        sent_ids = await _send_pending_alerts_async()

        assert alert.id in sent_ids
        await db_session.refresh(alert)
        assert alert.is_sent is True
        assert alert.sent_at is not None

    @pytest.mark.asyncio
    async def test_leaves_alert_unsent_when_telegram_fails(self, db_session, mocker):
        subscription = await _create_subscription(db_session)
        analysis = NewsAnalysisModel(
            subscription_id=subscription.id,
            analyzed_at=datetime.now(timezone.utc),
            articles_count=1,
            sentiment_score=0.0,
            sentiment_label="neutral",
            summary="s",
            key_events=[],
            ai_provider_used="groq",
            raw_response={},
        )
        db_session.add(analysis)
        await db_session.commit()
        await db_session.refresh(analysis)

        alert = AlertsModel(
            subscription_id=subscription.id,
            analysis_id=analysis.id,
            alert_type="first_analysis",
            text="First analysis created.",
            is_sent=False,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        mocker.patch(
            "app.tasks.analysis_tasks.send_telegram_message",
            new=AsyncMock(return_value=False),
        )

        sent_ids = await _send_pending_alerts_async()

        assert alert.id not in sent_ids
        await db_session.refresh(alert)
        assert alert.is_sent is False
        assert alert.sent_at is None

    @pytest.mark.asyncio
    async def test_ignores_already_sent_alerts(self, db_session, mocker):
        subscription = await _create_subscription(db_session)
        analysis = NewsAnalysisModel(
            subscription_id=subscription.id,
            analyzed_at=datetime.now(timezone.utc),
            articles_count=1,
            sentiment_score=0.0,
            sentiment_label="neutral",
            summary="s",
            key_events=[],
            ai_provider_used="groq",
            raw_response={},
        )
        db_session.add(analysis)
        await db_session.commit()
        await db_session.refresh(analysis)

        already_sent = AlertsModel(
            subscription_id=subscription.id,
            analysis_id=analysis.id,
            alert_type="first_analysis",
            text="Already sent.",
            is_sent=True,
            sent_at=datetime.now(timezone.utc),
        )
        db_session.add(already_sent)
        await db_session.commit()

        mock_send = mocker.patch(
            "app.tasks.analysis_tasks.send_telegram_message",
            new=AsyncMock(return_value=True),
        )

        sent_ids = await _send_pending_alerts_async()

        assert sent_ids == []
        mock_send.assert_not_called()
