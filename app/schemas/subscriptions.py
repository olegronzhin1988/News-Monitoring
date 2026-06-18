# subscription.py schemas file, contains subscription schemas

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID

# Sunscription creation schema, as data provided by user
class SSubscriptionCreate(BaseModel):
    topic:str = Field(default=...,
                      title="Subscription topic")
    keywords:list[str] = Field(default=[],
                               title="Topic keywords")
    language:str = Field(default="en",
                         title="News language")
    check_interval_minutes:int = Field(default=60,
                                       title="News check regularity, in minutes")
# Subscription update schema
class SSubscriptionUpdate(BaseModel):
    topic: Optional[str] = Field(default=None,
                                 title="Subscription topic")
    keywords: Optional[list[str]] = Field(default=None,
                                          title="Topic keywords")
    language: Optional[str] = Field(default=None,
                                    title="News language")
    check_interval_minutes: Optional[int] = Field(default=None,
                                                  title="News check regularity, in minutes")
    is_active: Optional[bool] = Field(default=None,
                                      title="Subscription activity status")

# Subscription response schema
class SSubscriptionResponse(SSubscriptionCreate):
    id: UUID = Field(default=...,
                     title="Subscription ID")
    is_active:bool = Field(default=True,
                           title="Subscription activity status")
    created_at:datetime = Field(title="Creation time")
    updated_at:datetime = Field(title="Update time")

    model_config=ConfigDict(from_attributes=True)