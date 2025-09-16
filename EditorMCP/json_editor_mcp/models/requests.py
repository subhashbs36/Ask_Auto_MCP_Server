"""Request and response models for JSON Editor MCP Tool."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from .core import ProposedChange, AppliedChange


class PreviewRequest(BaseModel):
    """Request model for json_editor_preview tool."""
    
    document: Dict[str, Any] = Field(..., description="JSON document to edit")
    instruction: str = Field(..., description="Natural language editing instruction")
    
    @field_validator('instruction')
    @classmethod
    def validate_instruction(cls, v):
        """Ensure instruction is not empty and has reasonable length."""
        if not v or not v.strip():
            raise ValueError("Instruction cannot be empty")
        
        instruction = v.strip()
        if len(instruction) < 3:
            raise ValueError("Instruction must be at least 3 characters long")
        if len(instruction) > 5000:
            raise ValueError("Instruction cannot exceed 5000 characters")
        
        return instruction
    
    @field_validator('document')
    @classmethod
    def validate_document(cls, v):
        """Ensure document is not empty."""
        if not v:
            raise ValueError("Document cannot be empty")
        return v


class PreviewResponse(BaseModel):
    """Response model for json_editor_preview tool."""
    
    session_id: str = Field(..., description="Unique session identifier for applying changes")
    changes: List[ProposedChange] = Field(..., description="List of proposed changes")
    message: str = Field(..., description="Human-readable message about the preview")
    status: str = Field(..., description="Status of the preview operation")
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v):
        """Ensure session ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Ensure status is one of the allowed values."""
        allowed_statuses = ["success", "error", "warning", "no_changes"]
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v


class ApplyRequest(BaseModel):
    """Request model for json_editor_apply tool."""
    
    session_id: str = Field(..., description="Session ID from preview operation")
    confirmed_changes: Optional[List[str]] = Field(
        default=None, 
        description="List of change IDs to apply. If None, all changes are applied"
    )
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v):
        """Ensure session ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()
    
    @field_validator('confirmed_changes')
    @classmethod
    def validate_confirmed_changes(cls, v):
        """Ensure confirmed changes list is valid if provided."""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("Confirmed changes must be a list")
            for change_id in v:
                if not isinstance(change_id, str) or not change_id.strip():
                    raise ValueError("All change IDs must be non-empty strings")
        return v


class ApplyResponse(BaseModel):
    """Response model for json_editor_apply tool."""
    
    modified_document: Dict[str, Any] = Field(..., description="The modified JSON document")
    applied_changes: List[AppliedChange] = Field(..., description="List of changes that were applied")
    message: str = Field(..., description="Human-readable message about the apply operation")
    status: str = Field(..., description="Status of the apply operation")
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Ensure status is one of the allowed values."""
        allowed_statuses = ["success", "error", "partial_success", "no_changes"]
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v
    
    @field_validator('modified_document')
    @classmethod
    def validate_modified_document(cls, v):
        """Ensure modified document is not empty."""
        if not v:
            raise ValueError("Modified document cannot be empty")
        return v