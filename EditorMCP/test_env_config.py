#!/usr/bin/env python3
"""Test script to verify .env file integration with config loader."""

import os
import sys
from pathlib import Path

# Add the json_editor_mcp package to the path
sys.path.insert(0, str(Path(__file__).parent))

from json_editor_mcp.config.loader import ConfigLoader

def test_env_loading():
    """Test that .env file is properly loaded."""
    print("Testing .env file integration...")
    
    # Create a config loader
    loader = ConfigLoader(config_file="config.yaml", env_file=".env")
    
    # Check if GEMINI_API_KEY is loaded from .env file
    gemini_key = os.getenv('GEMINI_API_KEY')
    print(f"GEMINI_API_KEY from environment: {gemini_key}")
    
    if gemini_key:
        print("✅ .env file loaded successfully!")
        print(f"   API Key starts with: {gemini_key[:10]}...")
    else:
        print("❌ .env file not loaded or GEMINI_API_KEY not found")
    
    # Test configuration loading
    try:
        config = loader.load_config()
        print("\n✅ Configuration loaded successfully!")
        print(f"   LLM Provider: {config.llm_config.provider}")
        print(f"   LLM Model: {config.llm_config.model}")
        print(f"   API Key starts with: {str(config.llm_config.api_key)[:10]}...")
        
        return True
    except Exception as e:
        print(f"\n❌ Configuration loading failed: {e}")
        return False

def test_yaml_env_substitution():
    """Test that YAML file properly substitutes environment variables."""
    print("\nTesting YAML environment variable substitution...")
    
    try:
        loader = ConfigLoader(config_file="config.yaml", env_file=".env")
        config = loader.load_config()
        
        # Check if the API key from YAML substitution matches the environment
        expected_key = os.getenv('GEMINI_API_KEY')
        actual_key = config.llm_config.api_key
        
        if actual_key == expected_key:
            print("✅ YAML environment variable substitution working!")
            print("   Substituted value matches environment variable")
        else:
            print("❌ YAML environment variable substitution failed")
            print(f"   Expected: {expected_key}")
            print(f"   Got: {actual_key}")
            return False
            
        return True
    except Exception as e:
        print(f"❌ YAML substitution test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing .env integration with configuration loader\n")
    
    # Test 1: Basic .env loading
    test1_passed = test_env_loading()
    
    # Test 2: YAML environment variable substitution
    test2_passed = test_yaml_env_substitution()
    
    print("\n📊 Test Results:")
    print(f"   .env loading: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"   YAML substitution: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! .env integration is working correctly.")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Please check the configuration.")
        sys.exit(1)