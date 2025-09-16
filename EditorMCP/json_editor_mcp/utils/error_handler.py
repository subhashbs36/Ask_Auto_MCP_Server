"""Comprehensive error handling utilities for JSON Editor MCP Tool."""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from functools import wraps
import json
from pydantic import ValidationError as PydanticValidationError

from ..models.errors import (
    ErrorResponse, ValidationError, LLMError, SessionError, ProcessingError,
    JSONEditorException, ValidationException, LLMException, 
    SessionException, ProcessingException
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry logic with exponential backoff."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter


class ErrorHandler:
    """Comprehensive error handler with categorization and retry logic."""
    
    def __init__(self, default_retry_config: Optional[RetryConfig] = None):
        self.default_retry_config = default_retry_config or RetryConfig()
        self.error_counts: Dict[str, int] = {}
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
    def categorize_error(self, error: Exception) -> ErrorResponse:
        """Categorize an exception into appropriate error response."""
        
        # Handle known JSON Editor exceptions
        if isinstance(error, JSONEditorException):
            return self._handle_json_editor_exception(error)
        
        # Handle Pydantic validation errors
        if isinstance(error, PydanticValidationError):
            return self._handle_pydantic_validation_error(error)
        
        # Handle JSON parsing errors
        if isinstance(error, (json.JSONDecodeError, ValueError)) and "JSON" in str(error):
            return self._handle_json_parsing_error(error)
        
        # Handle network/connection errors
        if self._is_network_error(error):
            return self._handle_network_error(error)
        
        # Handle memory/resource errors
        if isinstance(error, (MemoryError, RecursionError)):
            return self._handle_resource_error(error)
        
        # Handle timeout errors
        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return self._handle_timeout_error(error)
        
        # Generic processing error for unhandled exceptions
        return self._handle_generic_error(error)
    
    def _handle_json_editor_exception(self, error: JSONEditorException) -> ErrorResponse:
        """Handle known JSON Editor exceptions."""
        
        if isinstance(error, ValidationException):
            return ValidationError(
                error_code=error.error_code,
                message=error.message,
                details=error.details,
                field_errors=error.details.get('field_errors')
            )
        
        elif isinstance(error, LLMException):
            return LLMError(
                error_code=error.error_code,
                message=error.message,
                details=error.details,
                provider=error.details.get('provider'),
                retry_after=error.details.get('retry_after')
            )
        
        elif isinstance(error, SessionException):
            return SessionError(
                error_code=error.error_code,
                message=error.message,
                details=error.details,
                session_id=error.details.get('session_id')
            )
        
        elif isinstance(error, ProcessingException):
            return ProcessingError(
                error_code=error.error_code,
                message=error.message,
                details=error.details,
                document_size=error.details.get('document_size'),
                processing_stage=error.details.get('processing_stage')
            )
        
        # Fallback for base JSONEditorException
        return ErrorResponse(
            error_type="processing",
            error_code=error.error_code,
            message=error.message,
            details=error.details
        )
    
    def _handle_pydantic_validation_error(self, error: PydanticValidationError) -> ValidationError:
        """Handle Pydantic validation errors."""
        
        field_errors = {}
        for err in error.errors():
            field_path = ".".join(str(loc) for loc in err['loc'])
            if field_path not in field_errors:
                field_errors[field_path] = []
            field_errors[field_path].append(err['msg'])
        
        return ValidationError(
            error_code="VALIDATION_FAILED",
            message="Request validation failed",
            details={"validation_errors": error.errors()},
            field_errors=field_errors,
            suggestions=[
                "Check the request format and ensure all required fields are provided",
                "Verify that field types match the expected schema"
            ]
        )
    
    def _handle_json_parsing_error(self, error: Exception) -> ValidationError:
        """Handle JSON parsing errors."""
        
        return ValidationError(
            error_code="INVALID_JSON",
            message=f"Invalid JSON document: {str(error)}",
            details={"original_error": str(error)},
            suggestions=[
                "Ensure the document is valid JSON format",
                "Check for missing quotes, brackets, or commas",
                "Use a JSON validator to verify document structure"
            ]
        )
    
    def _handle_network_error(self, error: Exception) -> LLMError:
        """Handle network-related errors."""
        
        return LLMError(
            error_code="NETWORK_ERROR",
            message=f"Network error occurred: {str(error)}",
            details={"original_error": str(error)},
            retry_after=30,
            suggestions=[
                "Check network connectivity",
                "Verify LLM service endpoint is accessible",
                "Check firewall and proxy settings"
            ]
        )
    
    def _handle_resource_error(self, error: Exception) -> ProcessingError:
        """Handle memory and resource errors."""
        
        return ProcessingError(
            error_code="RESOURCE_EXHAUSTED",
            message=f"Resource limit exceeded: {str(error)}",
            details={"original_error": str(error)},
            suggestions=[
                "Reduce document size",
                "Simplify the editing instruction",
                "Process document in smaller chunks"
            ]
        )
    
    def _handle_timeout_error(self, error: Exception) -> LLMError:
        """Handle timeout errors."""
        
        return LLMError(
            error_code="TIMEOUT",
            message=f"Operation timed out: {str(error)}",
            details={"original_error": str(error)},
            retry_after=60,
            suggestions=[
                "Retry the operation",
                "Simplify the editing instruction",
                "Check LLM service status"
            ]
        )
    
    def _handle_generic_error(self, error: Exception) -> ProcessingError:
        """Handle unhandled exceptions."""
        
        error_id = f"generic_{int(time.time())}"
        logger.error(f"Unhandled error [{error_id}]: {type(error).__name__}: {str(error)}", 
                    exc_info=True)
        
        return ProcessingError(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details={
                "error_id": error_id,
                "error_type": type(error).__name__,
                "original_error": str(error)
            },
            suggestions=[
                "Retry the operation",
                "Contact support if the problem persists",
                f"Reference error ID: {error_id}"
            ]
        )
    
    def _is_network_error(self, error: Exception) -> bool:
        """Check if error is network-related."""
        
        network_error_types = [
            "ConnectionError", "ConnectTimeout", "ReadTimeout",
            "HTTPError", "RequestException", "URLError"
        ]
        
        error_type = type(error).__name__
        return any(net_err in error_type for net_err in network_error_types)
    
    async def with_retry(
        self,
        func: Callable[..., T],
        *args,
        retry_config: Optional[RetryConfig] = None,
        error_context: Optional[str] = None,
        **kwargs
    ) -> T:
        """Execute function with retry logic and exponential backoff."""
        
        config = retry_config or self.default_retry_config
        context = error_context or func.__name__
        
        last_error = None
        
        for attempt in range(config.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as error:
                last_error = error
                
                # Don't retry validation errors
                if isinstance(error, (ValidationException, PydanticValidationError)):
                    raise
                
                # Check circuit breaker
                if self._is_circuit_open(context):
                    raise LLMException(
                        "CIRCUIT_BREAKER_OPEN",
                        f"Circuit breaker is open for {context}",
                        {"context": context, "attempt": attempt + 1}
                    )
                
                # Log retry attempt
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed for {context}: {str(error)}"
                )
                
                # Don't wait after the last attempt
                if attempt < config.max_attempts - 1:
                    delay = self._calculate_delay(attempt, config)
                    logger.info(f"Retrying {context} in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                
                # Update error counts and circuit breaker
                self._update_error_tracking(context, error)
        
        # All attempts failed
        self._trigger_circuit_breaker(context)
        
        if last_error:
            raise last_error
        else:
            raise ProcessingException(
                "MAX_RETRIES_EXCEEDED",
                f"Maximum retry attempts ({config.max_attempts}) exceeded for {context}"
            )
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for exponential backoff with jitter."""
        
        delay = config.base_delay * (config.backoff_factor ** attempt)
        delay = min(delay, config.max_delay)
        
        if config.jitter:
            # Add random jitter (±25%)
            import random
            jitter_factor = 0.75 + (random.random() * 0.5)  # 0.75 to 1.25
            delay *= jitter_factor
        
        return delay
    
    def _update_error_tracking(self, context: str, error: Exception):
        """Update error counts for circuit breaker logic."""
        
        self.error_counts[context] = self.error_counts.get(context, 0) + 1
        
        # Reset success count
        if context in self.circuit_breakers:
            self.circuit_breakers[context]["consecutive_successes"] = 0
    
    def _is_circuit_open(self, context: str) -> bool:
        """Check if circuit breaker is open for given context."""
        
        if context not in self.circuit_breakers:
            return False
        
        breaker = self.circuit_breakers[context]
        
        # Check if circuit is still open
        if breaker["state"] == "open":
            if time.time() - breaker["opened_at"] > breaker["timeout"]:
                # Move to half-open state
                breaker["state"] = "half-open"
                logger.info(f"Circuit breaker for {context} moved to half-open state")
                return False
            return True
        
        return False
    
    def _trigger_circuit_breaker(self, context: str):
        """Trigger circuit breaker for given context."""
        
        error_count = self.error_counts.get(context, 0)
        
        # Trigger circuit breaker after 5 consecutive errors
        if error_count >= 5:
            self.circuit_breakers[context] = {
                "state": "open",
                "opened_at": time.time(),
                "timeout": 300,  # 5 minutes
                "consecutive_successes": 0
            }
            logger.warning(f"Circuit breaker opened for {context} after {error_count} errors")
    
    def record_success(self, context: str):
        """Record successful operation for circuit breaker logic."""
        
        # Reset error count on success
        if context in self.error_counts:
            self.error_counts[context] = 0
        
        # Handle circuit breaker state
        if context in self.circuit_breakers:
            breaker = self.circuit_breakers[context]
            
            if breaker["state"] == "half-open":
                breaker["consecutive_successes"] += 1
                
                # Close circuit after 3 consecutive successes
                if breaker["consecutive_successes"] >= 3:
                    del self.circuit_breakers[context]
                    logger.info(f"Circuit breaker closed for {context}")


def with_error_handling(
    error_handler: Optional[ErrorHandler] = None,
    retry_config: Optional[RetryConfig] = None,
    context: Optional[str] = None
):
    """Decorator for automatic error handling and retry logic."""
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            handler = error_handler or ErrorHandler()
            func_context = context or func.__name__
            
            try:
                result = await handler.with_retry(
                    func, *args, 
                    retry_config=retry_config,
                    error_context=func_context,
                    **kwargs
                )
                handler.record_success(func_context)
                return result
                
            except Exception as error:
                error_response = handler.categorize_error(error)
                logger.error(f"Error in {func_context}: {error_response.message}")
                raise error
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            handler = error_handler or ErrorHandler()
            func_context = context or func.__name__
            
            try:
                # For sync functions, we can't use async retry
                result = func(*args, **kwargs)
                handler.record_success(func_context)
                return result
                
            except Exception as error:
                error_response = handler.categorize_error(error)
                logger.error(f"Error in {func_context}: {error_response.message}")
                raise error
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global error handler instance
default_error_handler = ErrorHandler()


def handle_error(error: Exception) -> ErrorResponse:
    """Convenience function to handle errors using default handler."""
    return default_error_handler.categorize_error(error)


def create_graceful_degradation_response(
    service_name: str,
    fallback_message: str,
    suggestions: Optional[List[str]] = None
) -> ErrorResponse:
    """Create a graceful degradation response when services are unavailable."""
    
    return ErrorResponse(
        error_type="llm",
        error_code="SERVICE_UNAVAILABLE",
        message=f"{service_name} is currently unavailable. {fallback_message}",
        details={"service": service_name},
        suggestions=suggestions or [
            f"Retry the operation when {service_name} is available",
            "Check service status and configuration",
            "Contact support if the problem persists"
        ]
    )