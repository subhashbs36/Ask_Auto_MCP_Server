"""Specific error handlers for different service types."""

import logging
from typing import Any, Dict, List, Optional
import json

from ..models.errors import (
    ValidationError, LLMError, SessionError, ProcessingError,
    ValidationException, LLMException, SessionException, ProcessingException
)
from .error_handler import ErrorHandler, RetryConfig

logger = logging.getLogger(__name__)


class ValidationErrorHandler:
    """Specialized error handler for validation operations."""
    
    @staticmethod
    def handle_json_validation_error(error: Exception, document: Any = None) -> ValidationError:
        """Handle JSON document validation errors."""
        
        details = {"original_error": str(error)}
        
        if document is not None:
            try:
                # Try to get document size for context
                doc_str = json.dumps(document) if isinstance(document, (dict, list)) else str(document)
                details["document_size"] = len(doc_str)
            except Exception:
                details["document_size"] = "unknown"
        
        if isinstance(error, json.JSONDecodeError):
            return ValidationError(
                error_code="INVALID_JSON_FORMAT",
                message=f"Invalid JSON format at line {error.lineno}, column {error.colno}: {error.msg}",
                details=details,
                suggestions=[
                    "Check JSON syntax for missing quotes, brackets, or commas",
                    "Validate JSON structure using a JSON validator",
                    "Ensure proper escaping of special characters"
                ]
            )
        
        elif "too large" in str(error).lower() or "size" in str(error).lower():
            return ValidationError(
                error_code="DOCUMENT_TOO_LARGE",
                message="Document exceeds maximum allowed size",
                details=details,
                suggestions=[
                    "Reduce document size by removing unnecessary data",
                    "Split large documents into smaller chunks",
                    "Consider using document streaming for large files"
                ]
            )
        
        elif "nested" in str(error).lower() or "depth" in str(error).lower():
            return ValidationError(
                error_code="DOCUMENT_TOO_NESTED",
                message="Document nesting level exceeds maximum allowed depth",
                details=details,
                suggestions=[
                    "Flatten deeply nested structures",
                    "Reduce nesting levels in the JSON document",
                    "Consider restructuring the document format"
                ]
            )
        
        else:
            return ValidationError(
                error_code="VALIDATION_FAILED",
                message=f"Document validation failed: {str(error)}",
                details=details,
                suggestions=[
                    "Check document format and structure",
                    "Ensure all required fields are present",
                    "Verify data types match expected schema"
                ]
            )
    
    @staticmethod
    def handle_instruction_validation_error(instruction: str, error: Exception) -> ValidationError:
        """Handle instruction validation errors."""
        
        details = {
            "instruction": instruction,
            "instruction_length": len(instruction),
            "original_error": str(error)
        }
        
        if not instruction or not instruction.strip():
            return ValidationError(
                error_code="EMPTY_INSTRUCTION",
                message="Instruction cannot be empty",
                details=details,
                suggestions=[
                    "Provide a clear editing instruction",
                    "Describe what changes you want to make to the JSON",
                    "Use specific language about the modifications needed"
                ]
            )
        
        elif len(instruction) > 10000:  # Arbitrary large instruction limit
            return ValidationError(
                error_code="INSTRUCTION_TOO_LONG",
                message="Instruction exceeds maximum allowed length",
                details=details,
                suggestions=[
                    "Shorten the instruction to be more concise",
                    "Focus on specific changes rather than general descriptions",
                    "Break complex instructions into multiple operations"
                ]
            )
        
        else:
            return ValidationError(
                error_code="INVALID_INSTRUCTION",
                message=f"Invalid instruction format: {str(error)}",
                details=details,
                suggestions=[
                    "Use clear, specific language for editing instructions",
                    "Avoid ambiguous or conflicting requirements",
                    "Provide concrete examples of desired changes"
                ]
            )


