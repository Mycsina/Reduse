"""Prompt for converting natural language queries to structured ListingQuery objects."""

from typing import Any, Dict, List

from backend.ai.prompts.base import Prompt


class ListingQueryPrompt(Prompt):
    """Prompt for converting natural language queries to structured ListingQuery objects."""

    def __init__(self):
        """Initialize the prompt."""
        system_prompt = """You are an AI assistant that converts natural language queries into structured JSON objects for database filtering. 
Your job is to extract search criteria from user queries and format them into a structured ListingQuery JSON object.
Never include any explanations, code, or markdown formatting in your response - only return the raw JSON object."""

        template = """
User query: "{query}"

AVAILABLE FIELDS:
{available_fields}

TASK:
Convert the user query into a structured JSON object that can be used to filter a database of listings.

OUTPUT FORMAT:
Return a valid JSON object with these possible top-level fields:
- "price": {{ "min": number | null, "max": number | null }} (Extract numeric price ranges)
- "search_text": string | null (For general keyword searches across title/description)
- "filter": {{ 
    "type": "AND" | "OR",
    "conditions": [
      {{ "field": string, "operator": string, "value": string }} | {{ "type": "AND" | "OR", "conditions": [...] }} (Nested groups)
    ]
  }} | null

Only include fields mentioned or implied in the query. Use the "filter" field for specific field-based conditions.

OPERATORS:
- "EQ": Case-insensitive exact string match (e.g., color = 'red').
- "CONTAINS": Case-insensitive substring match (e.g., description contains 'ocean view').
- "REGEX": Case-insensitive regex match (use if the user provides a pattern).
- "EQ_NUM": Numeric equality (e.g., bedrooms = 3).
- "GT": Numeric greater than (e.g., price > 1000).
- "LT": Numeric less than (e.g., mileage < 50000).
- "GTE": Numeric greater than or equal (e.g., year >= 2020).
- "LTE": Numeric less than or equal (e.g., size <= 1500).

GUIDELINES:
- Use `price` for explicit price range queries (e.g., "between $100k and $200k", "under $50k", "over $1M").
- Use `search_text` for general keywords not tied to a specific field (e.g., "waterfront property", "reliable sedan").
- Use `filter` for conditions on specific `AVAILABLE FIELDS`.
- Choose the most appropriate operator. Prefer specific numeric operators (`EQ_NUM`, `GT`, `LT`, etc.) for numeric fields.
- Use `CONTAINS` for partial text matches on string fields.
- Use `EQ` for exact matches on string fields (like categories, specific model names if appropriate).
- Handle numeric values correctly (extract numbers from text like "$500,000" -> 500000).
- If a query implies a range on a specific field (not price), use two conditions (e.g., "year between 2018 and 2020" -> year gte 2018 AND year lte 2020).

EXAMPLES:

Query: "Apartments under $500,000 with at least 2 bedrooms"
{{ 
  "price": {{ "min": null, "max": 500000 }},
  "search_text": null,
  "filter": {{ 
    "type": "AND", 
    "conditions": [
      {{ "field": "bedrooms", "operator": "GTE", "value": 2 }}
    ]
  }}
}}

Query: "Show me red cars or blue trucks"
{{ 
  "price": null,
  "search_text": null,
  "filter": {{
    "type": "OR",
    "conditions": [
      {{ 
        "type": "AND",
        "conditions": [
            {{ "field": "color", "operator": "EQ", "value": "red" }},
            {{ "field": "type", "operator": "EQ", "value": "car" }}
        ]
      }},
      {{ 
        "type": "AND",
        "conditions": [
            {{ "field": "color", "operator": "EQ", "value": "blue" }},
            {{ "field": "type", "operator": "EQ", "value": "truck" }}
        ]
      }}
    ]
  }}
}}

Query: "Find listings mentioning 'hardwood floors' with a price over 1,000,000"
{{ 
  "price": {{ "min": 1000000, "max": null }},
  "search_text": null,
  "filter": {{
    "type": "AND",
    "conditions": [
        {{ "field": "description", "operator": "CONTAINS", "value": "hardwood floors" }}
    ]
  }}
}}

Query: "Vehicles from 2020 or newer with less than 30,000 miles"
{{
  "price": null,
  "search_text": null,
  "filter": {{
    "type": "AND",
    "conditions": [
      {{ "field": "year", "operator": "GTE", "value": 2020 }},
      {{ "field": "mileage", "operator": "LT", "value": 30000 }}
    ]
  }}
}}


YOUR RESPONSE (JSON only):

---
REMINDER: Convert query to structured JSON filter using available fields and the specified format/operators. Output JSON only.
---
"""

        super().__init__(template=template, system_prompt=system_prompt)

    def format(self, query: str, available_fields: List[str]) -> str:
        """Format the prompt with the query and available fields."""
        formatted_fields = "\n".join([f"- {field}" for field in available_fields])
        return self.template.format(query=query, available_fields=formatted_fields)


def create_listing_query_prompt() -> ListingQueryPrompt:
    """Create a listing query prompt."""
    return ListingQueryPrompt()
