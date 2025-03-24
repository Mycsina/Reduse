# flake8: noqa: E501

"""Product analysis prompt."""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import Prompt


class ProductInfo(BaseModel):
    """Schema for product information."""

    type: str = Field(description="The type of product being offered")
    brand: str = Field(description="The name of the company or manufacturer")
    base_model: str = Field(description="The core product name/number before variants")
    model_variant: Optional[str] = Field(default=None, description="Specific version/edition of the base model")
    info: Dict[str, Any] = Field(default_factory=dict, description="Additional product details")


class ProductAnalysisPrompt(Prompt):
    """Prompt for analyzing product listings."""

    def __init__(self):
        """Initialize the prompt."""
        system_prompt = (
            "You are an expert at analyzing product listings and extracting relevant information. "
            "You have deep knowledge of various product categories and can identify key details "
            "that matter to potential buyers."
        )

        template = """
Analyze the following product listing to identify and extract key information.

Guidelines:
1. Field Reuse:
   - First check the existing fields list below
   - Reuse existing fields when they match the semantic meaning
   - Only create new fields when necessary
   - Maintain consistent terminology across listings

2. Extract the core product details:
   - Type: What kind of product is this?
   - Brand: Who manufactured it?
   - Base Model: What's the main model name/number?
   - Model Variant: Any specific version/edition?

3. Additional Information:
   - Extract any details that would help someone evaluate this product
   - Include specifications, condition, features, etc.
   - Organize related information into logical groups
   - Use existing fields when possible

4. Data Quality:
   - Use "null" for fields that can't be determined
   - Be precise with technical specifications
   - Maintain original terminology where appropriate
   - Split comma-separated values into lists
   - Ensure values match the expected format of existing fields

Existing Fields:
{existing_fields}

Example 1 - Electronics:
Title: Used Apple MacBook Pro 16-inch with M1 Pro chip, 16GB RAM, 512GB SSD
Description: Excellent condition, barely used. Space Gray color. Comes with original charger.

Example Output 1:
{
  "type": "laptop",
  "brand": "Apple",
  "base_model": "MacBook Pro",
  "model_variant": "M1 Pro",
  "info": {
    "screen_size": "16-inch",
    "ram": "16GB",
    "storage": "512GB SSD",
    "color": "Space Gray",
    "condition": "excellent",
    "accessories": ["original charger"]
  }
}

Example 2 - Automotive:
Title: 2018 BMW 3 Series 320i xDrive Sedan
Description: Low mileage (35,000 miles), one owner, no accidents. Alpine White exterior with black leather interior. Features include premium package, navigation system, heated seats, and sunroof. Regularly serviced at BMW dealership, all maintenance records available. Winter tire set included.

Example Output 2:
{
  "type": "car",
  "brand": "BMW",
  "base_model": "3 Series",
  "model_variant": "320i xDrive",
  "info": {
    "year": "2018",
    "body_type": "Sedan",
    "mileage": "35,000 miles",
    "exterior_color": "Alpine White",
    "interior_color": "black",
    "interior_material": "leather",
    "ownership": "one owner",
    "accident_history": "none",
    "features": ["premium package", "navigation system", "heated seats", "sunroof"],
    "service_history": "dealer maintained",
    "includes": ["maintenance records", "winter tires"]
  }
}

Example 3 - Furniture:
Title: IKEA MALM Bed Frame with Storage, Queen Size, Black-Brown
Description: 2 years old, good condition with minor scratches on one drawer. 4 storage drawers underneath. Mattress not included. Assembled but can be disassembled for transport. Dimensions: 209x156x100 cm. Pet-free and smoke-free home.

Example Output 3:
{
  "type": "bed frame",
  "brand": "IKEA",
  "base_model": "MALM",
  "model_variant": "Storage",
  "info": {
    "size": "Queen",
    "color": "Black-Brown",
    "age": "2 years",
    "condition": "good",
    "features": ["storage drawers"],
    "drawer_count": "4",
    "damage": "minor scratches",
    "dimensions": "209x156x100 cm",
    "assembly_status": "assembled",
    "includes": ["disassembly available"],
    "excludes": ["mattress"],
    "environment": ["pet-free", "smoke-free"]
  }
}

Example 4 - Smartphone:
Title: Samsung Galaxy S22 Ultra 256GB Phantom Black Unlocked
Description: Purchased 6 months ago, perfect condition, no scratches or dents. All original accessories including charger, cable, and box. Screen protector and case applied since day one. Battery health at 98%. Factory unlocked, works with any carrier. Warranty valid until March 2023.

Example Output 4:
{
  "type": "smartphone",
  "brand": "Samsung",
  "base_model": "Galaxy S22",
  "model_variant": "Ultra",
  "info": {
    "storage": "256GB",
    "color": "Phantom Black",
    "carrier": "unlocked",
    "age": "6 months",
    "condition": "perfect",
    "cosmetic_condition": "no scratches or dents",
    "accessories": ["charger", "cable", "box", "screen protector", "case"],
    "battery_health": "98%",
    "warranty_status": "valid until March 2023"
  }
}

Now analyze this listing:
{input}
"""

        super().__init__(template=template, system_prompt=system_prompt)

    async def parse_output(self, output: str) -> ProductInfo:
        """Parse the model output into a structured format.

        Args:
            output: Raw model output string

        Returns:
            ProductInfo: Parsed product information
        """
        # Clean up the output to handle potential formatting issues
        output = output.strip()

        # Try to extract JSON content between triple backticks if present
        if "```json" in output:
            # Extract JSON between ```json and ``` markers
            start = output.find("```json") + 7
            end = output.find("```", start)
            if end > start:
                output = output[start:end].strip()
        elif "```" in output:
            # Extract JSON between ``` markers
            start = output.find("```") + 3
            end = output.find("```", start)
            if end > start:
                output = output[start:end].strip()

        try:
            data = json.loads(output)
            return ProductInfo(**data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON output: {e}")
        except Exception as e:
            raise ValueError(f"Failed to validate parsed data: {e}")

    def format(self, input: str, existing_fields: Optional[List[str]] = None) -> str:
        """Format the prompt with the input text and existing fields.

        Args:
            input: The input text to analyze
            existing_fields: List of existing field names to consider for reuse
        """
        # Format existing fields as a bullet list
        formatted_fields = "No existing fields to consider."
        if existing_fields:
            formatted_fields = "\n".join([f"- {field}" for field in sorted(existing_fields)])

        return self.template.format(input=input, existing_fields=formatted_fields)


def create_product_analysis_prompt() -> ProductAnalysisPrompt:
    """Create a product analysis prompt.

    Returns:
        ProductAnalysisPrompt: Configured prompt template
    """
    return ProductAnalysisPrompt()
