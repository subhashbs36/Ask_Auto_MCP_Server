"""
FastAPI route handlers for the JSON Editor REST API.
"""

import logging
from datetime import datetime, timezone
from fastapi import HTTPException

from .models import (
    EditRequest, PreviewResponse, ApplyRequest, ApplyResponse,
    HealthResponse, ServerInfoResponse
)
from .server import get_server


async def health_check():
    """Comprehensive health check endpoint."""
    server = await get_server()
    health_data = await server.health_check()
    return HealthResponse(**health_data)


async def server_info():
    """Get comprehensive server information."""
    server = await get_server()
    info_data = server.get_server_info()
    
    # Get current health for the response
    health_data = await server.health_check()
    info_data["health"] = health_data.get("components", {})
    
    return ServerInfoResponse(**info_data)


async def preview_changes(request: EditRequest):
    """Preview changes to a JSON document using sophisticated analysis."""
    server = await get_server()
    result = await server.preview_changes(request.document, request.instruction)
    return PreviewResponse(**result)


async def apply_changes(request: ApplyRequest):
    """Apply previously previewed changes using sophisticated processing."""
    server = await get_server()
    result = await server.apply_changes(request.session_id, request.confirmed_changes)
    return ApplyResponse(**result)


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


async def delete_session(session_id: str):
    """Delete a specific session."""
    server = await get_server()
    session_data = server.session_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    server.session_manager.delete_session(session_id)
    return {"message": f"Session {session_id} deleted successfully"}


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


async def startup_event():
    """Initialize server on startup."""
    try:
        await get_server()  # Initialize the server
        logging.info("JSON Editor REST API server started successfully")
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        raise