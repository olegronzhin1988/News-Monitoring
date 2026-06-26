# analysis_tasks, includes tasks for analysis

from uuid import UUID
import asyncio
from app.core.celery_app import celery_app
from app.core.database import new_session
from app.models.models import SubscriptionsModel, NewsAnalysisModel
from app.services.news_fetcher import fetch_news
from app.services.llm_analyzer import analyze_articles

# Celery task
@celery_app.task(name="analyze_subscription")
def analyze_subscription_task(subscription_id: str):
    result = asyncio.run(_analyze_subscription_async(subscription_id))
    return result


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

# Looking for subscription     
    async with new_session() as session:
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

    async with new_session() as session:
        new_analysis = NewsAnalysisModel(**analys_dict)
        session.add(new_analysis)
        await session.commit()
        await session.refresh(new_analysis)
        result = _NewsAnalysisModel_to_dict(new_analysis)
    return result