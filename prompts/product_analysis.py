# flake8: noqa: E501

"""Product analysis prompt configuration."""

import os

from ..ai.base import AIModel
from ..ai.google_provider import GoogleAIProvider

PROMPT_TEMPLATE = """Analyze the following product listing to identify and extract the **Brand, Model, and Variant** of the product being offered, as well as any other **additional information** that might be relevant to someone choosing this specific listing.

**Definitions:**

* **Brand:** The name of the company or manufacturer of the product.
* **Model:** The specific name or number assigned to a product line.
* **Variant:** The specific **configuration or trim level**.
    * **For Laptops:** Typically includes the **CPU and GPU configuration**.
    * **For Cars:** Refers to the **trim level**.
* **Additional Information:** Other details useful for a potential buyer.

**Instructions:**

1. Carefully read the product listing.
2. Identify the **Brand**, **Model**, and **Variant**.
3. Extract any **Additional Information**.
4. If Brand, Model, or Variant is missing, use "null".
5. Return the extracted information in a JSON object.

**Examples:**

**Input Listing:** Used Apple MacBook Pro 16-inch with M1 Pro chip, 16GB RAM, 512GB SSD, excellent condition.
**Output JSON:**
```json
{
  "brand": "Apple",
  "model": "MacBook Pro",
  "variant": "M1 Pro",
  "info": {
    "condition": "excellent",
    "ram": "16GB",
    "storage": "512GB SSD",
    "screen_size": "16-inch"
  }
}
```

**Input Listing:** Selling a Dell XPS 13 with Intel Core i7, NVIDIA GeForce MX550, 1TB SSD, touchscreen, includes charger.
**Output JSON:**
```json
{
  "brand": "Dell",
  "model": "XPS 13",
  "variant": "Intel Core i7, NVIDIA GeForce MX550",
  "info": {
    "storage": "1TB SSD",
    "features": "touchscreen",
    "included_accessories": "charger"
  }
}
```

**Input Listing:** 2024 Ford Mustang GT, 10,000 miles, 5.0L V8, 6-speed manual, black exterior, red interior, includes original owner's manual.
**Output JSON:**
```json
{
  "brand": "Ford",
  "model": "Mustang GT",
  "variant": "5.0L V8, 6-speed manual",
  "info": {
    "mileage": "10,000 miles",
    "color": "black exterior, red interior",
    "included_accessories": "original owner's manual"
  }
}
```

**Input Listing:** Samsung Galaxy S23 Ultra 256GB Phantom Black - Unlocked
**Output JSON:**
```json
{
  "brand": "Samsung",
  "model": "Galaxy S23 Ultra",
  "variant": "256GB Phantom Black",
  "info": {
    "condition": "Used",  // Assuming "Used" is implied if not stated otherwise
    "network_lock": "Unlocked"
  }
}
```

**Input Listing:**
{input}

**Return the JSON object:**
"""


def get_model_instance() -> AIModel:
    """Get the model configuration for product analysis."""
    return AIModel(
        name="gemini-2.0-flash-exp",
        provider=GoogleAIProvider(api_key=os.getenv("GOOGLE_API_KEY") or ""),
        temperature=0.1,  # Low temperature for consistent, factual responses
        max_tokens=8192,
        prompt_template=PROMPT_TEMPLATE,
    )
