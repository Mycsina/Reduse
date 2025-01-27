# flake8: noqa: E501

"""Product analysis prompt configuration."""

import os

from ..ai.base import AIModel
from ..ai.providers.google import GoogleAIProvider

PROMPT_TEMPLATE = """
You are an expert at analyzing product listings and extracting the relevant information. You can use your deep product knowledge to determine what fields are relevant to extract.
Analyze the following product listing to identify and extract the **Type, Brand, Base Model, and Model Variant** of the product being offered, as well as any other **additional information** that might be relevant to someone choosing this specific listing.

**Definitions:**

* **Type:** The type of product being offered.
* **Brand:** The name of the company or manufacturer of the product.
* **Base Model:** The core product name/number before variants (e.g., "RTX 3070")
* **Model Variant:** Specific version/edition of the base model (e.g., "OC", "Founders Edition")
* **Additional Information:** Other details useful for a potential buyer.

**Instructions:**

1. Carefully read the product listing.
2. Use your deep product knowledge to determine what information is relevant to extract.
3. Identify the **Type**, **Brand**, **Base Model**, and **Model Variant**.
4. Extract any **Additional Information**.
5. When in doubt, use "null" for fields that can't be determined.
6. Return the extracted information in a JSON object.
7. If there is more than one listing, return a list of JSON objects.

**Examples:**

**Input Listing:** Used Apple MacBook Pro 16-inch with M1 Pro chip, 16GB RAM, 512GB SSD, excellent condition.
**Output JSON:**
{
  "type": "laptop",
  "brand": "Apple",
  "base_model": "MacBook Pro",
  "model_variant": "null",
  "info": {
    "cpu": "M1 Pro",
    "ram": "16GB",
    "storage": "512GB SSD",
    "screen_size": "16-inch",
    "condition": "excellent"
  }
}
**Note:** In the above example, the model variant is "null" because the full model name is MacBook Pro.

**Input Listing:** Selling a Dell XPS 13 with Intel Core i7, NVIDIA GeForce MX550, 1TB SSD, touchscreen, includes charger.
**Output JSON:**
{
  "type": "laptop",
  "brand": "Dell",
  "base_model": "XPS 13",
  "model_variant": "null",
  "info": {
    "cpu": "Intel Core i7",
    "gpu": "NVIDIA GeForce MX550",
    "storage": "1TB SSD",
    "features": "touchscreen",
    "accessories": "charger"
  }
}
**Note:** In the above example, the model variant is "null" because the full model name is XPS 13.

**Input Listing:** 2024 Ford Mustang GT, 10,000 miles, 5.0L V8, 6-speed manual, black exterior, red interior, includes original owner's manual.
**Output JSON:**
{
  "type": "car",
  "brand": "Ford",
  "base_model": "Mustang GT",
  "model_variant": "null",
  "info": {
    "mileage": "10,000 miles",
    "engine": "5.0L V8",
    "transmission": "6-speed manual",
    "color": "black exterior, red interior",
    "accessories": "original owner's manual"
  }
}
**Note:** In the above example, the model variant is "null" because the full model name is Mustang GT.

**Input Listing:** Samsung Galaxy S23 Ultra 256GB Phantom Black - Unlocked
**Output JSON:**
{
  "type": "smartphone",
  "brand": "Samsung",
  "base_model": "Galaxy S23 Ultra",
  "model_variant": "null",
  "info": {
    "storage": "256GB",
    "color": "Phantom Black",
    "condition": "Used",
    "network_lock": "Unlocked"
  }
}
**Note:** In the above example, the model variant is "null" because the full model name is Galaxy S23 Ultra.

**Input Listing:** ASUS RTX 3070 OC 8GB GDDR6X, 100% brand new, never used, in original packaging.
**Output JSON:**
{
  "type": "gpu",
  "brand": "ASUS",
  "base_model": "RTX 3070",
  "model_variant": "OC",
  "info": {
    "condition": "100% brand new, never used, in original packaging",
    "memory": "8GB",
    "memory_type": "GDDR6X"
  }
}

**Input Listing:** ASUS ROG Zephyrus G14 GA401QM, 16GB RAM, 1TB SSD, 16:10 aspect ratio, 1080p display, 165Hz refresh rate, 100% brand new, never used, in original packaging.
**Output JSON:**
{
  "type": "laptop",
  "brand": "ASUS",
  "base_model": "Zephyrus G14",
  "model_variant": "GA401QM",
  "info": {
    "ram": "16GB",
    "storage": "1TB SSD",
    "screen_size": "16:10 aspect ratio",
    "display": "1080p",
    "refresh_rate": "165Hz",
    "condition": "100% brand new, never used, in original packaging"
  }
}
**Note:** In the above example, the base model is "Zephyrus G14" and the model variant is "GA401QM". ROG is a sub-brand of ASUS, so not relevant to the base model.

**Input Listing:** Selling fishing rod and reel
**Output JSON:**
{
  "type": "null",
  "brand": "null",
  "base_model": "null",
  "model_variant": "null",
  "info": {
    "item": ["fishing rod", "reel"]
  }
}
**Note:** In the above example, the type is "null" because the listing is not a product.

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
