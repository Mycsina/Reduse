"""Application-wide configuration settings."""

from pathlib import Path
from typing import Dict, Any
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Base paths
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"


class APISettings(BaseSettings):
    """API-related settings."""

    api_key: SecretStr = Field(default=..., env="API_KEY") # type: ignore
    cors_origins: list[str] = Field(default=["*"]) # type: ignore
    environment: str = Field(default="development", env="ENVIRONMENT") # type: ignore

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class DatabaseSettings(BaseSettings):
    """Database-related settings."""

    atlas_user: str = Field(..., env="ATLAS_USER") # type: ignore
    atlas_password: SecretStr = Field(..., env="ATLAS_PASSWORD") # type: ignore
    database_name: str = Field(default="Vroom")

    @property
    def uri(self) -> str:
        """Get the MongoDB connection URI."""
        return (
            f"mongodb+srv://{self.atlas_user}:{self.atlas_password.get_secret_value()}"
            f"@vroom.k7x4g.mongodb.net/?retryWrites=true&w=majority&appName=vroom"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class AISettings(BaseSettings):
    """AI-related settings."""

    gemini_api_key: SecretStr = Field(default="", env="GEMINI_API_KEY") # type: ignore
    openai_api_key: SecretStr = Field(default="", env="OPENAI_API_KEY") # type: ignore
    groq_api_key: SecretStr = Field(default="", env="GROQ_API_KEY") # type: ignore
    default_model: str = Field(default="gemini-2.0-flash-exp")
    rate_limits: Dict[str, int] = Field(
        default={
            "requests_per_minute": 60,
            "tokens_per_minute": 60000,
            "requests_per_day": 10000,
            "max_retries": 3,
        }
    )

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class ScraperSettings(BaseSettings):
    """Scraper-related settings."""

    max_concurrent_requests: int = Field(default=3)
    batch_size: Dict[str, int] = Field(
        default={
            "listings": 100,
            "details": 5,
        }
    )
    timeouts: Dict[str, int] = Field(
        default={
            "page_load": 30000,
            "cookie_consent": 5000,
            "content_load": 30000,
        }
    )
    retries: Dict[str, Any] = Field(
        default={
            "max_attempts": 3,
            "initial_delay": 2.0,
            "backoff_factor": 1.5,
        }
    )

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class LoggingSettings(BaseSettings):
    """Logging-related settings."""

    log_level: str = Field(default="INFO")
    file_max_bytes: int = Field(default=10 * 1024 * 1024)  # 10MB
    backup_count: int = Field(default=9)
    batch_size: int = Field(default=100)
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    noisy_loggers: Dict[str, str] = Field(
        default={
            "playwright": "WARNING",
            "urllib3": "WARNING",
            "uvicorn": "WARNING",
            "pymongo": "WARNING",
            "watchfiles": "WARNING",
            "grpclib": "WARNING",
        }
    )

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class Settings(BaseSettings):
    """Global settings container."""

    api: APISettings = Field(default_factory=APISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings) # type: ignore
    ai: AISettings = Field(default_factory=AISettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


# Create global settings instance
settings = Settings()

# Export individual configs for backward compatibility
API_CONFIG = settings.api.model_dump()
DB_CONFIG = settings.database.model_dump()
AI_CONFIG = settings.ai.model_dump()
SCRAPER_CONFIG = settings.scraper.model_dump()
LOGGING_CONFIG = settings.logging.model_dump()
