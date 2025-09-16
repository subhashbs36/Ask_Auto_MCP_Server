"""Error models for JSON Editor MCP Tool."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error_type: str = Field(..., description="Category of error (validation, llm, session, processing)")
    error_code: str = Field(..., description="Specific error code for programmatic handling")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    suggestions: Optional[List[str]] = Field(default=None, description="Suggested actions to resolve the error")
    
    @field_validator('error_type')
    @classmethod
    def validate_error_type(cls, v):
        """Ensure error type is one of the allowed categories."""
        allowed_types = ["validation", "llm", "session", "processing", "configuration", "network"]
        if v not in allowed_types:
            raise ValueError(f"Error type must be one of: {', '.join(allowed_types)}")
        return v
    
    @field_validator('error_code')
    @classmethod
    def validate_error_code(cls, v):
        """Ensure error code is not empty."""
        if not v or not v.strip():
            raise ValueError("Error code cannot be empty")
        return v.strip().upper()
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        """Ensure message is not empty."""
        if not v or not v.strip():
            raise ValueError("Error message cannot be empty")
        return v.strip()


class ValidationError(ErrorResponse):
    """Specific error model for validation failures."""
    
    error_type: str = Field(default="validation", description="Error type is always validation")
    field_errors: Optional[Dict[str, List[str]]] = Field(
        default=None, 
        description="Field-specific validation errors"
    )


class LLMError(ErrorResponse):
    """Specific error model for LLM service failures."""
    
    error_type: str = Field(default="llm", description="Error type is always llm")
    provider: Optional[str] = Field(default=None, description="LLM provider that failed")
    retry_after: Optional[int] = Field(default=None, description="Seconds to wait before retrying")


class SessionError(ErrorResponse):
    """Specific error model for session-related failures."""
    
    error_type: str = Field(default="session", description="Error type is always session")
    session_id: Optional[str] = Field(default=None, description="Session ID that caused the error")


class ProcessingError(ErrorResponse):
    """Specific error model for document processing failures."""
    
    error_type: str = Field(default="processing", description="Error type is always processing")
    document_size: Optional[int] = Field(default=None, description="Size of document that failed processing")
    processing_stage: Optional[str] = Field(default=None, description="Stage where processing failed")


# Exception classes for raising errors
class JSONEditorException(Exception):
    """Base exception for JSON Editor MCP Tool."""
    
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ProcessingException(JSONEditorException):
    """Exception for document processing failures."""
    
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, details)
        self.error_type = "processing"


class ValidationException(JSONEditorException):
    """Exception for validation failures."""
    
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, details)
        self.error_type = "validation"


class LLMException(JSONEditorException):
    """Exception for LLM service failures."""
    
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, details)
        self.error_type = "llm"


class SessionException(JSONEditorException):
    """Exception for session-related failures."""
    
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, details)
        self.error_type = "session"