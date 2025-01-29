"""Base prompt management and configuration."""

from typing import Any, Dict

from ...config import settings


class BasePromptConfig:
    """Base configuration for prompts."""

    def __init__(
        self,
        model_name: str = settings.ai.default_model,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        system_prompt: str = "",
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for provider consumption."""
        return {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
        }


class BasePromptTemplate:
    """Base class for prompt templates."""

    def __init__(self, template: str, config: BasePromptConfig | None = None):
        self.template = template
        self.config = config or BasePromptConfig()

    def format(self, **kwargs) -> str:
        """Format the prompt template with the given parameters."""
        return self.template.format(**kwargs)

    def get_config(self) -> Dict[str, Any]:
        """Get the configuration for this prompt."""
        return self.config.to_dict()
