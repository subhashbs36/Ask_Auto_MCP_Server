#!/usr/bin/env python3
"""Example usage of LLM service interface and adapters."""

import asyncio
from json_editor_mcp.config.models import LLMConfig
from json_editor_mcp.services.factory import create_llm_service
from json_editor_mcp.models.core import MapEntry


async def example_gemini_usage():
    """Example of using Gemini LLM service."""
    print("=== Gemini LLM Service Example ===")
    
    # Configure Gemini service
    config = LLMConfig(
        provider="gemini",
        api_key="your-gemini-api-key-here",  # Replace with actual key
        model="gemini-2.5-flash",
        max_retries=3,
        retry_delay=1.0,
        timeout=30
    )
    
    # Create service instance
    service = create_llm_service(config)
    print(f"Created service: {type(service).__name__}")
    print(f"Provider: {service.get_provider_name()}")
    print(f"Model: {service.get_model_name()}")
    
    # Example map entries
    map_entries = [
        MapEntry(id="1", path=["user", "name"], value="John Doe"),
        MapEntry(id="2", path=["user", "age"], value="30"),
        MapEntry(id="3", path=["user", "email"], value="john@example.com"),
    ]
    
    # Note: Actual API calls would require valid API key
    print("Map entries prepared for processing:")
    for entry in map_entries:
        print(f"  {entry.id}: {' -> '.join(entry.path)} = {entry.value}")


async def example_openai_usage():
    """Example of using OpenAI LLM service."""
    print("\n=== OpenAI LLM Service Example ===")
    
    # Configure OpenAI service
    config = LLMConfig(
        provider="openai",
        api_key="your-openai-api-key-here",  # Replace with actual key
        model="gpt-4",
        max_retries=3,
        retry_delay=1.0,
        timeout=30
    )
    
    try:
        # Create service instance
        service = create_llm_service(config)
        print(f"Created service: {type(service).__name__}")
        print(f"Provider: {service.get_provider_name()}")
        print(f"Model: {service.get_model_name()}")
        
        retry_config = service.get_retry_config()
        print(f"Retry config: {retry_config}")
        
    except ImportError as e:
        print(f"OpenAI service not available: {e}")
        print("Install with: pip install openai")


async def example_custom_usage():
    """Example of using Custom LLM service."""
    print("\n=== Custom LLM Service Example ===")
    
    # Configure custom service
    config = LLMConfig(
        provider="custom",
        endpoint="https://api.example.com/v1/chat/completions",
        api_key="your-custom-api-key-here",  # Optional
        model="custom-model-name",
        max_retries=2,
        retry_delay=2.0,
        timeout=45
    )
    
    # Create service instance
    service = create_llm_service(config)
    print(f"Created service: {type(service).__name__}")
    print(f"Provider: {service.get_provider_name()}")
    print(f"Model: {service.get_model_name()}")
    print(f"Endpoint: {service.config.endpoint}")
    
    # Show headers that would be used
    print("Request headers:")
    for key, value in service.headers.items():
        if key == "Authorization":
            print(f"  {key}: Bearer ***")  # Hide API key
        else:
            print(f"  {key}: {value}")


async def example_error_handling():
    """Example of error handling with LLM services."""
    print("\n=== Error Handling Example ===")
    
    # Test invalid configuration
    try:
        config = LLMConfig(
            provider="gemini",
            # Missing API key
            model="gemini-2.5-flash"
        )
        service = create_llm_service(config)
    except ValueError as e:
        print(f"✓ Caught expected validation error: {e}")
    
    # Test unsupported provider
    try:
        config = LLMConfig(
            provider="unsupported-provider",
            model="some-model"
        )
        service = create_llm_service(config)
    except ValueError as e:
        print(f"✓ Caught expected provider error: {e}")
    
    # Test custom service without endpoint
    try:
        config = LLMConfig(
            provider="custom",
            model="custom-model"
            # Missing endpoint
        )
        service = create_llm_service(config)
    except ValueError as e:
        print(f"✓ Caught expected endpoint error: {e}")


async def main():
    """Run all examples."""
    print("LLM Service Interface and Adapters Examples")
    print("=" * 50)
    
    await example_gemini_usage()
    await example_openai_usage()
    await example_custom_usage()
    await example_error_handling()
    
    print("\n" + "=" * 50)
    print("Examples completed successfully!")
    print("\nTo use these services with real API calls:")
    print("1. Replace API keys with your actual keys")
    print("2. Ensure you have the required dependencies installed")
    print("3. Call get_proposed_changes() or handle_ambiguous_instruction() methods")


if __name__ == "__main__":
    asyncio.run(main())