"""Core data models for JSON Editor MCP Tool."""

from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import uuid


class MapEntry(BaseModel):
    """Represents a single entry in the JSON-to-map conversion."""
    
    id: str = Field(..., description="Unique identifier for the map entry")
    path: List[str] = Field(..., description="JSON path to the value as list of keys")
    value: str = Field(..., description="String representation of the JSON value")
    
    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        """Ensure ID is not empty."""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        """Ensure path is not empty and contains valid keys."""
        if not v:
            raise ValueError("Path cannot be empty")
        for key in v:
            if not isinstance(key, str):
                raise ValueError("All path elements must be strings")
        return v


class ProposedChange(BaseModel):
    """Represents a proposed change to a JSON document."""
    
    id: str = Field(..., description="Unique identifier for the proposed change")
    path: List[str] = Field(..., description="JSON path to the value being changed")
    current_value: str = Field(..., description="Current value at the path")
    proposed_value: str = Field(..., description="Proposed new value")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score for the change")
    
    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        """Ensure ID is not empty."""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        """Ensure path is not empty and contains valid keys."""
        if not v:
            raise ValueError("Path cannot be empty")
        for key in v:
            if not isinstance(key, str):
                raise ValueError("All path elements must be strings")
        return v


class AppliedChange(BaseModel):
    """Represents a change that has been applied to a JSON document."""
    
    id: str = Field(..., description="Unique identifier for the applied change")
    path: List[str] = Field(..., description="JSON path to the value that was changed")
    old_value: str = Field(..., description="Previous value before the change")
    new_value: str = Field(..., description="New value after the change")
    applied_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Timestamp when change was applied")
    
    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        """Ensure ID is not empty."""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        """Ensure path is not empty and contains valid keys."""
        if not v:
            raise ValueError("Path cannot be empty")
        for key in v:
            if not isinstance(key, str):
                raise ValueError("All path elements must be strings")
        return v


class ChangePreview(BaseModel):
    """Represents a preview of changes with session information."""
    
    changes: List[ProposedChange] = Field(..., description="List of proposed changes")
    session_id: str = Field(..., description="Unique session identifier")
    document_hash: str = Field(..., description="Hash of the original document")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When the preview was created")
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v):
        """Ensure session ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()
    
    @field_validator('document_hash')
    @classmethod
    def validate_document_hash(cls, v):
        """Ensure document hash is not empty."""
        if not v or not v.strip():
            raise ValueError("Document hash cannot be empty")
        return v.strip()