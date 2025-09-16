#!/usr/bin/env python3
"""
Demonstration script for the JSON Editor MCP Tool configuration system.

This script shows how to:
1. Load configuration from YAML files and environment variables
2. Handle configuration validation errors
3. Create example configurations
4. Use different configuration sources
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from json_editor_mcp.config import (
    load_config,
    create_example_config,
    ConfigurationError,
    ServerConfig
)


def demo_basic_config_loading():
    """Demonstrate basic configuration loading."""
    print("=== Basic Configuration Loading ===")
    
    try:
        # Try to load configuration (will use environment variables if no YAML file)
        config = load_config()
        print(f"✓ Configuration loaded successfully!")
        print(f"  LLM Provider: {config.llm_config.provider}")
        print(f"  Redis Host: {config.redis_config.host}")
        print(f"  Log Level: {config.log_level}")
        print(f"  Max Document Size: {config.max_document_size} bytes")
        
    except ConfigurationError as e:
        print(f"✗ Configuration error: {e}")
        print("  This is expected if no configuration is provided.")


def demo_environment_config():
    """Demonstrate configuration from environment variables."""
    print("\n=== Environment Variable Configuration ===")
    
    # Set some environment variables
    env_vars = {
        'LLM_PROVIDER': 'openai',
        'LLM_API_KEY': 'demo-api-key',
        'LLM_MODEL': 'gpt-4',
        'LOG_LEVEL': 'DEBUG',
        'REDIS_HOST': 'redis.example.com'
    }
    
    # Save original values
    original_values = {}
    for key in env_vars:
        original_values[key] = os.environ.get(key)
        os.environ[key] = env_vars[key]
    
    try:
        config = load_config()
        print("✓ Configuration loaded from environment variables:")
        print(f"  LLM Provider: {config.llm_config.provider}")
        print(f"  LLM Model: {config.llm_config.model}")
        print(f"  Log Level: {config.log_level}")
        print(f"  Redis Host: {config.redis_config.host}")
        
    except ConfigurationError as e:
        print(f"✗ Configuration error: {e}")
    
    finally:
        # Restore original values
        for key, value in original_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def demo_yaml_config():
    """Demonstrate configuration from YAML file."""
    print("\n=== YAML Configuration ===")
    
    # Check if example config exists
    example_config_path = project_root / "config.yaml.example"
    if example_config_path.exists():
        try:
            config = load_config(str(example_config_path))
            print("✓ Configuration loaded from YAML file:")
            print(f"  LLM Provider: {config.llm_config.provider}")
            print(f"  Guardrails Enabled: {config.guardrails_config.enabled}")
            print(f"  Max Changes Per Request: {config.guardrails_config.max_changes_per_request}")
            
        except ConfigurationError as e:
            print(f"✗ Configuration error: {e}")
    else:
        print("✗ Example config file not found")


def demo_validation_errors():
    """Demonstrate configuration validation errors."""
    print("\n=== Configuration Validation Errors ===")
    
    # Set invalid environment variables
    os.environ['LLM_PROVIDER'] = 'invalid_provider'
    os.environ['LLM_API_KEY'] = 'test-key'
    os.environ['LLM_MODEL'] = 'test-model'
    
    try:
        config = load_config()
        print("✗ This should have failed!")
        
    except ConfigurationError as e:
        print("✓ Validation error caught as expected:")
        print(f"  {e}")
    
    finally:
        # Clean up
        os.environ.pop('LLM_PROVIDER', None)
        os.environ.pop('LLM_API_KEY', None)
        os.environ.pop('LLM_MODEL', None)


def demo_example_config():
    """Demonstrate creating example configuration."""
    print("\n=== Example Configuration Creation ===")
    
    example = create_example_config()
    print("✓ Example configuration created:")
    print(f"  LLM Provider: {example['llm_config']['provider']}")
    print(f"  LLM Model: {example['llm_config']['model']}")
    print(f"  Redis Host: {example['redis_config']['host']}")
    print(f"  Guardrails Enabled: {example['guardrails_config']['enabled']}")
    
    # Verify it creates a valid ServerConfig
    try:
        config = ServerConfig(**example)
        print("✓ Example configuration is valid")
    except Exception as e:
        print(f"✗ Example configuration is invalid: {e}")


def main():
    """Run all configuration demonstrations."""
    print("JSON Editor MCP Tool - Configuration System Demo")
    print("=" * 50)
    
    demo_basic_config_loading()
    demo_environment_config()
    demo_yaml_config()
    demo_validation_errors()
    demo_example_config()
    
    print("\n" + "=" * 50)
    print("Demo completed!")
    print("\nTo use the configuration system in your application:")
    print("1. Create a config.yaml file (see config.yaml.example)")
    print("2. Set environment variables as needed")
    print("3. Use load_config() to load and validate configuration")


if __name__ == "__main__":
    main()