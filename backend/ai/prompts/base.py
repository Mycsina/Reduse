"""Base prompt configuration and templates."""

from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field


class BasePromptConfig(BaseModel):
    """Base configuration for prompts."""

    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    system_prompt: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt
        }


# Define message types for clarity
Message = Tuple[str, str]  # (role, content)
MessageList = List[Message]


class BasePromptTemplate:
    """Base template for prompts."""

    def __init__(self, template: str, config: BasePromptConfig):
        """Initialize the prompt template.

        Args:
            template: The prompt template string
            config: Prompt configuration
        """
        self.template = template
        self.config = config

    def format(self, **kwargs: Any) -> str:
        """Format the prompt template with variables.

        Args:
            **kwargs: Variables to format the template with

        Returns:
            str: The formatted prompt
        """
        return self.template.format(**kwargs)

    def to_messages(self, **kwargs: Any) -> MessageList:
        """Convert the template to a list of messages.

        Args:
            **kwargs: Variables to format the template with

        Returns:
            MessageList: List of (role, content) tuples
        """
        formatted_user_message = self.format(**kwargs)
        return [("system", self.config.system_prompt), ("user", formatted_user_message)]

    def get_config(self) -> Dict[str, Any]:
        """Get the prompt configuration.

        Returns:
            dict: The prompt configuration
        """
        return self.config.to_dict()
