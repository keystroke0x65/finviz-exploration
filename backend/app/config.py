from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    finviz_api_token: str
    quote_cache_ttl_minutes: int = 15
    db_path: str = "finviz_dashboard.db"
    feeder_interval_minutes: int = 15
    watchlist_retention_days: int = 90
    is_feeder_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
