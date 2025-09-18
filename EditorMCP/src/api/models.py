"""
Pydantic models for the JSON Editor REST API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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