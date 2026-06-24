# analysis_tasks, includes tasks for analysis

from app.core.celery_app import celery_app
from app.models.models import SubscriptionsModel
from sqlalchemy.dialects.postgresql import UUID


async def _analyze_subscription_async(subscription_id:str)-> dict:
    async with AsyncSessionLocal() as session:
        subscription=await session.get(SubscriptionsModel, UUID(subscription_id))
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")


@celery_app.task(name="analyze_subscription")
def analyze_subscription_task(subscription_id:str):