from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-2"
    gemini_embedding_dimensions: int = 768
    database_url: str = "postgresql+asyncpg://genquantaa:genquantaa@localhost:5432/genquantaa"
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