class LLMErrorHandler:
    """Specialized error handler for LLM service operations."""
    
    def __init__(self):
        self.provider_retry_configs = {
            "gemini": RetryConfig(max_attempts=3, base_delay=2.0, max_delay=30.0),
            "openai": RetryConfig(max_attempts=3, base_delay=1.0, max_delay=60.0),
            "custom": RetryConfig(max_attempts=2, base_delay=5.0, max_delay=120.0)
        }
    
    def get_retry_config(self, provider: str) -> RetryConfig:
        """Get provider-specific retry configuration."""
        return self.provider_retry_configs.get(provider, RetryConfig())
    
    @staticmethod
    def handle_authentication_error(provider: str, error: Exception) -> LLMError:
        """Handle LLM authentication errors."""
        
        return LLMError(
            error_code="AUTHENTICATION_FAILED",
            message=f"Authentication failed for {provider} LLM service",
            details={
                "provider": provider,
                "original_error": str(error)
            },
            provider=provider,
            suggestions=[
                f"Check {provider} API key configuration",
                "Verify API key has necessary permissions",
                "Ensure API key is not expired or revoked",
                "Check environment variables and configuration files"
            ]
        )
    
    @staticmethod
    def handle_rate_limit_error(provider: str, error: Exception, retry_after: Optional[int] = None) -> LLMError:
        """Handle LLM rate limiting errors."""
        
        # Try to extract retry-after from error message
        if retry_after is None:
            error_str = str(error).lower()
            if "retry after" in error_str:
                try:
                    # Extract number from "retry after X seconds" pattern
                    import re
                    match = re.search(r'retry after (\d+)', error_str)
                    if match:
                        retry_after = int(match.group(1))
                except Exception:
                    pass
            
            # Default retry times by provider
            if retry_after is None:
                retry_after = {"gemini": 60, "openai": 30, "custom": 120}.get(provider, 60)
        
        return LLMError(
            error_code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded for {provider} LLM service",
            details={
                "provider": provider,
                "original_error": str(error)
            },
            provider=provider,
            retry_after=retry_after,
            suggestions=[
                f"Wait {retry_after} seconds before retrying",
                "Consider reducing request frequency",
                "Check rate limit quotas for your API key",
                "Implement request queuing for high-volume usage"
            ]
        )
    
    @staticmethod
    def handle_model_error(provider: str, model: str, error: Exception) -> LLMError:
        """Handle LLM model-specific errors."""
        
        error_str = str(error).lower()
        
        if "not found" in error_str or "invalid model" in error_str:
            return LLMError(
                error_code="INVALID_MODEL",
                message=f"Model '{model}' not found or invalid for {provider}",
                details={
                    "provider": provider,
                    "model": model,
                    "original_error": str(error)
                },
                provider=provider,
                suggestions=[
                    f"Check available models for {provider}",
                    "Verify model name spelling and format",
                    "Ensure model is accessible with your API key",
                    "Update configuration with correct model name"
                ]
            )
        
        elif "context" in error_str or "token" in error_str:
            return LLMError(
                error_code="CONTEXT_LENGTH_EXCEEDED",
                message=f"Input exceeds context length for model '{model}'",
                details={
                    "provider": provider,
                    "model": model,
                    "original_error": str(error)
                },
                provider=provider,
                suggestions=[
                    "Reduce input document size",
                    "Simplify the editing instruction",
                    "Use a model with larger context window",
                    "Split large documents into smaller chunks"
                ]
            )
        
        else:
            return LLMError(
                error_code="MODEL_ERROR",
                message=f"Model error for {provider}/{model}: {str(error)}",
                details={
                    "provider": provider,
                    "model": model,
                    "original_error": str(error)
                },
                provider=provider,
                suggestions=[
                    "Retry the operation",
                    "Check model status and availability",
                    "Try a different model if available",
                    "Contact provider support if issue persists"
                ]
            )
    
    @staticmethod
    def handle_response_parsing_error(provider: str, response: Any, error: Exception) -> LLMError:
        """Handle LLM response parsing errors."""
        
        details = {
            "provider": provider,
            "original_error": str(error)
        }
        
        # Include response details for debugging (truncated)
        if response is not None:
            try:
                response_str = str(response)
                details["response_preview"] = response_str[:500] + "..." if len(response_str) > 500 else response_str
                details["response_type"] = type(response).__name__
            except Exception:
                details["response_preview"] = "Unable to serialize response"
        
        return LLMError(
            error_code="RESPONSE_PARSING_FAILED",
            message=f"Failed to parse response from {provider} LLM service",
            details=details,
            provider=provider,
            suggestions=[
                "Retry the operation with the same input",
                "Check if the LLM service is functioning correctly",
                "Verify response format matches expected schema",
                "Contact support with the error details for debugging"
            ]
        )


