# config.py file, contains security objects

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
class Settings(BaseSettings):

    GROQ_API_KEY:str
    NEWS_API_KEY:str
    TELEGRAM_BOT_TOKEN:str
    TELEGRAM_CHAT_ID:str

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB:str = "news_monitoring_db"
    POSTGRES_HOST:str = "localhost"
    POSTGRES_PORT:int = 5432

    @computed_field
    @property
    def DATABASE_URL(self) ->str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @computed_field
    @property
    def REDIS_URL(self) ->str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    RABBITMQ_URL:str
    RABBITMQ_USER:str
    RABBITMQ_PASSWORD:str

    model_config = SettingsConfigDict(env_file=".env")
    
settings = Settings()
