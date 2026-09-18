"""OSINT Nexus Backend — Core Configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "OSINT Nexus"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "osintnexus"
    POSTGRES_PASSWORD: str = "osintnexus_dev"
    POSTGRES_DB: str = "osintnexus"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # API Keys (Optional)
    LLM_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENCODE_API_KEY: str = ""

    # Supported providers: nvidia, openai, anthropic, ollama, none
    # When "none" or empty, AI planner/analyzer return deterministic defaults.
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = ""
    LLM_BASE_URL: str = ""
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.3

    # Collector Configuration
    DNS_TIMEOUT: int = 10
    WHOIS_TIMEOUT: int = 15
    HTTP_TIMEOUT: int = 30
    CT_TIMEOUT: int = 30
    GITHUB_TIMEOUT: int = 15

    # Search Provider Configuration
    SEARXNG_BASE_URL: str = ""  # e.g. "http://searxng:8080"
    SEARXNG_ENABLED: bool = True  # Enable SearXNG when base URL is set
    SEARCH_PROVIDER_TIMEOUT: float = 10.0  # Per-provider timeout (seconds)
    SEARCH_MAX_RESULTS_PER_PROVIDER: int = 40  # Max results per provider

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
