from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    finviz_api_token: str
    quote_cache_ttl_minutes: int = 15
    db_path: str = "finviz_dashboard.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
