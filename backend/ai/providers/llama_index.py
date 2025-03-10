"""LlamaIndex provider implementation."""

import logging
from typing import Dict, List, Optional, Any

from llama_index.llms.groq import Groq
from llama_index.llms.gemini import Gemini
from llama_index.program.openai import OpenAIPydanticProgram
from llama_index.core import PromptTemplate

from .base import BaseProvider

logger = logging.getLogger(__name__)

class LlamaIndexProvider(BaseProvider):
    """LlamaIndex provider implementation of the BaseProvider interface."""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.llm = LlamaOpenAI(model=model_name)
    
    async def complete(self, prompt: str) -> str:
        """Complete a prompt using the LlamaIndex LLM."""
        response = self.llm.complete(prompt)
        return str(response)
        
    async def complete_chat(self, messages: List[Dict[str, str]]) -> str:
        """Complete a chat using the LlamaIndex LLM."""
        from llama_index.core.llms import ChatMessage, MessageRole
        
        # Convert to LlamaIndex message format
        converted_messages = []
        for msg in messages:
            role = MessageRole.SYSTEM if msg["role"] == "system" else MessageRole.USER
            converted_messages.append(ChatMessage(role=role, content=msg["content"]))
            
        response = self.llm.chat(converted_messages)
        return response.message.content
    
    async def complete_structured(self, prompt_template: str, output_class: Any, **kwargs) -> Any:
        """Generate structured output using LlamaIndex's PydanticProgram."""
        prompt = PromptTemplate(prompt_template)
        
        program = OpenAIPydanticProgram.from_defaults(
            output_cls=output_class,
            prompt=prompt,
            llm=self.llm,
        )
        
        return program(**kwargs) 