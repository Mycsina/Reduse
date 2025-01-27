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

    api_key: SecretStr = Field(default=..., env="API_KEY")  # type: ignore
    cors_origins: list[str] = Field(default=["*"])  # type: ignore
    environment: str = Field(default="development", env="ENVIRONMENT")  # type: ignore

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class DatabaseSettings(BaseSettings):
    """Database-related settings."""

    atlas_user: str = Field(..., env="ATLAS_USER")  # type: ignore
    atlas_password: SecretStr = Field(..., env="ATLAS_PASSWORD")  # type: ignore
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

    gemini_api_key: SecretStr = Field(default="", env="GEMINI_API_KEY")  # type: ignore
    openai_api_key: SecretStr = Field(default="", env="OPENAI_API_KEY")  # type: ignore
    groq_api_key: SecretStr = Field(default="", env="GROQ_API_KEY")  # type: ignore
    default_model: str = Field(default="gemini-2.0-flash-exp")
    rate_limits: Dict[str, int] = Field(
        default={
            "requests_per_minute": 60,
            "tokens_per_minute": 60000,
            "requests_per_day": 10000,
            "max_retries": 3,
        }
    )
    google_project_id: str = Field(default="", env="GOOGLE_PROJECT_ID")  # type: ignore
    google_location: str = Field(default="us-central1", env="GOOGLE_LOCATION")  # type: ignore

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class ScraperSettings(BaseSettings):
    """Scraper-related settings."""

    max_concurrent_requests: int = Field(default=3, env="MAX_CONCURRENT_REQUESTS")  # type: ignore
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
    file_log_level: str = Field(default="DEBUG")
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


class SchedulerSettings(BaseSettings):
    """Scheduler-related settings."""

    collection: str = Field(default="scheduled_jobs")
    timezone: str = Field(default="UTC")
    job_defaults: Dict[str, Any] = Field(
        default={
            "coalesce": True,  # Combine multiple pending executions of the same job into one
            "max_instances": 1,  # Only allow one instance of each job to run at a time
            "misfire_grace_time": 60,  # Allow jobs to be 60 seconds late
        }
    )
    executors: Dict[str, Dict[str, Any]] = Field(
        default={"default": {"class": "apscheduler.executors.asyncio:AsyncIOExecutor"}}
    )

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class EbaySettings(BaseSettings):
    """eBay API settings."""

    app_id: SecretStr = Field(default="", env="EBAY_APP_ID")  # type: ignore
    cert_id: SecretStr = Field(default="", env="EBAY_CERT_ID")  # type: ignore
    app_credentials: SecretStr = Field(default="", env="EBAY_APP_CREDENTIALS")  # type: ignore
    marketplace_id: str = Field(default="EBAY_PT", env="EBAY_MARKETPLACE_ID")  # type: ignore
    campaign_id: str = Field(default="", env="EBAY_CAMPAIGN_ID")  # type: ignore
    max_items_per_page: int = Field(default=100)
    max_pages: int = Field(default=10)  # Maximum number of pages to fetch

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class Settings(BaseSettings):
    """Global settings container."""

    api: APISettings = Field(default_factory=APISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore
    ai: AISettings = Field(default_factory=AISettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    ebay: EbaySettings = Field(default_factory=EbaySettings)  # type: ignore

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


# Create global settings instance
settings = Settings()
