# flake8: noqa: E501

"""Product analysis prompt."""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.ai.prompts.base import Prompt


class ProductInfo(BaseModel):
    """Schema for product information."""

    type: str = Field(description="The type of product being offered")
    brand: str = Field(description="The name of the company or manufacturer")
    base_model: str = Field(description="The core product name/number before variants")
    model_variant: Optional[str] = Field(default=None, description="Specific version/edition of the base model")
    info: Dict[str, Any] = Field(
        default_factory=dict, description="Additional product details, using canonical field names where possible."
    )


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
Analyze the following product listing to identify and extract key product information. The listing includes a title, description, and potentially a structured 'parameters' dictionary.

General Guidelines:
1. Prioritize Structured Parameters:
   - If the 'parameters' field is present and contains relevant information, use it as context for the analysis, but don't repeat the values in the 'info' dictionary.
   - Use the title and description for context, broader information, and details not covered in 'parameters'.

2. Field Reuse and Canonical Names:
   - **Strictly check the 'Existing Fields' list below.**
   - **Reuse existing fields *exactly* when they match the semantic meaning.** Do not create minor variations (e.g., 'engine size' if 'engine_displacement' exists).
   - Only create new fields if no existing accurately represents the information.
   - Maintain consistent terminology across listings.

3. Extract Core Product Details:
   - Type: What kind of product is this? (e.g., car, laptop, bed frame, smartphone)
   - Brand: Who manufactured it?
   - Base Model: What's the main model name/number?
   - Model Variant: Any specific version/edition? (Combine trim, engine specs, etc. if appropriate, e.g., "320i xDrive", "M1 Pro")
   - Don't extract information specific to this exact listing, only general product information (skip: number_of_owners, ownership_since, include: gpu, ram, engine)

4. Additional Information ('info' dictionary):
   - Extract relevant information from title, description, and parameters that help evaluate and search for the product (specifications, features).
   - Organize related information logically using appropriate field names from 'Existing Fields'.

5. Data Quality and Normalization:
   - Use JSON `null` for fields that cannot be determined.
   - Be precise. Extract numerical values where possible (e.g., mileage as an integer `35000`, not "35,000 km").
   - Normalize common values:
     - Colors: Use lowercase (e.g., "alpine white", "black").
     - Condition: Use lowercase terms (e.g., "excellent", "good", "fair", "poor", "for parts").
     - Yes/No: Use boolean `true`/`false`.
   - Split comma-separated *string* values into lists only if they represent multiple distinct items (e.g., accessories, features). Do not split descriptive phrases.
   - Ensure extracted values match the expected data type or format implied by existing fields if possible.


Existing Fields:
{existing_fields}

Example 1 - Electronics (No Change):
Title: Used Apple MacBook Pro 16-inch with M1 Pro chip, 16GB RAM, 512GB SSD
Description: Excellent condition, barely used. Space Gray color. Comes with original charger.
Parameters: {{}}

Example Output 1:
{{
  "type": "laptop",
  "brand": "Apple",
  "base_model": "MacBook Pro",
  "model_variant": null,
  "info": {{
    "cpu": "M1 Pro",
    "screen_size": "16-inch",
    "ram": "16GB",
    "storage": "512GB SSD",
    "color": "space gray", // Normalized
    "condition": "excellent", // Normalized
  }}
}}

Example 2 - Automotive (Updated for Canonical Fields & Normalization):
Title: 2018 BMW 3 Series 320i xDrive Sedan
Description: Low mileage, one owner, no accidents reported. Premium package, navigation system, heated seats, sunroof. Alpine White exterior, Black Leather interior. Regularly serviced, records available. Winter tires included. 35,000 miles.
Parameters: {{ "Year": "2018", "Brand": "BMW", "Model": "320i", "Trim": "xDrive", "Mileage": "35000", "Exterior Color": "Alpine White", "Interior Color": "Black Leather" }}

Example Output 2:
{{
  "type": "car",
  "brand": "BMW", // Prioritized parameter "Brand"
  "base_model": "320i", // Prioritized parameter "Model"
  "model_variant": "xDrive", // Prioritized parameter "Trim"
  "info": {{
    "year": 2018, // Prioritized parameter "Year", converted to integer
    "body_type": "sedan", // Inferred from title
    "mileage": 35000, // Prioritized parameter "Mileage", converted to integer
    "exterior_color": "alpine white", // Prioritized parameter "Exterior Color", normalized
    "interior_color": "black", // Normalized from parameter "Interior Color" ('Black Leather' -> 'black')
    "interior_material": "leather", // Inferred material from parameter "Interior Color" ('Black Leather' -> 'leather')
    "ownership_history": "one owner", // Extracted from description
    "features": ["premium package", "navigation system", "heated seats", "sunroof", "winter tires included"] // Combined from description
  }}
}}

