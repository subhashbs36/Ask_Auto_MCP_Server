"""Demo script showing how to use the PreviewTool."""

import asyncio
import json
from unittest.mock import Mock, AsyncMock

from json_editor_mcp.tools.preview_tool import PreviewTool
from json_editor_mcp.config.models import ServerConfig, LLMConfig, RedisConfig, PromptsConfig, GuardrailsConfig
from json_editor_mcp.models.core import ProposedChange


def create_demo_config():
    """Create a demo configuration."""
    return ServerConfig(
        llm_config=LLMConfig(
            provider="gemini",
            api_key="demo-key",
            model="gemini-pro",
            timeout=30,
            max_retries=3,
            retry_delay=1.0
        ),
        redis_config=RedisConfig(
            host="localhost",
            port=6379,
            password=None,
            db=0,
            connection_timeout=5,
            socket_timeout=5,
            max_connections=10
        ),
        prompts_config=PromptsConfig(
            system_prompt_file="prompts/system_prompt.txt",
            edit_instruction_template="prompts/templates/edit_instruction.txt",
            guardrails_prompt_file="prompts/guardrails_prompt.txt"
        ),
        guardrails_config=GuardrailsConfig(
            enabled=True,
            max_changes_per_request=50,
            forbidden_patterns=[],
            allowed_json_types=["string", "number", "boolean", "array", "object"],
            prevent_deletions=True,
            deletion_keywords=["delete", "remove", "clear", "erase", "eliminate"],
            allow_empty_values=True,
            max_instruction_length=5000
        ),
        max_document_size=10485760,
        log_level="INFO",
        session_ttl=3600
    )


def create_sample_document():
    """Create a sample JSON document."""
    return {
        "title": {
            "type": "text",
            "value": "My Blog Post"
        },
        "content": {
            "type": "text",
            "value": "This is the original content of my blog post."
        },
        "metadata": {
            "author": {
                "type": "text",
                "value": "John Doe"
            },
            "tags": ["technology", "programming"],
            "published": False
        }
    }


def mock_llm_service_with_changes():
    """Create a mock LLM service that returns sample changes."""
    mock_service = Mock()
    mock_service.get_provider_name = Mock(return_value="gemini")
    mock_service.get_model_name = Mock(return_value="gemini-pro")
    
    # Mock proposed changes
    proposed_changes = [
        ProposedChange(
            id="t0",
            path=["title", "value"],
            current_value="My Blog Post",
            proposed_value="My Updated Blog Post",
            confidence=0.95
        ),
        ProposedChange(
            id="t1",
            path=["content", "value"],
            current_value="This is the original content of my blog post.",
            proposed_value="This is the updated and improved content of my blog post.",
            confidence=0.90
        )
    ]
    
    mock_service.get_proposed_changes = AsyncMock(return_value=proposed_changes)
    return mock_service


def mock_llm_service_no_changes():
    """Create a mock LLM service that returns no changes."""
    mock_service = Mock()
    mock_service.get_provider_name = Mock(return_value="gemini")
    mock_service.get_model_name = Mock(return_value="gemini-pro")
    mock_service.get_proposed_changes = AsyncMock(return_value=[])
    return mock_service


async def demo_successful_preview():
    """Demonstrate a successful preview operation."""
    print("=== Demo: Successful Preview ===")
    
    # Create configuration and document
    config = create_demo_config()
    document = create_sample_document()
    
    # Mock the LLM service creation
    from unittest.mock import patch
    with patch('json_editor_mcp.tools.preview_tool.create_llm_service') as mock_create:
        mock_create.return_value = mock_llm_service_with_changes()
        
        # Create preview tool
        tool = PreviewTool(config)
        
        # Mock session manager
        tool.session_manager.create_session = Mock(return_value="demo-session-123")
        
        # Prepare request
        request_data = {
            "document": document,
            "instruction": "Update the title and improve the content to be more engaging"
        }
        
        # Handle preview
        result = await tool.handle_preview(request_data)
        
        # Display results
        print(f"Status: {result['status']}")
        print(f"Session ID: {result['session_id']}")
        print(f"Number of changes: {len(result['changes'])}")
        print(f"Message: {result['message']}")
        print("\nProposed Changes:")
        
        for i, change in enumerate(result['changes'], 1):
            path_str = " -> ".join(change['path'])
            print(f"  {i}. {path_str}")
            print(f"     Current: '{change['current_value']}'")
            print(f"     Proposed: '{change['proposed_value']}'")
            print(f"     Confidence: {change['confidence']}")
        
        print()


