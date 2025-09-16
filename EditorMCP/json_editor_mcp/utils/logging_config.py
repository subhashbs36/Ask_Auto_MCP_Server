"""Logging configuration for comprehensive error tracking and debugging."""

import logging
import logging.handlers
import sys
import json
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class ErrorTrackingHandler(logging.Handler):
    """Custom handler for tracking error patterns and metrics."""
    
    def __init__(self):
        super().__init__()
        self.error_counts: Dict[str, int] = {}
        self.error_patterns: Dict[str, int] = {}
        self.recent_errors: list = []
        self.max_recent_errors = 100
    
    def emit(self, record: logging.LogRecord):
        """Process log record for error tracking."""
        
        if record.levelno >= logging.ERROR:
            # Track error counts by logger
            logger_name = record.name
            self.error_counts[logger_name] = self.error_counts.get(logger_name, 0) + 1
            
            # Track error patterns by message
            message_pattern = self._extract_pattern(record.getMessage())
            self.error_patterns[message_pattern] = self.error_patterns.get(message_pattern, 0) + 1
            
            # Keep recent errors for analysis
            error_info = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "logger": logger_name,
                "level": record.levelname,
                "message": record.getMessage(),
                "pattern": message_pattern
            }
            
            if record.exc_info:
                error_info["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            
            self.recent_errors.append(error_info)
            
            # Keep only recent errors
            if len(self.recent_errors) > self.max_recent_errors:
                self.recent_errors = self.recent_errors[-self.max_recent_errors:]
    
    def _extract_pattern(self, message: str) -> str:
        """Extract error pattern from message for grouping."""
        
        # Remove specific values to group similar errors
        import re
        
        # Replace UUIDs, session IDs, timestamps, etc.
        pattern = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 
                        '<UUID>', message, flags=re.IGNORECASE)
        pattern = re.sub(r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', pattern)
        pattern = re.sub(r'\b\d+\b', '<NUMBER>', pattern)
        pattern = re.sub(r'\b[a-zA-Z0-9_]{20,}\b', '<LONG_ID>', pattern)
        
        return pattern
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of tracked errors."""
        
        return {
            "total_errors_by_logger": dict(self.error_counts),
            "error_patterns": dict(sorted(self.error_patterns.items(), 
                                        key=lambda x: x[1], reverse=True)[:10]),
            "recent_error_count": len(self.recent_errors),
            "most_recent_errors": self.recent_errors[-5:] if self.recent_errors else []
        }


class DebugInfoLogger:
    """Logger for detailed debugging information."""
    
    def __init__(self, logger_name: str = "json_editor_debug"):
        self.logger = logging.getLogger(logger_name)
    
    def log_request_details(self, operation: str, request_data: Dict[str, Any], 
                           request_id: Optional[str] = None):
        """Log detailed request information for debugging."""
        
        debug_info = {
            "operation": operation,
            "request_id": request_id or self._generate_request_id(),
            "request_size": len(str(request_data)),
            "has_document": "document" in request_data,
            "has_instruction": "instruction" in request_data
        }
        
        if "document" in request_data:
            doc = request_data["document"]
            if isinstance(doc, dict):
                debug_info["document_keys"] = list(doc.keys())
                debug_info["document_depth"] = self._calculate_depth(doc)
        
        if "instruction" in request_data:
            instruction = request_data["instruction"]
            debug_info["instruction_length"] = len(instruction)
            debug_info["instruction_words"] = len(instruction.split())
        
        self.logger.debug("Request details", extra=debug_info)
    
    def log_llm_interaction(self, provider: str, model: str, prompt_size: int, 
                           response_size: Optional[int] = None, duration: Optional[float] = None,
                           error: Optional[Exception] = None):
        """Log LLM service interaction details."""
        
        interaction_info = {
            "provider": provider,
            "model": model,
            "prompt_size": prompt_size,
            "response_size": response_size,
            "duration_seconds": duration,
            "success": error is None
        }
        
        if error:
            interaction_info["error_type"] = type(error).__name__
            interaction_info["error_message"] = str(error)
        
        level = logging.DEBUG if error is None else logging.ERROR
        self.logger.log(level, "LLM interaction", extra=interaction_info)
    
    def log_processing_stage(self, stage: str, document_size: Optional[int] = None,
                           changes_count: Optional[int] = None, duration: Optional[float] = None):
        """Log document processing stage information."""
        
        stage_info = {
            "processing_stage": stage,
            "document_size": document_size,
            "changes_count": changes_count,
            "duration_seconds": duration
        }
        
        self.logger.debug("Processing stage", extra=stage_info)
    
    def log_session_operation(self, operation: str, session_id: str, 
                             success: bool, details: Optional[Dict[str, Any]] = None):
        """Log session management operation details."""
        
        session_info = {
            "session_operation": operation,
            "session_id": session_id,
            "success": success
        }
        
        if details:
            session_info.update(details)
        
        level = logging.DEBUG if success else logging.WARNING
        self.logger.log(level, "Session operation", extra=session_info)
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID for tracking."""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _calculate_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of an object."""
        
        if current_depth > 50:  # Prevent infinite recursion
            return current_depth
        
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_depth(value, current_depth + 1) for value in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._calculate_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_json_logging: bool = False,
    enable_error_tracking: bool = True,
    enable_debug_logging: bool = False
) -> Dict[str, Any]:
    """Set up comprehensive logging configuration."""
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    if enable_json_logging:
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5  # 10MB files, keep 5 backups
        )
        file_handler.setLevel(numeric_level)
        
        if enable_json_logging:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
        
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Error tracking handler
    error_tracker = None
    if enable_error_tracking:
        error_tracker = ErrorTrackingHandler()
        error_tracker.setLevel(logging.WARNING)
        root_logger.addHandler(error_tracker)
    
    # Debug logger
    debug_logger = None
    if enable_debug_logging:
        debug_logger = DebugInfoLogger()
    
    # Set specific logger levels
    logging.getLogger("json_editor_mcp").setLevel(numeric_level)
    logging.getLogger("mcp").setLevel(logging.WARNING)  # Reduce MCP library noise
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Reduce HTTP client noise
    logging.getLogger("redis").setLevel(logging.WARNING)  # Reduce Redis noise
    
    return {
        "error_tracker": error_tracker,
        "debug_logger": debug_logger,
        "log_level": log_level,
        "handlers_count": len(root_logger.handlers)
    }


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


def log_performance_metrics(logger: logging.Logger, operation: str, 
                          duration: float, **metrics):
    """Log performance metrics for operations."""
    
    perf_info = {
        "operation": operation,
        "duration_seconds": duration,
        **metrics
    }
    
    logger.info("Performance metrics", extra=perf_info)


def log_error_with_context(logger: logging.Logger, error: Exception, 
                          context: Dict[str, Any], operation: str):
    """Log error with comprehensive context information."""
    
    error_info = {
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
        **context
    }
    
    logger.error(f"Error in {operation}: {str(error)}", extra=error_info, exc_info=True)