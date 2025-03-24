"""Base prompt class."""

from typing import Any, Dict, List, Tuple


class Prompt:
    """Base class for all prompts."""

    def __init__(self, template: str, system_prompt: str):
        """Initialize the prompt.

        Args:
            template: The prompt template string
            system_prompt: The system prompt
        """
        self.template = template
        self.system_prompt = system_prompt

    def format(self, **kwargs: Any) -> str:
        """Format the prompt template with variables.

        Args:
            **kwargs: Variables to format the template with

        Returns:
            str: The formatted prompt
        """
        return self.template.format(**kwargs)

    def to_messages(self, **kwargs: Any) -> List[Dict[str, str]]:
        """Convert the template to a list of messages.

        Args:
            **kwargs: Variables to format the template with

        Returns:
            List[Dict[str, str]]: List of message dictionaries
        """
        formatted_user_message = self.format(**kwargs)
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": formatted_user_message},
        ]
