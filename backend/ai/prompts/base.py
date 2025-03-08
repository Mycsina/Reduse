"""Base prompt configuration and templates."""

from typing import Any, Dict, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field


class BasePromptConfig(BaseModel):
    """Base configuration for prompts."""

    model_name: str
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    system_prompt: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


class BasePromptTemplate:
    """Base template for prompts with LangChain integration."""

    def __init__(self, template: str, config: BasePromptConfig):
        """Initialize the prompt template.

        Args:
            template: The prompt template string
            config: Prompt configuration
        """
        self.template = template
        self.config = config
        self._langchain_template = ChatPromptTemplate.from_messages(
            [("system", config.system_prompt), ("human", template)]
        )

    def format(self, **kwargs: Any) -> str:
        """Format the prompt template with variables.

        Args:
            **kwargs: Variables to format the template with

        Returns:
            str: The formatted prompt
        """
        return self.template.format(**kwargs)

    def to_langchain(self) -> ChatPromptTemplate:
        """Get the LangChain prompt template.

        Returns:
            ChatPromptTemplate: The LangChain prompt template
        """
        return self._langchain_template

    def get_config(self) -> Dict[str, Any]:
        """Get the prompt configuration.

        Returns:
            dict: The prompt configuration
        """
        return self.config.to_dict()
