from ..ai.base import AIModel

PROMPT_TEMPLATE = """Extract key specifications from the following product description in JSON format:
{input}

Return a JSON object with key-value pairs for specifications like:
- CPU model
- GPU model
- RAM amount
- Storage type and capacity
- Screen size and resolution
- Any other relevant specifications

Example response:
{
  "cpu": "AMD Ryzen 9 5900HS",
  "gpu": "NVIDIA RTX 3050 Ti 4GB",
  "ram": "16GB DDR4",
  "storage": "1TB NVMe SSD",
  "display": "14-inch 1440p 120Hz",
  "weight": "1.7kg"
}"""


def get_model_instance() -> AIModel:
    """Get the model configuration for description parsing."""
    return AIModel(
        model_name="gemini-2.0-flash-exp",
        temperature=0.1,  # Low temperature for consistent, factual responses
        max_tokens=1000,  # More tokens for detailed specs
        prompt_template=PROMPT_TEMPLATE,
    )
