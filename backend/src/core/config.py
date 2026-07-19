from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str
    supabase_anon_key: str = ""
    supabase_jwt_secret: str

    anthropic_api_key: str
    voyage_api_key: str

    github_token: str = ""
    notion_token: str = ""

    token_encryption_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
