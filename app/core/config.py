# app/core/config.py

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "InDepthRag"
    # Database
    database_url: str


    access_token_expire_minutes: int = 60
    secret_key:str
    algorithm:str = "HS256"
    debug: bool = True
    refresh_token_expire_days: int = 30


    # Future RAG settings
    # embedding_model: str = "default"
    # llm_model: str = "default"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
