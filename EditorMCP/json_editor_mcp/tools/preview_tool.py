"""Preview tool for JSON Editor MCP Tool."""

import logging
import time
from typing import Any, Dict, List, Optional

from ..config.models import ServerConfig
from ..models.requests import PreviewRequest, PreviewResponse
from ..models.core import MapEntry, ProposedChange
from ..models.errors import (
    ErrorResponse, ValidationException, LLMException, 
    SessionException, ProcessingException
)
from ..services.factory import create_llm_service
from ..services.json_processor import JSONProcessor
from ..services.hybrid_session_manager import HybridSessionManager
from ..services.interface import LLMServiceInterface
from ..utils.error_handler import ErrorHandler, with_error_handling
from ..utils.service_error_handlers import (
    ValidationErrorHandler, LLMErrorHandler, SessionErrorHandler, ProcessingErrorHandler
)
from ..utils.logging_config import (
    get_logger, DebugInfoLogger, log_performance_metrics, log_error_with_context
)
from ..utils.monitoring_config import get_monitoring_manager
from ..utils.llm_monitoring import track_llm_request


class PreviewTool:
    """Tool for handling json_editor_preview requests."""
    
    def __init__(self, config: ServerConfig, session_manager=None):
        """Initialize the preview tool with configuration.
        
        Args:
            config: Server configuration containing all service settings
            session_manager: Optional shared session manager instance
        """
        self.config = config
        self.logger = get_logger(__name__)
        self.debug_logger = DebugInfoLogger("preview_tool_debug")
        
        # Initialize error handlers
        self.error_handler = ErrorHandler()
        self.validation_handler = ValidationErrorHandler()
        self.llm_handler = LLMErrorHandler()
        self.session_handler = SessionErrorHandler()
        self.processing_handler = ProcessingErrorHandler()
        
        # Initialize services
        self.json_processor = JSONProcessor()
        
        # Use shared session manager if provided, otherwise create new one
        if session_manager:
            self.session_manager = session_manager
        else:
            self.session_manager = HybridSessionManager(
                redis_config=config.redis_config,
                session_ttl=config.session_ttl,
                prefer_redis=getattr(config, 'prefer_redis', False)
            )
        self.llm_service: Optional[LLMServiceInterface] = None
        
        # Initialize LLM service with error handling
        try:
            self.llm_service = create_llm_service(config.llm_config)
            self.logger.info(f"Initialized LLM service: {self.llm_service.get_provider_name()}")
        except Exception as e:
            error_response = self.error_handler.categorize_error(e)
            self.logger.error(f"Failed to initialize LLM service: {error_response.message}")
            raise
    
    @with_error_handling(context="preview_tool_handle_preview")
    async def handle_preview(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a json_editor_preview request.
        
        Args:
            request_data: Raw request data from MCP client
            
        Returns:
            Dictionary containing the preview response or error
        """
        start_time = time.time()
        request_id = self.debug_logger._generate_request_id()
        
        # Record request start for monitoring
        monitoring_manager = get_monitoring_manager()
        if monitoring_manager:
            monitoring_manager.record_request_start("preview", request_id)
        
        try:
            # Log request details for debugging
            self.debug_logger.log_request_details("preview", request_data, request_id)
            
            # Validate and parse request
            request = self._validate_request(request_data)
            
            # Validate document size
            self._validate_document_size(request.document)
            
            # Convert JSON to map format
            map_entries = self._convert_to_map(request.document)
            
            # Log processing stage
            self.debug_logger.log_processing_stage(
                "json_to_map_conversion",
                document_size=len(str(request.document)),
                changes_count=len(map_entries)
            )
            
            # Get proposed changes from LLM
            proposed_changes = await self._get_proposed_changes(map_entries, request.instruction)
            
            # Handle case where no changes are needed
            if not proposed_changes:
                duration = time.time() - start_time
                log_performance_metrics(
                    self.logger, "preview_no_changes", duration,
                    request_id=request_id, map_entries_count=len(map_entries)
                )
                return self._create_no_changes_response(request.instruction)
            
            # Create session for the preview
            session_id = self._create_preview_session(request.document, proposed_changes)
            
            # Create and return successful response
            response = PreviewResponse(
                session_id=session_id,
                changes=proposed_changes,
                message=self._generate_preview_message(proposed_changes),
                status="success"
            )
            
            duration = time.time() - start_time
            log_performance_metrics(
                self.logger, "preview_success", duration,
                request_id=request_id,
                map_entries_count=len(map_entries),
                changes_count=len(proposed_changes),
                session_id=session_id
            )
            
            self.logger.info(f"Preview generated successfully: {len(proposed_changes)} changes, session: {session_id}")
            
            # Record successful completion
            if monitoring_manager:
                monitoring_manager.record_request_complete("preview", request_id, "success")
                monitoring_manager.record_document_processing(
                    "preview", len(str(request.document)), duration, len(proposed_changes)
                )
            
            return response.model_dump()
            
        except (ValidationException, LLMException, SessionException, ProcessingException) as e:
            duration = time.time() - start_time
            error_response = self.error_handler.categorize_error(e)
            
            # Record error completion
            if monitoring_manager:
                monitoring_manager.record_request_complete(
                    "preview", request_id, "error", error_response.error_type
                )
            
            log_error_with_context(
                self.logger, e,
                {"request_id": request_id, "duration": duration, "operation": "preview"},
                "handle_preview"
            )
            
            return self._create_error_response_from_model(error_response)
            
        except Exception as e:
            duration = time.time() - start_time
            error_response = self.error_handler.categorize_error(e)
            
            # Record error completion
            if monitoring_manager:
                monitoring_manager.record_request_complete(
                    "preview", request_id, "error", "unexpected_error"
                )
            
            log_error_with_context(
                self.logger, e,
                {"request_id": request_id, "duration": duration, "operation": "preview"},
                "handle_preview"
            )
            
            return self._create_error_response_from_model(error_response)
    
    def _validate_request(self, request_data: Dict[str, Any]) -> PreviewRequest:
        """Validate and parse the preview request.
        
        Args:
            request_data: Raw request data
            
        Returns:
            Validated PreviewRequest object
            
        Raises:
            ValidationException: If request validation fails
        """
        try:
            # Check for required fields first
            if not isinstance(request_data, dict):
                error_response = self.validation_handler.handle_json_validation_error(
                    ValueError("Request data must be a dictionary"), request_data
                )
                raise ValidationException(error_response.error_code, error_response.message, error_response.details)
            
            if "document" not in request_data:
                raise ValidationException(
                    "MISSING_DOCUMENT",
                    "Missing required field: document",
                    {"missing_field": "document", "received_keys": list(request_data.keys())}
                )
            
            if "instruction" not in request_data:
                raise ValidationException(
                    "MISSING_INSTRUCTION", 
                    "Missing required field: instruction",
                    {"missing_field": "instruction", "received_keys": list(request_data.keys())}
                )
            
            # Validate instruction
            instruction = request_data["instruction"]
            if not instruction or not instruction.strip():
                error_response = self.validation_handler.handle_instruction_validation_error(
                    instruction, ValueError("Empty instruction")
                )
                raise ValidationException(error_response.error_code, error_response.message, error_response.details)
            
            return PreviewRequest.model_validate(request_data)
            
        except ValidationException:
            raise
        except Exception as e:
            error_response = self.validation_handler.handle_json_validation_error(e, request_data)
            raise ValidationException(error_response.error_code, error_response.message, error_response.details)
    
    def _validate_document_size(self, document: Dict[str, Any]) -> None:
        """Validate that the document size is within limits.
        
        Args:
            document: JSON document to validate
            
        Raises:
            ValidationException: If document is too large
        """
        try:
            import json
            document_size = len(json.dumps(document).encode('utf-8'))
            
            if document_size > self.config.max_document_size:
                error_response = self.validation_handler.handle_json_validation_error(
                    ValueError(f"Document too large: {document_size} bytes"), document
                )
                error_response.details.update({
                    "document_size": document_size,
                    "max_size": self.config.max_document_size
                })
                raise ValidationException(error_response.error_code, error_response.message, error_response.details)
                
        except ValidationException:
            raise
        except Exception as e:
            error_response = self.validation_handler.handle_json_validation_error(e, document)
            raise ValidationException(error_response.error_code, error_response.message, error_response.details)
    
    def _convert_to_map(self, document: Dict[str, Any]) -> List[MapEntry]:
        """Convert JSON document to map format.
        
        Args:
            document: JSON document to convert
            
        Returns:
            List of MapEntry objects
            
        Raises:
            ProcessingException: If conversion fails
        """
        try:
            # Validate JSON first
            validated_document = self.json_processor.validate_json(document)
            
            # Convert to map format
            map_entries = self.json_processor.json2map(validated_document)
            
            if not map_entries:
                error_response = self.processing_handler.handle_memory_error(
                    "json_to_map_conversion", len(str(document))
                )
                error_response.error_code = "NO_EDITABLE_CONTENT"
                error_response.message = "Document contains no editable text content"
                error_response.suggestions = [
                    "Ensure the document contains text nodes with 'type' and 'value' fields",
                    "Check that the document structure matches the expected format",
                    "Verify that text nodes have type 'text', 'Text', or 'Placeholder'"
                ]
                raise ProcessingException(error_response.error_code, error_response.message, error_response.details)
            
            self.logger.debug(f"Converted document to {len(map_entries)} map entries")
            return map_entries
            
        except ProcessingException:
            raise
        except RecursionError as e:
            error_response = self.processing_handler.handle_recursion_error("json_to_map_conversion")
            raise ProcessingException(error_response.error_code, error_response.message, error_response.details)
        except MemoryError as e:
            error_response = self.processing_handler.handle_memory_error("json_to_map_conversion", len(str(document)))
            raise ProcessingException(error_response.error_code, error_response.message, error_response.details)
        except Exception as e:
            error_response = self.processing_handler.handle_timeout_error("json_to_map_conversion")
            error_response.error_code = "MAP_CONVERSION_FAILED"
            error_response.message = f"Failed to convert document to map format: {str(e)}"
            error_response.details = {"error": str(e)}
            raise ProcessingException(error_response.error_code, error_response.message, error_response.details)
    
    async def _get_proposed_changes(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[ProposedChange]:
        """Get proposed changes from LLM service.
        
        Args:
            map_entries: List of map entries representing the document
            instruction: Natural language instruction
            
        Returns:
            List of proposed changes
            
        Raises:
            LLMException: If LLM service fails
        """
        if not self.llm_service:
            raise LLMException(
                error_code="LLM_SERVICE_NOT_INITIALIZED",
                message="LLM service is not properly initialized",
                details={"provider": self.config.llm_config.provider}
            )
        
        try:
            self.logger.debug(f"Getting proposed changes from {self.llm_service.get_provider_name()}")
            
            # Track LLM request for monitoring
            llm_request_id = f"llm_{request_id}" if 'request_id' in locals() else f"llm_{int(time.time())}"
            
            with track_llm_request(
                self.llm_service.get_provider_name(),
                self.llm_service.get_model_name(),
                llm_request_id
            ) as tracker:
                proposed_changes = await self.llm_service.get_proposed_changes(map_entries, instruction)
            
            # Validate proposed changes
            validated_changes = self._validate_proposed_changes(proposed_changes, map_entries)
            
            self.logger.debug(f"LLM proposed {len(validated_changes)} changes")
            return validated_changes
            
        except LLMException:
            raise
        except Exception as e:
            raise LLMException(
                error_code="LLM_PROCESSING_FAILED",
                message=f"Failed to get proposed changes from LLM: {str(e)}",
                details={
                    "provider": self.llm_service.get_provider_name(),
                    "model": self.llm_service.get_model_name(),
                    "error": str(e)
                }
            )
    
    def _validate_proposed_changes(
        self, 
        proposed_changes: List[ProposedChange], 
        map_entries: List[MapEntry]
    ) -> List[ProposedChange]:
        """Validate proposed changes against the original map entries.
        
        Args:
            proposed_changes: Changes proposed by LLM
            map_entries: Original map entries
            
        Returns:
            List of validated proposed changes
            
        Raises:
            LLMException: If validation fails
        """
        if not proposed_changes:
            return []
        
        # Create lookup for map entries by ID
        entry_lookup = {entry.id: entry for entry in map_entries}
        
        validated_changes = []
        for change in proposed_changes:
            try:
                # Check if the referenced entry exists
                if change.id not in entry_lookup:
                    self.logger.warning(f"Proposed change references non-existent entry: {change.id}")
                    continue
                
                original_entry = entry_lookup[change.id]
                
                # Verify path matches
                if change.path != original_entry.path:
                    self.logger.warning(f"Path mismatch for entry {change.id}: {change.path} vs {original_entry.path}")
                    continue
                
                # Verify current value matches
                if change.current_value != original_entry.value:
                    self.logger.warning(f"Current value mismatch for entry {change.id}")
                    # Update with correct current value
                    change.current_value = original_entry.value
                
                # Skip changes where proposed value is same as current
                if change.proposed_value == change.current_value:
                    self.logger.debug(f"Skipping no-op change for entry {change.id}")
                    continue
                
                validated_changes.append(change)
                
            except Exception as e:
                self.logger.warning(f"Error validating change {change.id}: {e}")
                continue
        
        return validated_changes
    
    def _create_preview_session(
        self, 
        document: Dict[str, Any], 
        proposed_changes: List[ProposedChange]
    ) -> str:
        """Create a preview session for the changes.
        
        Args:
            document: Original JSON document
            proposed_changes: List of proposed changes
            
        Returns:
            Session ID for the created session
            
        Raises:
            SessionException: If session creation fails
        """
        try:
            session_id = self.session_manager.create_session(document, proposed_changes)
            self.logger.debug(f"Created preview session: {session_id}")
            return session_id
        except SessionException:
            raise
        except Exception as e:
            raise SessionException(
                error_code="SESSION_CREATION_FAILED",
                message=f"Failed to create preview session: {str(e)}",
                details={"error": str(e)}
            )
    
    def _generate_preview_message(self, proposed_changes: List[ProposedChange]) -> str:
        """Generate a human-readable message about the proposed changes.
        
        Args:
            proposed_changes: List of proposed changes
            
        Returns:
            Human-readable message describing the changes
        """
        if not proposed_changes:
            return "No changes needed for the given instruction."
        
        change_count = len(proposed_changes)
        if change_count == 1:
            change = proposed_changes[0]
            path_str = " -> ".join(change.path)
            return f"Found 1 change to make: Update '{path_str}' from '{change.current_value}' to '{change.proposed_value}'"
        else:
            # Group changes by path for better readability
            path_counts = {}
            for change in proposed_changes:
                path_key = " -> ".join(change.path[:-1]) if len(change.path) > 1 else "root"
                path_counts[path_key] = path_counts.get(path_key, 0) + 1
            
            if len(path_counts) == 1:
                path_name = list(path_counts.keys())[0]
                return f"Found {change_count} changes to make in '{path_name}'"
            else:
                return f"Found {change_count} changes to make across {len(path_counts)} different sections"
    
    def _create_no_changes_response(self, instruction: str) -> Dict[str, Any]:
        """Create a response for when no changes are needed.
        
        Args:
            instruction: Original instruction
            
        Returns:
            Response dictionary indicating no changes needed
        """
        # Create a dummy session for consistency (though it won't be used)
        session_id = self.session_manager.generate_session_id()
        
        response = PreviewResponse(
            session_id=session_id,
            changes=[],
            message=f"No changes needed for the instruction: '{instruction}'. The document already matches the requested state.",
            status="no_changes"
        )
        
        self.logger.info(f"No changes needed for instruction: {instruction}")
        return response.model_dump()
    
    def _create_error_response(
        self, 
        error_type: str, 
        error_code: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a standardized error response.
        
        Args:
            error_type: Type of error (validation, llm, session, processing)
            error_code: Specific error code
            message: Human-readable error message
            details: Optional additional error details
            
        Returns:
            Error response dictionary
        """
        error_response = ErrorResponse(
            error_type=error_type,
            error_code=error_code,
            message=message,
            details=details
        )
        
        return {
            "error": error_response.model_dump(),
            "status": "error"
        }
    
    def _create_error_response_from_model(self, error_response: ErrorResponse) -> Dict[str, Any]:
        """Create error response dictionary from ErrorResponse model.
        
        Args:
            error_response: ErrorResponse model instance
            
        Returns:
            Error response dictionary
        """
        return {
            "error": error_response.model_dump(),
            "status": "error"
        }
    
    async def handle_ambiguous_instruction(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[str]:
        """Handle ambiguous instructions by getting suggestions from LLM.
        
        Args:
            map_entries: List of map entries representing the document
            instruction: Ambiguous instruction
            
        Returns:
            List of suggested clarifications
            
        Raises:
            LLMException: If LLM service fails
        """
        if not self.llm_service:
            raise LLMException(
                error_code="LLM_SERVICE_NOT_INITIALIZED",
                message="LLM service is not properly initialized"
            )
        
        try:
            suggestions = await self.llm_service.handle_ambiguous_instruction(map_entries, instruction)
            self.logger.debug(f"Generated {len(suggestions)} suggestions for ambiguous instruction")
            return suggestions
        except Exception as e:
            raise LLMException(
                error_code="SUGGESTION_GENERATION_FAILED",
                message=f"Failed to generate suggestions for ambiguous instruction: {str(e)}",
                details={"error": str(e)}
            )
    
    def get_tool_schema(self) -> Dict[str, Any]:
        """Get the MCP tool schema for json_editor_preview.
        
        Returns:
            Tool schema dictionary for MCP registration
        """
        return {
            "name": "json_editor_preview",
            "description": "Preview proposed changes to a JSON document using natural language instructions",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "document": {
                        "type": "object",
                        "description": "JSON document to edit"
                    },
                    "instruction": {
                        "type": "string",
                        "description": "Natural language editing instruction"
                    }
                },
                "required": ["document", "instruction"]
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the preview tool.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                "status": "healthy",
                "components": {}
            }
            
            # Check LLM service
            if self.llm_service:
                health_status["components"]["llm_service"] = {
                    "status": "healthy",
                    "provider": self.llm_service.get_provider_name(),
                    "model": self.llm_service.get_model_name()
                }
            else:
                health_status["components"]["llm_service"] = {
                    "status": "unhealthy",
                    "error": "LLM service not initialized"
                }
                health_status["status"] = "unhealthy"
            
            # Check session manager
            try:
                session_health = self.session_manager.health_check()
                health_status["components"]["session_manager"] = session_health
            except Exception as e:
                health_status["components"]["session_manager"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["status"] = "unhealthy"
            
            # Check JSON processor (always healthy if instantiated)
            health_status["components"]["json_processor"] = {
                "status": "healthy"
            }
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }