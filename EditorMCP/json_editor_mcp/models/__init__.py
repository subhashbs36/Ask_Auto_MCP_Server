"""Data models for JSON Editor MCP Tool."""

from .core import (
    MapEntry,
    ProposedChange,
    AppliedChange,
    ChangePreview,
)

from .requests import (
    PreviewRequest,
    PreviewResponse,
    ApplyRequest,
    ApplyResponse,
)

from .session import (
    PreviewSession,
)

from .errors import (
    ErrorResponse,
    ValidationError,
    LLMError,
    SessionError,
    ProcessingError,
    JSONEditorException,
    ProcessingException,
    ValidationException,
    LLMException,
    SessionException,
)

__all__ = [
    # Core models
    "MapEntry",
    "ProposedChange", 
    "AppliedChange",
    "ChangePreview",
    
    # Request/Response models
    "PreviewRequest",
    "PreviewResponse",
    "ApplyRequest",
    "ApplyResponse",
    
    # Session models
    "PreviewSession",
    
    # Error models
    "ErrorResponse",
    "ValidationError",
    "LLMError",
    "SessionError",
    "ProcessingError",
    
    # Exception classes
    "JSONEditorException",
    "ProcessingException",
    "ValidationException",
    "LLMException",
    "SessionException",
]