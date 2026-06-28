# test_sentiment_drift.py — tests for app.tasks.analysis_tasks._check_sentiment_drift.
#
# These tests talk to the real (isolated) test database, since the function
# under test issues several SQL queries against NewsAnalysisModel history.
# No external APIs are involved, so nothing is mocked here.

import pytest
from datetime import datetime, timedelta, timezone

from app.models.models import SubscriptionsModel, NewsAnalysisModel
from app.tasks.analysis_tasks import _check_sentiment_drift


async def _create_subscription(session, topic="Bitcoin"):
    subscription = SubscriptionsModel(topic=topic)
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def _create_analysis(session, subscription_id, sentiment_score, analyzed_at=None):
    analysis = NewsAnalysisModel(
        subscription_id=subscription_id,
        analyzed_at=analyzed_at or datetime.now(timezone.utc),
        articles_count=10,
        sentiment_score=sentiment_score,
        sentiment_label="neutral",
        summary="test summary",
        key_events=[],
        ai_provider_used="groq",
        raw_response={},
    )
    session.add(analysis)
    await session.commit()
    await session.refresh(analysis)
    return analysis


@pytest.mark.asyncio
async def test_returns_first_analysis_alert_when_no_history_exists(db_session):
    subscription = await _create_subscription(db_session)
    new_analysis = await _create_analysis(db_session, subscription.id, sentiment_score=0.2)

    result = await _check_sentiment_drift(
        session=db_session,
        subscription_id=subscription.id,
        new_analysis=new_analysis,
    )

    assert result is not None
    assert result["alert_type"] == "first_analysis"


@pytest.mark.asyncio
async def test_returns_none_when_drift_is_within_threshold(db_session):
    subscription = await _create_subscription(db_session)
    await _create_analysis(db_session, subscription.id, sentiment_score=0.3)
    new_analysis = await _create_analysis(db_session, subscription.id, sentiment_score=0.4)

    result = await _check_sentiment_drift(
        session=db_session,
        subscription_id=subscription.id,
        new_analysis=new_analysis,
    )

    # |0.4 - 0.3| = 0.1, well under the 0.5 threshold.
    assert result is None


@pytest.mark.asyncio
async def test_returns_sentiment_drop_when_current_score_is_much_lower(db_session):
    subscription = await _create_subscription(db_session)
    await _create_analysis(db_session, subscription.id, sentiment_score=0.6)
    new_analysis = await _create_analysis(db_session, subscription.id, sentiment_score=-0.1)

    result = await _check_sentiment_drift(
        session=db_session,
        subscription_id=subscription.id,
        new_analysis=new_analysis,
    )

    assert result is not None
    assert result["alert_type"] == "sentiment_drop"


@pytest.mark.asyncio
async def test_returns_sentiment_spike_when_current_score_is_much_higher(db_session):
    subscription = await _create_subscription(db_session)
    await _create_analysis(db_session, subscription.id, sentiment_score=-0.3)
    new_analysis = await _create_analysis(db_session, subscription.id, sentiment_score=0.5)

    result = await _check_sentiment_drift(
        session=db_session,
        subscription_id=subscription.id,
        new_analysis=new_analysis,
    )

    assert result is not None
    assert result["alert_type"] == "sentiment_spike"


@pytest.mark.asyncio
async def test_baseline_is_average_of_analyses_within_last_24_hours(db_session):
    subscription = await _create_subscription(db_session)
    now = datetime.now(timezone.utc)

    # Two analyses within the last 24h: average = (0.0 + 0.2) / 2 = 0.1
    await _create_analysis(db_session, subscription.id, sentiment_score=0.0,
                            analyzed_at=now - timedelta(hours=20))
    await _create_analysis(db_session, subscription.id, sentiment_score=0.2,
                            analyzed_at=now - timedelta(hours=2))

    # New analysis at 0.7 -> |0.7 - 0.1| = 0.6 >= 0.5 threshold -> drift expected.
    new_analysis = await _create_analysis(db_session, subscription.id, sentiment_score=0.7,
                                           analyzed_at=now)

    result = await _check_sentiment_drift(
        session=db_session,
        subscription_id=subscription.id,
        new_analysis=new_analysis,
    )

    assert result is not None
    assert result["alert_type"] == "sentiment_spike"


@pytest.mark.asyncio
async def test_falls_back_to_last_analysis_when_nothing_within_24_hours(db_session):
    subscription = await _create_subscription(db_session)
    now = datetime.now(timezone.utc)

    # Only an old analysis, well outside the 24h window — e.g. a subscription
    # with a check_interval_minutes greater than 1440.
    await _create_analysis(db_session, subscription.id, sentiment_score=0.5,
                            analyzed_at=now - timedelta(days=3))

    new_analysis = await _create_analysis(db_session, subscription.id, sentiment_score=-0.2,
                                           analyzed_at=now)

    result = await _check_sentiment_drift(
        session=db_session,
        subscription_id=subscription.id,
        new_analysis=new_analysis,
    )

    # baseline = 0.5 (the only past analysis), |-0.2 - 0.5| = 0.7 >= 0.5 -> drop.
    assert result is not None
    assert result["alert_type"] == "sentiment_drop"


@pytest.mark.asyncio
async def test_drift_check_is_isolated_per_subscription(db_session):
    # Analyses belonging to a different subscription must never influence
    # the baseline calculation for this one.
    subscription_a = await _create_subscription(db_session, topic="Bitcoin")
    subscription_b = await _create_subscription(db_session, topic="Tesla")

    await _create_analysis(db_session, subscription_b.id, sentiment_score=0.9)

    new_analysis = await _create_analysis(db_session, subscription_a.id, sentiment_score=0.1)

    result = await _check_sentiment_drift(
        session=db_session,
        subscription_id=subscription_a.id,
        new_analysis=new_analysis,
    )

    # subscription_a has no history of its own -> first_analysis, regardless
    # of subscription_b's data.
    assert result is not None
    assert result["alert_type"] == "first_analysis"