async def demo_no_changes_preview():
    """Demonstrate a preview operation with no changes needed."""
    print("=== Demo: No Changes Needed ===")
    
    # Create configuration and document
    config = create_demo_config()
    document = create_sample_document()
    
    # Mock the LLM service creation
    from unittest.mock import patch
    with patch('json_editor_mcp.tools.preview_tool.create_llm_service') as mock_create:
        mock_create.return_value = mock_llm_service_no_changes()
        
        # Create preview tool
        tool = PreviewTool(config)
        
        # Mock session manager
        tool.session_manager.generate_session_id = Mock(return_value="dummy-session-456")
        
        # Prepare request
        request_data = {
            "document": document,
            "instruction": "The document is already perfect as is"
        }
        
        # Handle preview
        result = await tool.handle_preview(request_data)
        
        # Display results
        print(f"Status: {result['status']}")
        print(f"Session ID: {result['session_id']}")
        print(f"Number of changes: {len(result['changes'])}")
        print(f"Message: {result['message']}")
        print()


async def demo_validation_error():
    """Demonstrate a preview operation with validation error."""
    print("=== Demo: Validation Error ===")
    
    # Create configuration
    config = create_demo_config()
    
    # Mock the LLM service creation
    from unittest.mock import patch
    with patch('json_editor_mcp.tools.preview_tool.create_llm_service') as mock_create:
        mock_create.return_value = mock_llm_service_with_changes()
        
        # Create preview tool
        tool = PreviewTool(config)
        
        # Prepare invalid request (missing instruction)
        request_data = {
            "document": create_sample_document(),
            # Missing instruction field
        }
        
        # Handle preview
        result = await tool.handle_preview(request_data)
        
        # Display results
        print(f"Status: {result['status']}")
        print("Error Details:")
        error = result['error']
        print(f"  Type: {error['error_type']}")
        print(f"  Code: {error['error_code']}")
        print(f"  Message: {error['message']}")
        print()


def demo_tool_schema():
    """Demonstrate the tool schema."""
    print("=== Demo: Tool Schema ===")
    
    # Create configuration
    config = create_demo_config()
    
    # Mock the LLM service creation
    from unittest.mock import patch
    with patch('json_editor_mcp.tools.preview_tool.create_llm_service') as mock_create:
        mock_create.return_value = mock_llm_service_with_changes()
        
        # Create preview tool
        tool = PreviewTool(config)
        
        # Get tool schema
        schema = tool.get_tool_schema()
        
        # Display schema
        print("Tool Schema:")
        print(json.dumps(schema, indent=2))
        print()


def demo_health_check():
    """Demonstrate the health check."""
    print("=== Demo: Health Check ===")
    
    # Create configuration
    config = create_demo_config()
    
    # Mock the LLM service creation
    from unittest.mock import patch
    with patch('json_editor_mcp.tools.preview_tool.create_llm_service') as mock_create:
        mock_create.return_value = mock_llm_service_with_changes()
        
        # Create preview tool
        tool = PreviewTool(config)
        
        # Mock session manager health check
        tool.session_manager.health_check = Mock(return_value={
            "status": "healthy",
            "redis_connected": True,
            "active_sessions": 0
        })
        
        # Get health status
        health = tool.health_check()
        
        # Display health status
        print("Health Check Results:")
        print(json.dumps(health, indent=2))
        print()


async def main():
    """Run all demos."""
    print("JSON Editor MCP Tool - PreviewTool Demo")
    print("=" * 50)
    print()
    
    # Run demos
    await demo_successful_preview()
    await demo_no_changes_preview()
    await demo_validation_error()
    demo_tool_schema()
    demo_health_check()
    
    print("Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())