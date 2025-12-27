"""Application configuration."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic API
    anthropic_api_key: str

    # Cohere API (for embeddings and reranking)
    cohere_api_key: str = ""

    # API Authentication
    api_key: str

    # Database (optional for basic API functionality)
    database_url: str = ""
    supabase_url: str = ""
    supabase_key: str = ""

    # Redis (optional for basic API functionality)
    redis_url: str = ""

    # Celery (optional for basic API functionality)
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    # CORS: Set your Chrome extension ID after publishing to Web Store
    # Format: chrome-extension://YOUR_EXTENSION_ID
    allowed_origins: str = "https://ruh-api-948739110049.us-central1.run.app"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields like CLOUD_RUN_URL
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


# Global settings instance
settings = Settings()
