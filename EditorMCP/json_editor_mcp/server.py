"""MCP Server interface for JSON Editor MCP Tool."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence

import structlog
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel.server import NotificationOptions
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    ToolsCapability
)
from mcp import McpError

from .config.models import ServerConfig
from .config.loader import ConfigLoader
from .tools.preview_tool import PreviewTool
from .tools.apply_tool import ApplyTool
from .models.errors import (
    ValidationException, LLMException, SessionException, ProcessingException
)


class MCPServer:
    """MCP Server that registers and handles JSON Editor tools."""
    
    def __init__(self, config: ServerConfig):
        """Initialize the MCP server with configuration.
        
        Args:
            config: Server configuration containing all service settings
        """
        self.config = config
        self.logger = structlog.get_logger(__name__)
        
        # Initialize MCP server
        self.server = Server("json-editor-mcp")
        
        # Initialize tools
        self.preview_tool = PreviewTool(config)
        self.apply_tool = ApplyTool(config)
        
        # Register MCP handlers
        self._register_handlers()
        
        self.logger.info("MCP Server initialized successfully")
    
    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """Handle list_tools request."""
            return await self._handle_list_tools()
        
        @self.server.call_tool()
        async def handle_call_tool(request: CallToolRequest) -> CallToolResult:
            """Handle call_tool request."""
            return await self._handle_call_tool(request)
    
    async def _handle_list_tools(self) -> ListToolsResult:
        """Handle list_tools MCP request.
        
        Returns:
            ListToolsResult containing available tools
        """
        try:
            tools = [
                Tool(
                    name="json_editor_preview",
                    description="Preview proposed changes to a JSON document using natural language instructions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document": {
                                "type": "object",
                                "description": "JSON document to edit"
                            },
                            "instruction": {
                                "type": "string",
                                "description": "Natural language editing instruction"
                            }
                        },
                        "required": ["document", "instruction"]
                    }
                ),
                Tool(
                    name="json_editor_apply",
                    description="Apply previously previewed changes to a JSON document",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Session ID from preview operation"
                            },
                            "confirmed_changes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of change IDs to apply. If omitted, all changes are applied"
                            }
                        },
                        "required": ["session_id"]
                    }
                )
            ]
            
            self.logger.debug(f"Listed {len(tools)} available tools")
            return ListToolsResult(tools=tools)
            
        except Exception as e:
            self.logger.error(f"Error listing tools: {e}", exc_info=True)
            raise McpError(
                code=INTERNAL_ERROR,
                message=f"Failed to list tools: {str(e)}"
            )
    
    async def _handle_call_tool(self, request: CallToolRequest) -> CallToolResult:
        """Handle call_tool MCP request.
        
        Args:
            request: CallToolRequest containing tool name and arguments
            
        Returns:
            CallToolResult containing tool execution results
        """
        try:
            # Validate request
            self._validate_tool_request(request)
            
            # Route to appropriate tool handler
            if request.params.name == "json_editor_preview":
                result = await self._handle_preview_tool(request.params.arguments)
            elif request.params.name == "json_editor_apply":
                result = await self._handle_apply_tool(request.params.arguments)
            else:
                raise McpError(
                    code=METHOD_NOT_FOUND,
                    message=f"Unknown tool: {request.params.name}"
                )
            
            # Convert result to MCP format
            return self._create_tool_result(result)
            
        except McpError:
            # Re-raise MCP errors as-is
            raise
        except ValidationException as e:
            self.logger.warning(f"Validation error in tool call: {e.message}")
            raise McpError(
                code=INVALID_PARAMS,
                message=e.message,
                data=e.details
            )
        except (LLMException, SessionException, ProcessingException) as e:
            self.logger.error(f"Tool execution error: {e.message}")
            raise McpError(
                code=INTERNAL_ERROR,
                message=e.message,
                data=e.details
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in tool call: {e}", exc_info=True)
            raise McpError(
                code=INTERNAL_ERROR,
                message=f"An unexpected error occurred: {str(e)}"
            )
    
    def _validate_tool_request(self, request: CallToolRequest) -> None:
        """Validate the tool call request.
        
        Args:
            request: CallToolRequest to validate
            
        Raises:
            McpError: If request validation fails
        """
        if not request.params:
            raise McpError(
                code=INVALID_PARAMS,
                message="Missing tool call parameters"
            )
        
        if not request.params.name:
            raise McpError(
                code=INVALID_PARAMS,
                message="Missing tool name"
            )
        
        if not hasattr(request.params, 'arguments') or request.params.arguments is None:
            raise McpError(
                code=INVALID_PARAMS,
                message="Missing tool arguments"
            )
    
    async def _handle_preview_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle json_editor_preview tool call.
        
        Args:
            arguments: Tool arguments from MCP request
            
        Returns:
            Tool execution result
        """
        self.logger.info("Handling json_editor_preview tool call")
        
        try:
            result = await self.preview_tool.handle_preview(arguments)
            self.logger.info("Preview tool executed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Preview tool execution failed: {e}")
            raise
    
    async def _handle_apply_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle json_editor_apply tool call.
        
        Args:
            arguments: Tool arguments from MCP request
            
        Returns:
            Tool execution result
        """
        self.logger.info("Handling json_editor_apply tool call")
        
        try:
            result = await self.apply_tool.handle_apply(arguments)
            self.logger.info("Apply tool executed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Apply tool execution failed: {e}")
            raise
    
    def _create_tool_result(self, result: Dict[str, Any]) -> CallToolResult:
        """Create MCP CallToolResult from tool execution result.
        
        Args:
            result: Tool execution result dictionary
            
        Returns:
            CallToolResult for MCP response
        """
        try:
            # Check if result contains an error
            if "error" in result:
                error_info = result["error"]
                content = [
                    TextContent(
                        type="text",
                        text=f"Error: {error_info.get('message', 'Unknown error')}"
                    )
                ]
                
                # Add error details if available
                if "details" in error_info:
                    import json
                    details_text = json.dumps(error_info["details"], indent=2)
                    content.append(
                        TextContent(
                            type="text",
                            text=f"Details: {details_text}"
                        )
                    )
            else:
                # Success result
                import json
                result_text = json.dumps(result, indent=2, default=str)
                content = [
                    TextContent(
                        type="text",
                        text=result_text
                    )
                ]
            
            return CallToolResult(
                content=content,
                isError="error" in result
            )
            
        except Exception as e:
            self.logger.error(f"Error creating tool result: {e}")
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Error formatting result: {str(e)}"
                    )
                ],
                isError=True
            )
    
    async def run_stdio(self) -> None:
        """Run the MCP server using stdio transport.
        
        This is the main entry point for running the server.
        """
        try:
            self.logger.info("Starting MCP server with stdio transport")
            
            # Perform health checks before starting
            await self._perform_health_checks()
            
            # Run the server
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="json-editor-mcp",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
                
        except Exception as e:
            self.logger.error(f"Error running MCP server: {e}", exc_info=True)
            raise
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all components before starting server.
        
        Raises:
            Exception: If any health check fails
        """
        self.logger.info("Performing health checks...")
        
        try:
            # Check preview tool health
            preview_health = self.preview_tool.health_check()
            if preview_health.get("status") != "healthy":
                raise Exception(f"Preview tool health check failed: {preview_health}")
            
            # Check apply tool health
            apply_health = self.apply_tool.health_check()
            if apply_health.get("status") != "healthy":
                raise Exception(f"Apply tool health check failed: {apply_health}")
            
            self.logger.info("All health checks passed")
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            raise
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information and status.
        
        Returns:
            Dictionary containing server information
        """
        try:
            return {
                "name": "json-editor-mcp",
                "version": "1.0.0",
                "description": "MCP server for natural language JSON document editing",
                "tools": [
                    {
                        "name": "json_editor_preview",
                        "description": "Preview proposed changes to a JSON document"
                    },
                    {
                        "name": "json_editor_apply", 
                        "description": "Apply previously previewed changes"
                    }
                ],
                "config": {
                    "llm_provider": self.config.llm_config.provider,
                    "llm_model": self.config.llm_config.model,
                    "max_document_size": self.config.max_document_size,
                    "session_ttl": self.config.session_ttl,
                    "log_level": self.config.log_level
                },
                "health": {
                    "preview_tool": self.preview_tool.health_check(),
                    "apply_tool": self.apply_tool.health_check()
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting server info: {e}")
            return {
                "name": "json-editor-mcp",
                "version": "1.0.0",
                "status": "error",
                "error": str(e)
            }


async def create_server(config_path: Optional[str] = None) -> MCPServer:
    """Create and initialize MCP server with configuration.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Initialized MCPServer instance
        
    Raises:
        Exception: If server creation fails
    """
    try:
        # Load configuration
        config_loader = ConfigLoader()
        if config_path:
            config = config_loader.load_from_file(config_path)
        else:
            # Try to load from config.yaml first, then fall back to environment
            try:
                config = config_loader.load_from_file("config.yaml")
            except FileNotFoundError:
                config = config_loader.load_from_env()
        
        # Create and return server
        server = MCPServer(config)
        return server
        
    except Exception as e:
        logger = structlog.get_logger(__name__)
        logger.error(f"Failed to create MCP server: {e}", exc_info=True)
        raise


async def main(config_path: Optional[str] = None) -> None:
    """Main entry point for running the MCP server.
    
    Args:
        config_path: Optional path to configuration file
    """
    try:
        # Create and run server
        server = await create_server(config_path)
        await server.run_stdio()
        
    except KeyboardInterrupt:
        logger = structlog.get_logger(__name__)
        logger.info("Server shutdown requested")
    except Exception as e:
        logger = structlog.get_logger(__name__)
        logger.error(f"Server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import sys
    
    # Get config path from command line arguments if provided
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Run the server
    asyncio.run(main(config_path))