class SessionErrorHandler:
    """Specialized error handler for session management operations."""
    
    @staticmethod
    def handle_session_not_found_error(session_id: str) -> SessionError:
        """Handle session not found errors."""
        
        return SessionError(
            error_code="SESSION_NOT_FOUND",
            message=f"Session '{session_id}' not found or expired",
            details={"session_id": session_id},
            session_id=session_id,
            suggestions=[
                "Generate a new preview to create a fresh session",
                "Check that the session ID is correct",
                "Ensure the session hasn't expired",
                "Verify Redis connection and session storage"
            ]
        )
    
    @staticmethod
    def handle_session_expired_error(session_id: str, created_at: Optional[str] = None) -> SessionError:
        """Handle session expiration errors."""
        
        details = {"session_id": session_id}
        if created_at:
            details["created_at"] = created_at
        
        return SessionError(
            error_code="SESSION_EXPIRED",
            message=f"Session '{session_id}' has expired",
            details=details,
            session_id=session_id,
            suggestions=[
                "Generate a new preview to create a fresh session",
                "Complete apply operations promptly after preview",
                "Check session timeout configuration",
                "Consider extending session timeout if needed"
            ]
        )
    
    @staticmethod
    def handle_document_mismatch_error(session_id: str, expected_hash: str, actual_hash: str) -> SessionError:
        """Handle document state mismatch errors."""
        
        return SessionError(
            error_code="DOCUMENT_STATE_MISMATCH",
            message="Document has changed since preview was generated",
            details={
                "session_id": session_id,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash
            },
            session_id=session_id,
            suggestions=[
                "Generate a new preview with the current document",
                "Ensure document hasn't been modified between preview and apply",
                "Check for concurrent modifications to the document",
                "Verify document integrity and consistency"
            ]
        )
    
    @staticmethod
    def handle_redis_connection_error(error: Exception) -> SessionError:
        """Handle Redis connection errors."""
        
        return SessionError(
            error_code="SESSION_STORAGE_UNAVAILABLE",
            message="Session storage is currently unavailable",
            details={"original_error": str(error)},
            suggestions=[
                "Check Redis server status and connectivity",
                "Verify Redis configuration and credentials",
                "Ensure Redis server is running and accessible",
                "Check network connectivity to Redis server"
            ]
        )


class ProcessingErrorHandler:
    """Specialized error handler for document processing operations."""
    
    @staticmethod
    def handle_memory_error(operation: str, document_size: Optional[int] = None) -> ProcessingError:
        """Handle memory exhaustion errors."""
        
        details = {"operation": operation}
        if document_size:
            details["document_size"] = document_size
        
        return ProcessingError(
            error_code="MEMORY_EXHAUSTED",
            message=f"Memory limit exceeded during {operation}",
            details=details,
            document_size=document_size,
            processing_stage=operation,
            suggestions=[
                "Reduce document size before processing",
                "Process document in smaller chunks",
                "Increase available memory for the service",
                "Optimize document structure to reduce memory usage"
            ]
        )
    
    @staticmethod
    def handle_recursion_error(operation: str, max_depth: Optional[int] = None) -> ProcessingError:
        """Handle recursion limit errors."""
        
        details = {"operation": operation}
        if max_depth:
            details["max_depth"] = max_depth
        
        return ProcessingError(
            error_code="RECURSION_LIMIT_EXCEEDED",
            message=f"Document nesting too deep for {operation}",
            details=details,
            processing_stage=operation,
            suggestions=[
                "Flatten deeply nested document structures",
                "Reduce nesting levels in the JSON document",
                "Consider alternative document organization",
                "Process nested sections separately"
            ]
        )
    
    @staticmethod
    def handle_timeout_error(operation: str, timeout_seconds: Optional[int] = None) -> ProcessingError:
        """Handle processing timeout errors."""
        
        details = {"operation": operation}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        
        return ProcessingError(
            error_code="PROCESSING_TIMEOUT",
            message=f"Processing timeout exceeded for {operation}",
            details=details,
            processing_stage=operation,
            suggestions=[
                "Simplify the editing instruction",
                "Reduce document complexity",
                "Increase processing timeout if possible",
                "Break complex operations into smaller steps"
            ]
        )
    
    @staticmethod
    def handle_concurrent_modification_error(operation: str, resource: str) -> ProcessingError:
        """Handle concurrent modification errors."""
        
        return ProcessingError(
            error_code="CONCURRENT_MODIFICATION",
            message=f"Concurrent modification detected during {operation}",
            details={
                "operation": operation,
                "resource": resource
            },
            processing_stage=operation,
            suggestions=[
                "Retry the operation",
                "Ensure exclusive access during processing",
                "Implement proper locking mechanisms",
                "Check for other concurrent operations"
            ]
        )