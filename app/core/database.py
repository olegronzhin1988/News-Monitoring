# database.py file, database settings

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import Annotated
from fastapi import Depends
from app.core.config import settings as stngs

# Async engine with stngs.DATABASE_URL
engine = create_async_engine(stngs.DATABASE_URL)

# Session for engine
# Expire on_commit prevents uploaded/changed objects
# auto expiration after commit, so SQLAlchemy doesn`t
# do new SELECT of existing data 
new_session = async_sessionmaker(engine, 
                                 expire_on_commit=False)

# Dependency function for database session
async def get_db():
    async with new_session() as session:
        yield session

# Databasae session dependency
SessionDep = Annotated[AsyncSession, Depends(get_db)]