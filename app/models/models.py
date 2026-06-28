# models.py, includes app models

from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from sqlalchemy import Text, JSON, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from datetime import datetime, timezone
from typing import List
from uuid import uuid4, UUID as PyUUID

# Base class for other classes
class Base(DeclarativeBase):
    pass

# Users` subscriptions on topics model 
class SubscriptionsModel(Base):
    __tablename__="subscriptions"
# Subscription id
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True),
                                    primary_key=True,
                                    default=uuid4)
# Subscription topic
    topic: Mapped[str] = mapped_column(nullable=False)
# Additional key words
    keywords: Mapped[list] = mapped_column(ARRAY(String), 
                                           default=list)
# News language 
    language: Mapped[str] = mapped_column(default="en")
# Subscription status, active or mot
    is_active: Mapped[bool] = mapped_column(default=True)
# Check regularity, in minutes
    check_interval_minutes: Mapped[int] = mapped_column(default=60)
# Creation time
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=lambda: datetime.now(timezone.utc))
# Update time
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=lambda: datetime.now(timezone.utc),
                                                 onupdate=lambda: datetime.now(timezone.utc))
# Relatonships
# subscription -> news_analyses, one to many
    news_analyses: Mapped[List["NewsAnalysisModel"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )
# subscription -> alerts, one to many
    alerts: Mapped[List["AlertsModel"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


# Analysis results
class NewsAnalysisModel(Base):
    __tablename__="news_analyses"
#Analysis id
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True),
                                    primary_key=True,
                                    default=uuid4)
# Subscription ID, link to subscriptions
    subscription_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True),
                                                 ForeignKey("subscriptions.id"))
# Date of analysis
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=lambda: datetime.now(timezone.utc))
# Number of articles analysed
    articles_count: Mapped[int]
# Analysis sentiment value, -1.0...1.0
    sentiment_score: Mapped[float]
# Analysis sentiment, "positive"/"neutral"/"negative" 
    sentiment_label: Mapped[str]
# Final resume
    summary: Mapped[str] = mapped_column(Text)
# Analysis key events
    key_events: Mapped[list] = mapped_column(ARRAY(String),
                                             default=list)
# LLM used for analysis
    ai_provider_used: Mapped[str]
# Full LLM answer
    raw_response: Mapped[dict] = mapped_column(JSON)
# Relationships
# news_analysis -> subscription, many to one
    subscription: Mapped[SubscriptionsModel] = relationship(back_populates="news_analyses")
# news_analysis -> alerts, one to many
    alerts: Mapped[List["AlertsModel"]] = relationship(
        back_populates="news_analysis",
        cascade="all, delete-orphan"
    )


# Sent notifications
class AlertsModel(Base):
    __tablename__="alerts"
# notification ID
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True),
                                    primary_key=True,
                                    default=uuid4)
# Subscription ID, link to subscriptions
    subscription_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True),
                                                 ForeignKey("subscriptions.id"))
# Analysis ID, link to news_analysis
    analysis_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True),
                                                 ForeignKey("news_analyses.id"))
# Notification type, "sentiment_drop"/"sentiment_spike"/"first_analysis"
    alert_type: Mapped[str]
# Notification text
    text: Mapped[str] = mapped_column(Text)
# Sending Date and time 
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                              default=lambda:datetime.now(timezone.utc))
# Sending status
    is_sent: Mapped[bool]
# Relationships
# alert -> subscription, many to one
    subscription: Mapped[SubscriptionsModel] = relationship(back_populates="alerts")
# alert -> news_analysis, many to one
    news_analysis: Mapped[NewsAnalysisModel] = relationship(back_populates="alerts")