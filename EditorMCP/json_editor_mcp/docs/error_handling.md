# Comprehensive Error Handling System

## Overview

The JSON Editor MCP Tool implements a comprehensive error handling system that provides:

- **Categorized Error Responses**: Structured error responses with specific error codes and types
- **Retry Logic with Exponential Backoff**: Automatic retry for transient failures
- **Circuit Breaker Pattern**: Prevents cascading failures when services are unavailable
- **Graceful Degradation**: Fallback behavior when services are temporarily unavailable
- **Detailed Logging and Debugging**: Comprehensive logging for troubleshooting and monitoring
- **Service-Specific Error Handlers**: Specialized handling for different service types

## Error Categories

### 1. Validation Errors (`validation`)
- **INVALID_JSON_FORMAT**: JSON parsing failures with line/column information
- **DOCUMENT_TOO_LARGE**: Document exceeds size limits
- **DOCUMENT_TOO_NESTED**: Document nesting exceeds depth limits
- **EMPTY_INSTRUCTION**: Missing or empty editing instructions
- **INSTRUCTION_TOO_LONG**: Instruction exceeds length limits
- **MISSING_DOCUMENT**: Required document field missing
- **MISSING_INSTRUCTION**: Required instruction field missing

### 2. LLM Service Errors (`llm`)
- **AUTHENTICATION_FAILED**: API key or authentication issues
- **RATE_LIMIT_EXCEEDED**: Provider rate limits exceeded
- **INVALID_MODEL**: Model not found or inaccessible
- **CONTEXT_LENGTH_EXCEEDED**: Input exceeds model context window
- **RESPONSE_PARSING_FAILED**: Unable to parse LLM response
- **TIMEOUT**: LLM service timeout
- **NETWORK_ERROR**: Network connectivity issues

### 3. Session Errors (`session`)
- **SESSION_NOT_FOUND**: Session ID not found or expired
- **SESSION_EXPIRED**: Session has exceeded TTL
- **DOCUMENT_STATE_MISMATCH**: Document changed since preview
- **SESSION_STORAGE_UNAVAILABLE**: Redis connection issues
- **SESSION_CREATION_FAILED**: Unable to create new session

### 4. Processing Errors (`processing`)
- **MEMORY_EXHAUSTED**: Memory limits exceeded
- **RECURSION_LIMIT_EXCEEDED**: Document nesting too deep
- **PROCESSING_TIMEOUT**: Processing operation timeout
- **CONCURRENT_MODIFICATION**: Concurrent access conflicts
- **MAP_CONVERSION_FAILED**: JSON to map conversion failure
- **NO_EDITABLE_CONTENT**: No editable text nodes found
- **INTERNAL_ERROR**: Unexpected system errors

## Error Response Format

All errors follow a standardized format:

```json
{
  "error": {
    "error_type": "validation|llm|session|processing",
    "error_code": "SPECIFIC_ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "additional_context": "value",
      "debug_info": "..."
    },
    "suggestions": [
      "Actionable suggestion 1",
      "Actionable suggestion 2"
    ]
  },
  "status": "error"
}
```

### Service-Specific Error Fields

**LLM Errors** include:
- `provider`: LLM service provider name
- `retry_after`: Seconds to wait before retrying

**Session Errors** include:
- `session_id`: The problematic session ID

**Processing Errors** include:
- `document_size`: Size of document being processed
- `processing_stage`: Stage where error occurred

**Validation Errors** include:
- `field_errors`: Field-specific validation failures

## Retry Logic and Circuit Breaker

### Retry Configuration

```python
class RetryConfig:
    max_attempts: int = 3          # Maximum retry attempts
    base_delay: float = 1.0        # Base delay in seconds
    max_delay: float = 60.0        # Maximum delay cap
    backoff_factor: float = 2.0    # Exponential backoff multiplier
    jitter: bool = True            # Add random jitter to delays
```

### Provider-Specific Retry Settings

- **Gemini**: 3 attempts, 2s base delay, 30s max delay
- **OpenAI**: 3 attempts, 1s base delay, 60s max delay  
- **Custom**: 2 attempts, 5s base delay, 120s max delay

### Circuit Breaker Logic

- **Trigger**: Opens after 5 consecutive failures
- **Timeout**: 5 minutes in open state
- **Half-Open**: Allows limited requests to test recovery
- **Close**: Closes after 3 consecutive successes in half-open state

## Usage Examples

### Basic Error Handling

```python
from json_editor_mcp.utils.error_handler import ErrorHandler

error_handler = ErrorHandler()

try:
    # Some operation that might fail
    result = risky_operation()
except Exception as e:
    error_response = error_handler.categorize_error(e)
    return {"error": error_response.model_dump(), "status": "error"}
```

### Using the Decorator

```python
from json_editor_mcp.utils.error_handler import with_error_handling, RetryConfig

@with_error_handling(
    retry_config=RetryConfig(max_attempts=3, base_delay=2.0),
    context="llm_api_call"
)
async def call_llm_api(prompt: str):
    # This function will automatically retry on failure
    return await llm_client.generate(prompt)
```

### Service-Specific Error Handling

