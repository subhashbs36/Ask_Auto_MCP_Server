"""Session models for Redis storage."""

from datetime import datetime, UTC
from typing import Any, Dict, List
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .core import ProposedChange


class PreviewSession(BaseModel):
    """Model for storing preview session data in Redis."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    session_id: str = Field(..., description="Unique session identifier")
    document: Dict[str, Any] = Field(..., description="Original JSON document")
    document_hash: str = Field(..., description="Hash of the original document for verification")
    proposed_changes: List[ProposedChange] = Field(..., description="List of proposed changes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When the session was created")
    
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
    
    @field_validator('document')
    @classmethod
    def validate_document(cls, v):
        """Ensure document is not empty."""
        if not v:
            raise ValueError("Document cannot be empty")
        return v