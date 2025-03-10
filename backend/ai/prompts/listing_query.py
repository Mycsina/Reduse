"""Prompt for converting natural language queries to structured ListingQuery objects."""

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.routers.query.listings import ListingQuery

from .base import BasePromptConfig, BasePromptTemplate


class ListingQueryConfig(BasePromptConfig):
    """Configuration for the listing query prompt."""

    def __init__(self):
        """Initialize with default configuration."""
        system_prompt = """You are an AI assistant that converts natural language queries into structured JSON objects for database filtering. 
Your job is to extract search criteria from user queries and format them into a structured ListingQuery JSON object.
Never include any explanations, code, or markdown formatting in your response - only return the raw JSON object."""

        super().__init__(
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=500,  # Reduced to optimize for cheaper models
        )


class ListingQueryPrompt(BasePromptTemplate):
    """Prompt for converting natural language queries to structured ListingQuery objects."""

    template = """
User query: "{query}"

AVAILABLE FIELDS:
{available_fields}

TASK:
Convert the user query into a structured JSON object that can be used to filter a database of listings.

OUTPUT FORMAT:
Return a valid JSON object with these possible fields:
- "price": {{ "min": number or null, "max": number or null }}
- "search_text": string or null
- "filter": {{ 
    "operator": "and" or "or", 
    "conditions": [
      {{ "field": string, "operator": string, "value": any }}
    ]
  }}

Only include fields mentioned or implied in the query.
Operators can be: "eq" (equals), "lt" (less than), "gt" (greater than), "lte" (less than or equal), "gte" (greater than or equal).

EXAMPLES:

Query: "Apartments under $500,000 with at least 2 bedrooms"
{{
  "price": {{
    "max": 500000
  }},
  "filter": {{
    "operator": "and",
    "conditions": [
      {{
        "field": "bedrooms",
        "operator": "gte",
        "value": 2
      }}
    ]
  }}
}}

Query: "Red cars with low mileage from 2018 or newer"
{{
  "filter": {{
    "operator": "and",
    "conditions": [
      {{
        "field": "color",
        "operator": "eq",
        "value": "red"
      }},
      {{
        "field": "year",
        "operator": "gte",
        "value": 2018
      }},
      {{
        "field": "mileage",
        "operator": "lte",
        "value": 50000
      }}
    ]
  }}
}}

YOUR RESPONSE (JSON only):
"""

    def __init__(self):
        """Initialize the prompt with default configuration."""
        super().__init__(template=self.template, config=ListingQueryConfig())

    def format(self, query: str, available_fields: List[str]) -> str:
        """Format the prompt with the query and available fields."""

        # Format fields as a simple bullet list
        formatted_fields = "\n".join([f"- {field}" for field in available_fields])

        return self.template.format(query=query, available_fields=formatted_fields)

    def to_messages(self, **kwargs: Any) -> List[Dict[str, str]]:
        """Convert the template to a list of messages for AI providers."""
        formatted_user_message = self.format(**kwargs)
        return [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": formatted_user_message},
        ]


def create_listing_query_prompt() -> ListingQueryPrompt:
    """Create a listing query prompt."""
    return ListingQueryPrompt()
