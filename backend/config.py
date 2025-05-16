"""Application-wide configuration settings."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables
load_dotenv(override=True)

# Base paths
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"


class PROVIDER_TYPE(Enum):
    GOOGLE = "google"
    GROQ = "groq"


class APISettings(BaseSettings):
    """API-related settings."""

    api_key: SecretStr = Field(default=..., validation_alias="API_KEY")
    cors_origins: list[str] = Field(default=["*"])
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class DatabaseSettings(BaseSettings):
    """Database-related settings."""

    mongodb_uri: Optional[str] = Field(default=None, validation_alias="MONGODB_URI")
    atlas_user: str = Field(validation_alias="ATLAS_USER")
    atlas_password: SecretStr = Field(..., validation_alias="ATLAS_PASSWORD")
    database_name: str = Field(default="Vroom")

    @property
    def uri(self) -> str:
        """Get the MongoDB connection URI."""
        # Use explicit MONGODB_URI if provided
        if self.mongodb_uri:
            return self.mongodb_uri

        # Otherwise construct from components
        return (
            f"mongodb+srv://{self.atlas_user}:{self.atlas_password.get_secret_value()}"
            f"@vroom.k7x4g.mongodb.net/?retryWrites=true&w=majority&appName=vroom"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class AISettings(BaseSettings):
    """AI-related settings."""

    google_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GOOGLE_API_KEY")
    openai_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="OPENAI_API_KEY")
    groq_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GROQ_API_KEY")
    default_provider: PROVIDER_TYPE = Field(default=PROVIDER_TYPE.GOOGLE)  # Default to the composite provider
    default_model: str = Field(default="gemma-3-27b-it", validation_alias="AI_DEFAULT_MODEL")
    google_project_id: str = Field(default="", validation_alias="GOOGLE_PROJECT_ID")
    google_location: str = Field(default="us-central1", validation_alias="GOOGLE_LOCATION")

    # Concurrency settings
    analysis_max_concurrent: int = Field(default=10, validation_alias="AI_ANALYSIS_MAX_CONCURRENT")
    embedding_max_concurrent: int = Field(default=10, validation_alias="AI_EMBEDDING_MAX_CONCURRENT")

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class CrawlerSettings(BaseSettings):
    """Scraper-related settings."""

    max_concurrent_requests: int = Field(default=3, validation_alias="MAX_CONCURRENT_REQUESTS")
    time_before_recrawl: int = Field(default=1, validation_alias="TIME_BEFORE_RECRAWL")

    class Timeouts:
        page_load: int = 30000
        cookie_consent: int = 5000
        content_load: int = 30000

    timeouts: Timeouts = Field(default=Timeouts())

    class Retries:
        max_attempts: int = 3
        initial_delay: float = 2.0
        backoff_factor: float = 1.5

    retries: Retries = Field(default=Retries())

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


class LoggingSettings(BaseSettings):
    """Logging-related settings."""

    log_level: str = Field(default="INFO")
    file_log_level: str = Field(default="DEBUG")
    file_max_bytes: int = Field(default=10 * 1024 * 1024)  # 10MB
    backup_count: int = Field(default=9)
    batch_size: int = Field(default=100)
    format: str = Field(default="%(name)s - %(levelname)s - %(message)s")
    file_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    enable_endpoint_logging: bool = Field(default=False, validation_alias="ENABLE_ENDPOINT_LOGGING")
    noisy_loggers: Dict[str, str] = Field(
        default={
            "playwright": "WARNING",
            "urllib3": "WARNING",
            "uvicorn": "WARNING",
            "pymongo": "WARNING",
            "watchfiles": "WARNING",
            "grpclib": "WARNING",
            "pymongo.topology": "WARNING",  # Suppress MongoDB topology logs
            "pymongo.server": "WARNING",  # Suppress MongoDB server logs
            "pymongo.connection": "WARNING",  # Suppress MongoDB connection logs
            "pymongo.monitoring": "WARNING",  # Suppress MongoDB monitoring logs
            "sse_starlette": "WARNING",  # Suppress all SSE-related logs
            "sse_starlette.sse": "WARNING",  # Suppress specific SSE debug logs
            "watchfiles.main": "WARNING",  # Suppress watchfiles logs
            "crawlee": "WARNING",
            "numba": "WARNING",
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


class Settings(BaseSettings):
    """Global settings container."""

    api: APISettings = Field(default_factory=APISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore
    ai: AISettings = Field(default_factory=AISettings)
    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    AUTH_SECRET_KEY: str = Field(default="", validation_alias="AUTH_SECRET_KEY")

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


# Create global settings instance
settings = Settings()
