# flake8: noqa: E501

"""Product analysis prompt configuration."""

from typing import Any, Dict

from ...config import settings
from .base import BasePromptConfig, BasePromptTemplate


class ProductAnalysisConfig(BasePromptConfig):
    """Configuration for product analysis prompts."""

    def __init__(self):
        super().__init__(
            model_name=settings.ai.default_model,
            temperature=0.1,  # Low temperature for consistent, factual responses
            max_tokens=8192,
            system_prompt="You are an expert at analyzing product listings and extracting the relevant information.",
        )


class ProductAnalysisTemplate(BasePromptTemplate):
    """Template for product analysis prompts."""

    def __init__(self):
        template = """
You can use your deep product knowledge to determine what fields are relevant to extract.
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

**Input Listing:** {input}
**Return the JSON object:**"""
        super().__init__(template=template, config=ProductAnalysisConfig())


def create_product_analysis_prompt() -> BasePromptTemplate:
    """Create a product analysis prompt."""
    return ProductAnalysisTemplate()