Example 3 - Furniture (Updated Normalization):
Title: IKEA MALM Bed Frame with Storage, Queen Size, Black-Brown
Description: 2 years old, good condition with minor scratches on one drawer. 4 storage drawers underneath. Mattress not included. Assembled but can be disassembled for transport. Dimensions: 209x156x100 cm. Pet-free and smoke-free home.
Parameters: {{ "Brand": "IKEA", "Product line": "MALM", "Size": "Queen", "Color": "Black-brown" }}

Example Output 3:
{{
  "type": "bed frame", // Inferred from title
  "brand": "IKEA", // Prioritized parameter "Brand"
  "base_model": "MALM", // Prioritized parameter "Product line"
  "model_variant": "Storage", // Inferred from title/description
  "info": {{
    "size": "Queen", // Prioritized parameter "Size"
    "color": "black-brown", // Prioritized parameter "Color" ('Black-brown'), normalized
    "condition": "good", // Extracted from description, normalized
    "dimensions": "209x156x100 cm", // Extracted from description
    // "age": "2 years", // Too uncertain, don't add
    // "features": ["storage drawers"], // Wasn't added as it is too specific
    // "drawer_count": 4, // Wasn't added as it is too specific

  }}
}}

Example 4 - Smartphone (Updated Normalization):
Title: Samsung Galaxy S22 Ultra 256GB Phantom Black Unlocked
Description: Purchased 6 months ago, perfect condition, no scratches or dents. All original accessories including charger, cable, and box. Screen protector and case applied since day one. Battery health at 98%. Factory unlocked, works with any carrier.
Parameters: {{ "Brand": "Samsung", "Model": "Galaxy S22 Ultra", "Storage Capacity": "256 GB", "Color": "Phantom Black", "Network": "Unlocked" }}

Example Output 4:
{{
  "type": "smartphone", // Inferred from title/model
  "brand": "Samsung", // Prioritized parameter "Brand"
  "base_model": "Galaxy S22", // Derived from parameter "Model"
  "model_variant": "Ultra", // Derived from parameter "Model"
  "info": {{
    "storage": "256GB", // Prioritized parameter "Storage Capacity" ('256 GB'), adjusted format
    "color": "phantom black", // Prioritized parameter "Color", normalized
    "network_lock": "unlocked", // Prioritized parameter "Network" ('Unlocked'), canonical name
    "age": "6 months", // Extracted from description
    "condition": "perfect", // Extracted from description, normalized
    "battery_health": "98%", // Extracted from description
    "accessories": ["original charger", "original cable", "original box", "screen protector", "case"] // Extracted from description
  }}
}}

Now analyze this listing:
{input}

---
REMINDER: Analyze listing (prioritize parameters). Extract Type, Brand, Base Model, Variant, & relevant 'info' using existing fields. Normalize values. Output valid JSON.
---
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

    def format(
        self,
        input_text: str,
        parameters: Optional[Dict[str, str]] = None,
        existing_fields: Optional[List[str]] = None,
    ) -> str:
        """Format the prompt with the input text, parameters, and existing fields.

        Args:
            input_text: The main input text (title + description) to analyze.
            parameters: Optional dictionary of structured parameters.
            existing_fields: List of existing field names to consider for reuse.
        """
        # Format existing fields as a bullet list
        formatted_fields = "No existing fields to consider."
        if existing_fields:
            formatted_fields = "\n".join([f"- {field}" for field in sorted(existing_fields)])

        # Format the input including parameters if they exist
        formatted_input = f"{input_text}"
        if parameters:
            formatted_parameters = json.dumps(parameters, indent=2)
            formatted_input += f"\nParameters:\n{formatted_parameters}"
        else:
            formatted_input += "\nParameters: {}"  # Indicate empty parameters

        return self.template.format(input=formatted_input, existing_fields=formatted_fields)


def create_product_analysis_prompt() -> ProductAnalysisPrompt:
    """Create a product analysis prompt.

    Returns:
        ProductAnalysisPrompt: Configured prompt template
    """
    return ProductAnalysisPrompt()
