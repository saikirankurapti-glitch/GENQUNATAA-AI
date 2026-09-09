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
    bootstrap_admin_emails: str = ""
    bootstrap_cto_emails: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def bootstrap_admin_email_list(self) -> set[str]:
        return {x.strip().lower() for x in self.bootstrap_admin_emails.split(",") if x.strip()}

    @property
    def bootstrap_cto_email_list(self) -> set[str]:
        return {x.strip().lower() for x in self.bootstrap_cto_emails.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
