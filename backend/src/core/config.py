from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str
    supabase_anon_key: str = ""
    supabase_jwt_secret: str

    groq_api_key: str
    voyage_api_key: str

    github_token: str = ""
    notion_token: str = ""

    token_encryption_key: str

    # Comma-separated. Defaults to the local frontend dev server; update (or
    # override via env) once deployed to Vercel with a real domain.
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
