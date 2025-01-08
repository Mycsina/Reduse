# flake8: noqa: E501

from ..ai.base import AIModel

PROMPT_TEMPLATE = """Analyze the following product listing to identify and extract the **Brand, Model, and Variant** of the product being offered, as well as any other **additional information** that might be relevant to someone choosing this specific listing.

**Definitions:**

* **Brand:** The name of the company or manufacturer of the product (e.g., Apple, Samsung, Dell, Ford).
* **Model:** The specific name or number assigned to a product line or individual product by the brand (e.g., MacBook Pro, Galaxy S23, Focus, Mustang).
* **Variant:** The specific **configuration or trim level** of the product that differentiates it based on key internal components or feature packages.
    * **For Laptops:** This typically includes the **CPU and GPU configuration** (e.g., "Intel Core i7, NVIDIA GeForce RTX 3060").
    * **For Cars:** This refers to the **trim level** (e.g., "LX", "EX", "Limited", "GT").
* **Additional Information:** Any other details present in the listing that could help a potential buyer make a decision about this *specific* item. This might include:
    * **Condition:** (e.g., "Used - Excellent", "New in Box", "Like New")
    * **Specifications not included in the Variant:** (e.g., RAM amount, storage capacity, screen size for laptops; mileage, year of manufacture for cars)
    * **Features:** (e.g., "Touchscreen", "4WD", "Leather Seats")
    * **Included Accessories:** (e.g., "With original box and charger", "Includes spare battery")
    * **Color:** (if not part of the variant)
    * **Warranty Information:**
    * **Other relevant details:**

**Instructions:**

1. Carefully read the product listing provided below.
2. Identify the **Brand**, **Model**, and the specific **Variant** (configuration or trim level) of the product.
3. Extract any **Additional Information** that is presented in the listing and would be useful for a potential buyer.
4. If any of the Brand, Model, or Variant information is not explicitly stated, use "null" as the value.
5. Return the extracted information in a JSON object with the following structure:

```json
{
  "brand": "Product Brand",
  "model": "Product Model",
  "variant": "Specific Configuration or Trim Level",
  "info": {
    "key1": "value1",
    "key2": "value2",
    // ... other relevant information
  }
}

Product Listing:
{input}

Return the JSON object:
"""


def get_model_instance() -> AIModel:
    """Get the model configuration for product categorization."""
    return AIModel(
        model_name="gemini-2.0-flash-exp",
        temperature=0.1,  # Low temperature for consistent, factual responses
        max_tokens=500,  # Plenty for our JSON response
        prompt_template=PROMPT_TEMPLATE,
    )
