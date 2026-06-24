# config.py file, contains security objects

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
class Settings(BaseSettings):

    GROQ_API_KEY:str
    GROQ_MODEL:str
    NEWS_API_KEY:str
    OPENROUTER_API_KEY:str
    OPENROUTER_MODEL:str
    TELEGRAM_BOT_TOKEN:str
    TELEGRAM_CHAT_ID:str

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB:str
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

    RABBITMQ_USER:str
    RABBITMQ_PASSWORD:str
    RABBITMQ_HOST:str = "localhost"
    RABBITMQ_PORT:int = 5672

    @computed_field
    @property
    def RABBITMQ_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    model_config = SettingsConfigDict(env_file=".env")
    
settings = Settings()
