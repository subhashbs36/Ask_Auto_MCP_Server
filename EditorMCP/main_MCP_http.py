"""
JSON Editor REST API Server
JSON Editor MCP server functionality in a REST API
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Import the sophisticated components from your original code
from json_editor_mcp.config.loader import ConfigLoader
from json_editor_mcp.tools.preview_tool import PreviewTool
from json_editor_mcp.tools.apply_tool import ApplyTool
from json_editor_mcp.models.errors import (
    ValidationException, LLMException, SessionException, ProcessingException
)

# Pydantic models for API
class EditRequest(BaseModel):
    """Request model for JSON editing."""
    document: Dict[str, Any] = Field(..., description="JSON document to edit")
    instruction: str = Field(..., description="Natural language editing instruction")

class PreviewResponse(BaseModel):
    """Response model for preview operation."""
    session_id: str = Field(..., description="Session ID for applying changes")
    changes: List[Dict[str, Any]] = Field(..., description="List of proposed changes")
    status: str = Field(..., description="Operation status")
    message: Optional[str] = Field(None, description="Optional message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class ApplyRequest(BaseModel):
    """Request model for applying changes."""
    session_id: str = Field(..., description="Session ID from preview operation")
    confirmed_changes: Optional[List[str]] = Field(None, description="Optional list of change IDs to apply")

class ApplyResponse(BaseModel):
    """Response model for apply operation."""
    modified_document: Dict[str, Any] = Field(..., description="Modified JSON document")
    applied_changes: List[Dict[str, Any]] = Field(..., description="List of applied changes")
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Success message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Server health status")
    version: str = Field(..., description="Server version")
    uptime: float = Field(..., description="Server uptime in seconds")
    active_sessions: int = Field(..., description="Number of active sessions")
    components: Dict[str, Any] = Field(..., description="Component health status")

class ServerInfoResponse(BaseModel):
    """Response model for server information."""
    name: str = Field(..., description="Server name")
    version: str = Field(..., description="Server version")
    description: str = Field(..., description="Server description")
    config: Dict[str, Any] = Field(..., description="Server configuration")
    health: Dict[str, Any] = Field(..., description="Component health status")

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
            # Load configuration using the config loader
            config_loader = ConfigLoader()
            
            # Always try to load from config.yaml first
            config_file = config_path or "config.yaml"
            
            try:
                self.config = config_loader.load_from_file(config_file)
                self.logger.info(f"Configuration loaded from {config_file}")
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

# Initialize the sophisticated server
json_editor_server = None

async def get_server():
    """Get or create the server instance."""
    global json_editor_server
    if json_editor_server is None:
        json_editor_server = JSONEditorServer()
    return json_editor_server

# FastAPI app
app = FastAPI(
    title="Sophisticated JSON Editor API",
    description="Advanced REST API for editing JSON documents using natural language with LLM integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize server on startup."""
    global json_editor_server
    try:
        json_editor_server = JSONEditorServer()
        logging.info("Sophisticated JSON Editor REST API server started successfully")
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        raise

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check endpoint."""
    server = await get_server()
    health_data = await server.health_check()
    return HealthResponse(**health_data)

@app.get("/info", response_model=ServerInfoResponse)
async def server_info():
    """Get comprehensive server information."""
    server = await get_server()
    info_data = server.get_server_info()
    
    # Get current health for the response
    health_data = await server.health_check()
    info_data["health"] = health_data.get("components", {})
    
    return ServerInfoResponse(**info_data)

@app.post("/preview", response_model=PreviewResponse)
async def preview_changes(request: EditRequest):
    """Preview changes to a JSON document using sophisticated analysis."""
    server = await get_server()
    result = await server.preview_changes(request.document, request.instruction)
    return PreviewResponse(**result)

@app.post("/apply", response_model=ApplyResponse)
async def apply_changes(request: ApplyRequest):
    """Apply previously previewed changes using sophisticated processing."""
    server = await get_server()
    result = await server.apply_changes(request.session_id, request.confirmed_changes)
    return ApplyResponse(**result)

@app.get("/sessions")
async def list_sessions():
    """List active sessions with metadata."""
    server = await get_server()
    active_session_ids = server.session_manager.list_active_sessions()
    
    sessions_info = {}
    for session_id in active_session_ids:
        session_data = server.session_manager.get_session(session_id)
        if session_data:
            sessions_info[session_id] = {
                "created_at": session_data.created_at.isoformat(),
                "document_hash": session_data.document_hash,
                "changes_count": len(session_data.proposed_changes),
                "age_seconds": (datetime.now(timezone.utc) - session_data.created_at).total_seconds()
            }
    
    return {
        "active_sessions": len(sessions_info),
        "sessions": sessions_info
    }

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session."""
    server = await get_server()
    session_data = server.session_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    server.session_manager.delete_session(session_id)
    return {"message": f"Session {session_id} deleted successfully"}

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "JSON Editor API",
        "version": "1.0.0",
        "description": "Advanced REST API for editing JSON documents using natural language",
        "features": [
            "LLM integration (Gemini, OpenAI, Custom)",
            "Change detection and validation",
            "Session-based workflow with automatic cleanup",
            "Comprehensive error handling and logging",
            "Guardrails and safety checks",
            "Performance monitoring and metrics"
        ],
        "endpoints": {
            "POST /preview": "Preview proposed changes to a JSON document",
            "POST /apply": "Apply previously previewed changes",
            "GET /health": "Health check with component status",
            "GET /info": "Server information and configuration",
            "GET /sessions": "List active sessions",
            "DELETE /sessions/{id}": "Delete a specific session"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )