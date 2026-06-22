# subscriptions.py, includes router functions and endpoints

from fastapi import APIRouter, HTTPException, status
from app.core.database import SessionDep
from app.models.models import AlertsModel, SubscriptionsModel, NewsAnalysisModel
from app.schemas.subscriptions import SSubscriptionCreate, SSubscriptionResponse, SSubscriptionUpdate
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from uuid import UUID

# Service function, checks subscription and returns it if possible, else - raises exception
async def _subscription_check(subscription_id:UUID,
                              session:SessionDep) -> SSubscriptionResponse:
# Looking for subscription with ID
    subscription_found = await session.get(SubscriptionsModel, subscription_id)

# Exception if none found:
    if not subscription_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Subscription with ID {subscription_id} doesn`t exist")

# returning result
    return subscription_found

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

# GET subscriptions list, with skip and limit options 
@subscriptions_router.get("/",
                          status_code=status.HTTP_200_OK,
                          description="get subscriptions list")
async def subscription_get_list(session:SessionDep,
                                skip:int=0,
                                limit:int=100) -> list[SSubscriptionResponse]:
# Selecting subscriptions from db and returning them
    query = select(SubscriptionsModel).offset(skip).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()

# GET subscription via ID
@subscriptions_router.get("/{subscription_id}",
                          status_code=status.HTTP_200_OK,
                          description="Select subscription via ID")
async def subscription_get(subscription_id:UUID,
                           session:SessionDep) -> SSubscriptionResponse:
# Looking for subscription with ID
    return await _subscription_check(subscription_id, session)

# partially update subscription via ID, PATCH
@subscriptions_router.patch("/{subscription_id}",
                            status_code=status.HTTP_200_OK,
                            description="Partially update subscription via ID")
async def subscription_change(subscription_id:UUID,
                              session:SessionDep,
                              update_data:SSubscriptionUpdate) ->SSubscriptionResponse:
# Calling service function to check subscription
    subscription_found = await _subscription_check(subscription_id, session)

# creating update values for query
    values={}
    values = update_data.model_dump(exclude_unset=True)

# update subscription if there is something to update
    if values:
        query = update(SubscriptionsModel).where(SubscriptionsModel.id == subscription_id).values(**values)
        await session.execute(query)
        await session.commit()
        await session.refresh(subscription_found)
    return subscription_found

# DELETE subscription via subscription ID
@subscriptions_router.delete("/{subscription_id}",
                            status_code=status.HTTP_204_NO_CONTENT,
                            description="Delete subscription via ID")
async def subscription_delete(subscription_id:UUID,
                              session:SessionDep):
# Calling service function to check subscription
    subscription_found = await _subscription_check(subscription_id, session)

# Delete found subscription
    await session.delete(subscription_found)
    await session.commit()