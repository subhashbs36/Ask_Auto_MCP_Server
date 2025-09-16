"""Factory for creating LLM service instances."""

from typing import Type
from .interface import LLMServiceInterface
from .gemini_adapter import GeminiLLMService
from .openai_adapter import OpenAILLMService
from .custom_adapter import CustomLLMService
from ..config.models import LLMConfig


def create_llm_service(config: LLMConfig) -> LLMServiceInterface:
    """Create an LLM service instance based on the provider configuration.
    
    Args:
        config: LLM configuration containing provider and settings
        
    Returns:
        LLM service instance for the specified provider
        
    Raises:
        ValueError: If provider is not supported
    """
    provider_map: dict[str, Type[LLMServiceInterface]] = {
        "gemini": GeminiLLMService,
        "openai": OpenAILLMService,
        "custom": CustomLLMService,
    }
    
    provider = config.provider.lower()
    
    if provider not in provider_map:
        supported_providers = ", ".join(provider_map.keys())
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: {supported_providers}"
        )
    
    service_class = provider_map[provider]
    return service_class(config)