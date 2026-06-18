# subscriptions.py, includes router functions and endpoints

from fastapi import APIRouter, HTTPException, status
from app.core.database import SessionDep
from app.models.models import AlertsModel, SubscriptionsModel, NewsAnalysisModel
from app.schemas.subscriptions import SSubscriptionCreate, SSubscriptionResponse, SSubscriptionUpdate
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update

# Subscription router
subscriptions_router=APIRouter(prefix="/subscriptions",
                               tags=["subscriptions"])

# SUBSCRIPTIONS ENDPOINS
# Creare new subscription, POST
@subscriptions_router.post("/",
                           status_code=status.HTTP_201_CREATED,
                           description="Create new subscription")
async def subscription_create(session:SessionDep,
                              data_in:SSubscriptionCreate) -> SSubscriptionResponse:
# Creating dict for a new subscription to add to DB
    subscription_dict=data_in.model_dump()
   
# Creating new subscription
    new_subscription = SubscriptionsModel(**subscription_dict)
    session.add(new_subscription)
    await session.commit()
    await session.refresh(new_subscription)

# Returning new subscription
    return new_subscription