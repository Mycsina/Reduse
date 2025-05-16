"""Query logic for listings and analyzed listings."""

import json
import logging
import re

from backend.ai.prompts.listing_query import ListingQueryPrompt
from backend.ai.providers.factory import create_provider
from backend.schemas.filtering import ListingQuery
from backend.services.query import get_distinct_info_fields

logger = logging.getLogger(__name__)


async def process_natural_language_query(query_text: str) -> ListingQuery:
    """
    Process a natural language query into a structured ListingQuery.

    Args:
        query_text: The natural language query to process

    Returns:
        A structured ListingQuery object
    """
    # Get field metadata for AI context
    field_names = await get_distinct_info_fields()

    # Get AI provider and prepare prompt
    ai_provider = create_provider()
    prompt = ListingQueryPrompt()

    # Process the natural language query
    formatted_prompt = prompt.format(query_text, field_names)
    response = await ai_provider.generate_text(formatted_prompt)

    # Extract the JSON from the response
    try:
        # Find JSON block in the response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)

        if json_match:
            json_str = json_match.group(0)
        else:
            raise ValueError("No valid JSON found in AI response")

        # Parse the structured query
        structured_query_dict = json.loads(json_str)

        # Normalize filter type to uppercase
        if structured_query_dict.get("filter", {}).get("type"):
            structured_query_dict["filter"]["type"] = structured_query_dict["filter"][
                "type"
            ].upper()

        # Normalize operators to uppercase
        for condition in structured_query_dict.get("filter", {}).get("conditions", []):
            if isinstance(condition, dict) and "operator" in condition:
                condition["operator"] = condition["operator"].upper()

        structured_query = ListingQuery(**structured_query_dict)

    except (json.JSONDecodeError, ValueError) as e:
        # Handle parsing errors
        logger.error(f"Failed to parse AI response: {e}")
        logger.debug(f"Prompt: {formatted_prompt}")
        logger.debug(f"AI response: {response}")

        raise e

    return structured_query
