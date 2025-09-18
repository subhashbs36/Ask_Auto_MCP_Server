"""
JSONEditorServer class for handling JSON editing operations.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from json_editor_mcp.config.loader import ConfigLoader
from json_editor_mcp.tools.preview_tool import PreviewTool
from json_editor_mcp.tools.apply_tool import ApplyTool
from json_editor_mcp.models.errors import (
    ValidationException, LLMException, SessionException, ProcessingException
)


class JSONEditorServer:
    """REST API server wrapping the JSON Editor functionality."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the server with configuration."""
        self.logger = logging.getLogger(__name__)
        self.session_ttl = 3600  # 1 hour
        self.start_time = time.time()
        
        # Initialize the sophisticated components
        self._initialize_components(config_path)
        
        # Start background cleanup
        self._start_cleanup_task()
    
    def _initialize_components(self, config_path: Optional[str] = None):
        """Initialize the JSON Editor components."""
        try:
            # Try to find config.yaml in the project root
            if config_path is None:
                # Look for config.yaml in the project root (two levels up from src/api/)
                from pathlib import Path
                current_dir = Path(__file__).parent
                project_root = current_dir.parent.parent
                config_file = project_root / "config.yaml"
                env_file = project_root / ".env"
                
                # Fallback to current directory if not found in project root
                if not config_file.exists():
                    config_file = "config.yaml"
                if not env_file.exists():
                    env_file = ".env"
            else:
                config_file = config_path
                # Find .env file relative to config file
                from pathlib import Path
                config_dir = Path(config_path).parent
                env_file = config_dir / ".env"
            
            # Load configuration using the config loader with proper .env file location
            config_loader = ConfigLoader(env_file=str(env_file))
            
            try:
                self.config = config_loader.load_from_file(str(config_file))
                self.logger.info(f"Configuration loaded from {config_file}")
                self.logger.info(f"Environment variables loaded from {env_file}")
            except FileNotFoundError:
                self.logger.warning(f"Configuration file {config_file} not found, creating minimal config")
                self.config = self._create_minimal_config()
            
            # Initialize shared session manager first
            from json_editor_mcp.services.hybrid_session_manager import HybridSessionManager
            self.session_manager = HybridSessionManager(
                redis_config=self.config.redis_config,
                session_ttl=self.config.session_ttl,
                prefer_redis=getattr(self.config, 'prefer_redis', False)
            )
            
            # Initialize the sophisticated tools with shared session manager
            self.preview_tool = PreviewTool(self.config, self.session_manager)
            self.apply_tool = ApplyTool(self.config, self.session_manager)
            
            self.logger.info("JSON Editor components initialized successfully")
            self.logger.info(f"Using LLM provider: {self.config.llm_config.provider}")
            self.logger.info(f"Using LLM model: {self.config.llm_config.model}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
    
    def _create_minimal_config(self):
        """Create a minimal configuration when no config file is available."""
        from json_editor_mcp.config.models import ServerConfig, LLMConfig, RedisConfig
        
        # Get LLM config from environment variables as fallback
        llm_provider = os.getenv('LLM_PROVIDER', 'gemini')
        llm_api_key = (
            os.getenv('LLM_API_KEY') or 
            os.getenv('GEMINI_API_KEY') or 
            os.getenv('GOOGLE_GEN_AI_KEY')
        )
        llm_model = os.getenv('LLM_MODEL') or os.getenv('GOOGLE_GEN_AI_MODEL', 'gemini-2.0-flash')
        
        if not llm_api_key:
            raise ValueError(
                "LLM API key is required. Either:\n"
                "1. Create a config.yaml file with your API key, or\n"
                "2. Set one of these environment variables: LLM_API_KEY, GEMINI_API_KEY, GOOGLE_GEN_AI_KEY"
            )
        
        llm_config = LLMConfig(
            provider=llm_provider,
            api_key=llm_api_key,
            model=llm_model,
            endpoint=None,
            timeout=30,
            custom_headers=None,
            auth_token=None,
            retry_attempts=3,
            backoff_factor=1.0,
            max_retries=3,
            retry_delay=1.0
        )
        
        # Create Redis config with defaults
        redis_config = RedisConfig(
            host="localhost",
            port=6379,
            password=None,
            db=0,
            connection_timeout=5,
            socket_timeout=5,
            max_connections=10,
            session_expiration=3600
        )
        
        return ServerConfig(
            llm_config=llm_config,
            redis_config=redis_config,
            prefer_redis=False,  # Memory-first approach
            server_config=None,
            max_document_size=10485760,  # 10MB default
            log_level="INFO",
            session_ttl=3600  # 1 hour default
        )
    
    def _start_cleanup_task(self):
        """Start background task for session cleanup."""
        def cleanup_sessions():
            while True:
                try:
                    # Use the shared session manager's cleanup method
                    cleaned_count = self.session_manager.cleanup_expired_sessions()
                    if cleaned_count > 0:
                        self.logger.info(f"Cleaned up {cleaned_count} expired sessions")
                    
                except Exception as e:
                    self.logger.error(f"Error in session cleanup: {e}")
                
                time.sleep(300)  # Run every 5 minutes
        
        cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
        cleanup_thread.start()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            uptime = time.time() - self.start_time
            
            # Check preview tool health
            preview_health = self.preview_tool.health_check()
            
            # Check apply tool health
            apply_health = self.apply_tool.health_check()
            
            # Determine overall status
            overall_status = "healthy"
            if (preview_health.get("status") != "healthy" or 
                apply_health.get("status") != "healthy"):
                overall_status = "unhealthy"
            
            return {
                "status": overall_status,
                "version": "1.0.0",
                "uptime": uptime,
                "active_sessions": len(self.session_manager.list_active_sessions()),
                "components": {
                    "preview_tool": preview_health,
                    "apply_tool": apply_health
                }
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "version": "1.0.0",
                "uptime": time.time() - self.start_time,
                "active_sessions": len(self.session_manager.list_active_sessions()),
                "error": str(e)
            }
    
    async def preview_changes(self, document: Dict[str, Any], instruction: str) -> Dict[str, Any]:
        """Preview changes using the sophisticated preview tool."""
        try:
            # Validate input
            if not document:
                raise HTTPException(status_code=400, detail="Document is required")
            
            if not instruction.strip():
                raise HTTPException(status_code=400, detail="Instruction is required")
            
            # Use the sophisticated preview tool
            arguments = {
                "document": document,
                "instruction": instruction
            }
            
            result = await self.preview_tool.handle_preview(arguments)
            
            # Check if the result contains an error
            if "error" in result:
                error_info = result["error"]
                if error_info.get("error_type") == "validation":
                    raise HTTPException(status_code=400, detail=error_info.get("message", "Validation error"))
                else:
                    raise HTTPException(status_code=500, detail=error_info.get("message", "Processing error"))
            
            # The sophisticated tool already creates and manages the session
            
            # Add REST API specific metadata
            if "metadata" not in result:
                result["metadata"] = {}
            
            result["metadata"].update({
                "llm_provider": self.config.llm_config.provider,
                "model": self.config.llm_config.model
            })
            
            return result
            
        except HTTPException:
            raise
        except ValidationException as e:
            self.logger.warning(f"Validation error in preview: {e.message}")
            raise HTTPException(status_code=400, detail=e.message)
        except (LLMException, SessionException, ProcessingException) as e:
            self.logger.error(f"Preview tool error: {e.message}")
            raise HTTPException(status_code=500, detail=e.message)
        except Exception as e:
            self.logger.error(f"Unexpected error in preview: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    async def apply_changes(self, session_id: str, confirmed_changes: Optional[List[str]] = None) -> Dict[str, Any]:
        """Apply changes using the sophisticated apply tool."""
        try:
            # Validate session ID
            if not session_id:
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Use the sophisticated apply tool (it manages its own session validation)
            arguments = {
                "session_id": session_id,
                "confirmed_changes": confirmed_changes
            }
            
            result = await self.apply_tool.handle_apply(arguments)
            
            # Check if the result contains an error
            if "error" in result:
                error_info = result["error"]
                if error_info.get("error_type") == "validation":
                    raise HTTPException(status_code=400, detail=error_info.get("message", "Validation error"))
                elif error_info.get("error_type") == "session":
                    raise HTTPException(status_code=404, detail=error_info.get("message", "Session error"))
                else:
                    raise HTTPException(status_code=500, detail=error_info.get("message", "Processing error"))
            
            # Clean up session after successful apply
            session_data = self.session_manager.get_session(session_id)
            if session_data:
                # Add session duration to metadata before cleanup
                if "metadata" not in result:
                    result["metadata"] = {}
                
                # Calculate duration using session creation timestamp
                try:
                    result["metadata"]["session_duration"] = (
                        datetime.now(timezone.utc) - session_data.created_at
                    ).total_seconds()
                except (ValueError, AttributeError):
                    # Handle timestamp errors gracefully
                    pass
                
                self.session_manager.delete_session(session_id)
            
            # Add REST API specific metadata
            if "metadata" not in result:
                result["metadata"] = {}
            
            result["metadata"]["method"] = "sophisticated_processing"
            
            return result
            
        except HTTPException:
            raise
        except ValidationException as e:
            self.logger.warning(f"Validation error in apply: {e.message}")
            raise HTTPException(status_code=400, detail=e.message)
        except (LLMException, SessionException, ProcessingException) as e:
            self.logger.error(f"Apply tool error: {e.message}")
            raise HTTPException(status_code=500, detail=e.message)
        except Exception as e:
            self.logger.error(f"Unexpected error in apply: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get comprehensive server information."""
        try:
            return {
                "name": "json-editor-rest-api",
                "version": "1.0.0",
                "description": "Sophisticated JSON Editor REST API with advanced LLM integration",
                "config": {
                    "llm_provider": self.config.llm_config.provider,
                    "llm_model": self.config.llm_config.model,
                    "max_document_size": self.config.max_document_size,
                    "session_ttl": self.session_ttl,
                    "log_level": self.config.log_level
                },
                "endpoints": {
                    "POST /preview": "Preview proposed changes to a JSON document",
                    "POST /apply": "Apply previously previewed changes",
                    "GET /health": "Health check with component status",
                    "GET /info": "Server information and configuration",
                    "GET /sessions": "List active sessions",
                    "DELETE /sessions/{id}": "Delete a specific session"
                },
                "features": [
                    "Advanced LLM integration (Gemini, OpenAI, Custom)",
                    "Sophisticated change detection and validation",
                    "Session-based workflow with automatic cleanup",
                    "Comprehensive error handling and logging",
                    "Guardrails and safety checks",
                    "Performance monitoring and metrics"
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting server info: {e}")
            return {
                "name": "json-editor-rest-api",
                "version": "1.0.0",
                "status": "error",
                "error": str(e)
            }


# Global server instance
_json_editor_server = None


async def get_server():
    """Get or create the server instance."""
    global _json_editor_server
    if _json_editor_server is None:
        _json_editor_server = JSONEditorServer()
    return _json_editor_server