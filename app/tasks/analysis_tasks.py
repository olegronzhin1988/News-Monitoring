# analysis_tasks, includes service functions for analysis and celery tasks

from uuid import UUID
import asyncio
from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from datetime import datetime, timedelta, timezone
from app.core.config import settings as stngs
from app.core.celery_app import celery_app
from app.models.models import SubscriptionsModel, NewsAnalysisModel
from app.services.news_fetcher import fetch_news
from app.services.llm_analyzer import analyze_articles

# SERVICE FUNCTIONS.
# Service function, transforms NewsAnalysisModel into dict
def _NewsAnalysisModel_to_dict(analysis:NewsAnalysisModel) -> dict:
        result = {
    "id": str(analysis.id),
    "subscription_id": str(analysis.subscription_id),
    "articles_count": analysis.articles_count,
    "sentiment_score": analysis.sentiment_score,
    "sentiment_label": analysis.sentiment_label,
    "summary": analysis.summary,
    "key_events": analysis.key_events,
    "ai_provider_used": analysis.ai_provider_used,
}   
        return result

# Main service function
async def _analyze_subscription_async(subscription_id:str)-> dict:
    # Creating local async engine for celery tasks
    engine = create_async_engine(stngs.DATABASE_URL)
    session_celery = async_sessionmaker(engine, expire_on_commit=False)

    # Looking for subscription
    try: 
        async with session_celery() as session:
            subscription=await session.get(SubscriptionsModel, UUID(subscription_id))
            if not subscription:
                raise ValueError(f"Subscription {subscription_id} not found")

            # Taking out wars to neglect lazy loading
            topic=subscription.topic
            language = subscription.language
            subscription_pk=subscription.id

        # Calling service function to get articles
        articles= await fetch_news(topic=topic,
                                language=language)
        analys_dict={}
        analys_dict["subscription_id"] = subscription_pk

        # If no articles found 
        if not articles:
            analys_dict["articles_count"] = 0
            analys_dict["sentiment_score"] = 0.0
            analys_dict["sentiment_label"] = "neutral"
            analys_dict["summary"] = "no articles found"
            analys_dict["key_events"] = []
            analys_dict["ai_provider_used"] = "no_llm_call"
            analys_dict["raw_response"] = {}

        # if articles were found
        else:
            analysis_res = await analyze_articles(topic=topic,
                                                articles=articles)
            analys_dict["articles_count"] = len(articles)

            # Add analysis result to new_analysis
            analys_dict = analys_dict | analysis_res

        async with session_celery() as session:
            new_analysis = NewsAnalysisModel(**analys_dict)
            session.add(new_analysis)
            await session.commit()
            await session.refresh(new_analysis)
            result = _NewsAnalysisModel_to_dict(new_analysis)
        
        return result
    finally:
        await engine.dispose()

# Service function to launch analyses for subscriptions
async def _dispatch_due_analyses_async():
    # Creating local async engine for celery tasks
    engine = create_async_engine(stngs.DATABASE_URL)
    session_celery = async_sessionmaker(engine, expire_on_commit=False)


    # Looking for active subscriptions
    try:
        dispatched_uuids  =[] 
        async with session_celery() as session:
            query = select(SubscriptionsModel).where(SubscriptionsModel.is_active == True)
            result = await session.execute(query)
            subscriptions_found = result.scalars().all()

            # If there is any active subscriptions found
            for subscription in subscriptions_found:
                query = select(NewsAnalysisModel).where(
                    NewsAnalysisModel.subscription_id == subscription.id
                    ).order_by(
                        desc(NewsAnalysisModel.analyzed_at)
                        ).limit(1)
                result = await session.execute(query)
                last_analysis = result.scalar_one_or_none()

                # Creating delayed task for subscription if there is no analysis or it was too long ago              
                if not last_analysis or (datetime.now(timezone.utc) - last_analysis.analyzed_at) >= timedelta(minutes=subscription.check_interval_minutes):
                    analyze_subscription_task.delay(str(subscription.id))                
                    dispatched_uuids.append(str(subscription.id))

        # Return analyzed subscriptions` UUIDs
        return dispatched_uuids
    finally:
        await engine.dispose()


# CELERY TASKS.
# Analyze subscription task, launches subscription analysis
@celery_app.task(name="analyze_subscription")
def analyze_subscription_task(subscription_id: str):
    result = asyncio.run(_analyze_subscription_async(subscription_id))
    return result

# Dispatcher for subscription analyses
@celery_app.task(name="dispatch_due_analyses")
def dispatch_due_analyses_task():
    result = asyncio.run(_dispatch_due_analyses_async())
    return result