```python
from json_editor_mcp.utils.service_error_handlers import LLMErrorHandler

llm_handler = LLMErrorHandler()

try:
    response = await gemini_api.generate(prompt)
except Exception as e:
    if "authentication" in str(e).lower():
        error_response = llm_handler.handle_authentication_error("gemini", e)
    elif "rate limit" in str(e).lower():
        error_response = llm_handler.handle_rate_limit_error("gemini", e)
    else:
        error_response = llm_handler.handle_model_error("gemini", model_name, e)
    
    raise LLMException(error_response.error_code, error_response.message, error_response.details)
```

## Logging and Monitoring

### Structured Logging

```python
from json_editor_mcp.utils.logging_config import setup_logging, get_logger

# Setup logging with error tracking
config = setup_logging(
    log_level="INFO",
    log_file="logs/json_editor.log",
    enable_json_logging=True,
    enable_error_tracking=True,
    enable_debug_logging=True
)

logger = get_logger(__name__)
```

### Performance Metrics

```python
from json_editor_mcp.utils.logging_config import log_performance_metrics

log_performance_metrics(
    logger, 
    "preview_generation", 
    duration_seconds,
    document_size=len(document),
    changes_count=len(changes)
)
```

### Error Context Logging

```python
from json_editor_mcp.utils.logging_config import log_error_with_context

log_error_with_context(
    logger, 
    exception,
    {"operation": "preview", "session_id": session_id},
    "handle_preview_request"
)
```

### Debug Information

```python
from json_editor_mcp.utils.logging_config import DebugInfoLogger

debug_logger = DebugInfoLogger()

# Log request details
debug_logger.log_request_details("preview", request_data, request_id)

# Log LLM interactions
debug_logger.log_llm_interaction(
    provider="gemini",
    model="gemini-pro",
    prompt_size=len(prompt),
    response_size=len(response),
    duration=processing_time
)

# Log processing stages
debug_logger.log_processing_stage(
    "json_to_map_conversion",
    document_size=doc_size,
    changes_count=changes_count,
    duration=stage_duration
)
```

## Graceful Degradation

### Service Unavailable Responses

```python
from json_editor_mcp.utils.error_handler import create_graceful_degradation_response

# When LLM service is unavailable
response = create_graceful_degradation_response(
    "Gemini LLM Service",
    "Please try again when the service is available.",
    [
        "Check Gemini service status",
        "Verify API key and configuration", 
        "Try using a different LLM provider"
    ]
)
```

### Fallback Behavior

The system implements graceful degradation by:

1. **Detecting Service Failures**: Circuit breaker monitors service health
2. **Providing Clear Messages**: Users get actionable error messages
3. **Suggesting Alternatives**: Error responses include recovery suggestions
4. **Maintaining State**: Sessions persist during temporary service outages
5. **Automatic Recovery**: Services automatically resume when available

## Error Tracking and Analytics

### Error Metrics

The error tracking handler collects:

- **Error Counts by Logger**: Track which components have the most errors
- **Error Patterns**: Group similar errors for trend analysis
- **Recent Errors**: Keep history of recent failures for debugging
- **Error Rates**: Monitor error frequency over time

### Accessing Error Summary

```python
# Get error tracking summary
error_tracker = config["error_tracker"]
summary = error_tracker.get_error_summary()

print(f"Total errors by component: {summary['total_errors_by_logger']}")
print(f"Most common error patterns: {summary['error_patterns']}")
print(f"Recent errors: {summary['most_recent_errors']}")
```

## Best Practices

### 1. Use Appropriate Error Types
- Use `ValidationException` for input validation failures
- Use `LLMException` for LLM service issues
- Use `SessionException` for session management problems
- Use `ProcessingException` for document processing failures

### 2. Provide Actionable Error Messages
- Include specific details about what went wrong
- Suggest concrete steps to resolve the issue
- Reference relevant documentation or configuration

### 3. Implement Proper Retry Logic
- Don't retry validation errors (they won't succeed)
- Use exponential backoff for network errors
- Respect rate limits with appropriate delays
- Implement circuit breakers for cascading failures

### 4. Log Comprehensive Context
- Include operation context in error logs
- Log performance metrics for monitoring
- Use structured logging for better analysis
- Include request IDs for tracing

### 5. Handle Edge Cases
- Large documents that exceed memory limits
- Deeply nested JSON that causes recursion errors
- Network timeouts and connectivity issues
- Concurrent access and race conditions

## Configuration

### Error Handler Configuration

```python
# Custom retry configuration
retry_config = RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    max_delay=120.0,
    backoff_factor=2.0,
    jitter=True
)

# Initialize with custom config
error_handler = ErrorHandler(default_retry_config=retry_config)
```

### Logging Configuration

```python
# Production logging setup
setup_logging(
    log_level="INFO",
    log_file="/var/log/json_editor/app.log",
    enable_json_logging=True,
    enable_error_tracking=True,
    enable_debug_logging=False
)

# Development logging setup  
setup_logging(
    log_level="DEBUG",
    enable_json_logging=False,
    enable_error_tracking=True,
    enable_debug_logging=True
)
```

This comprehensive error handling system ensures the JSON Editor MCP Tool is robust, debuggable, and provides excellent user experience even when things go wrong.