# flake8: noqa: E501

"""Product analysis prompt configuration."""

from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

from ...config import settings
from .base import BasePromptConfig, BasePromptTemplate


class ProductInfo(BaseModel):
    """Schema for product information."""

    type: str = Field(description="The type of product being offered")
    brand: str = Field(description="The name of the company or manufacturer")
    base_model: str = Field(description="The core product name/number before variants")
    model_variant: Optional[str] = Field(default=None, description="Specific version/edition of the base model")
    info: Dict[str, Any] = Field(default_factory=dict, description="Additional product details")


class ProductAnalysisConfig(BasePromptConfig):
    """Configuration for product analysis prompts."""

    def __init__(self):
        """Initialize product analysis configuration."""
        super().__init__(
            model_name=settings.ai.default_model,
            temperature=0.1,  # Low temperature for consistent, factual responses
            max_tokens=8192,
            system_prompt=(
                "You are an expert at analyzing product listings and extracting relevant information. "
                "You have deep knowledge of various product categories and can identify key details "
                "that matter to potential buyers."
            ),
        )


class ProductAnalysisTemplate(BasePromptTemplate):
    """Template for product analysis prompts with structured output parsing."""

    def __init__(self):
        """Initialize product analysis template."""
        self.output_parser = JsonOutputParser(pydantic_object=ProductInfo)
        
        template = """
Analyze the following product listing to identify and extract key information.

Guidelines:
1. Extract the core product details:
   - Type: What kind of product is this?
   - Brand: Who manufactured it?
   - Base Model: What's the main model name/number?
   - Model Variant: Any specific version/edition?

2. Additional Information:
   - Extract any details that would help someone evaluate this product
   - Include specifications, condition, features, etc.
   - Organize related information into logical groups

3. Data Quality:
   - Use "null" for fields that can't be determined
   - Be precise with technical specifications
   - Maintain original terminology where appropriate
   - Split comma-separated values into lists

Example Input:
Title: Used Apple MacBook Pro 16-inch with M1 Pro chip, 16GB RAM, 512GB SSD
Description: Excellent condition, barely used. Space Gray color. Comes with original charger.

Example Output:
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

Now analyze this listing:
{input}

JSON Output:"""

        super().__init__(template=template, config=ProductAnalysisConfig())

    async def parse_output(self, output: str) -> ProductInfo:
        """Parse the model output into a structured format.
        
        Args:
            output: Raw model output string
            
        Returns:
            ProductInfo: Parsed product information
        """
        return self.output_parser.parse(output)

    def to_langchain(self):
        """Get the LangChain-compatible prompt chain.
        
        Returns:
            Chain: LangChain prompt chain with output parsing
        """
        return super().to_langchain() | self.output_parser


def create_product_analysis_prompt() -> ProductAnalysisTemplate:
    """Create a product analysis prompt.
    
    Returns:
        ProductAnalysisTemplate: Configured prompt template
    """
    return ProductAnalysisTemplate()
