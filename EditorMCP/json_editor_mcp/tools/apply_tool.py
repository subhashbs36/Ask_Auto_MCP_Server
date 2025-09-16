"""Apply tool for JSON Editor MCP Tool."""

import logging
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from ..config.models import ServerConfig
from ..models.requests import ApplyRequest, ApplyResponse
from ..models.core import MapEntry, ProposedChange, AppliedChange
from ..models.errors import (
    ErrorResponse, ValidationException, LLMException, 
    SessionException, ProcessingException
)
from ..services.json_processor import JSONProcessor
from ..services.hybrid_session_manager import HybridSessionManager


class ApplyTool:
    """Tool for handling json_editor_apply requests."""
    
    def __init__(self, config: ServerConfig, session_manager=None):
        """Initialize the apply tool with configuration.
        
        Args:
            config: Server configuration containing all service settings
            session_manager: Optional shared session manager instance
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
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
    
    async def handle_apply(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a json_editor_apply request.
        
        Args:
            request_data: Raw request data from MCP client
            
        Returns:
            Dictionary containing the apply response or error
        """
        try:
            # Validate and parse request
            request = self._validate_request(request_data)
            
            # Retrieve session data
            session = self._get_session(request.session_id)
            
            # Verify document state hasn't changed
            self._verify_document_state(request.session_id, session.document)
            
            # Determine which changes to apply
            changes_to_apply = self._determine_changes_to_apply(
                session.proposed_changes, 
                request.confirmed_changes
            )
            
            # Handle case where no changes need to be applied
            if not changes_to_apply:
                return self._create_no_changes_response(session.document, request.session_id)
            
            # Apply changes to the document
            modified_document, applied_changes = self._apply_changes(
                session.document, 
                changes_to_apply
            )
            
            # Verify changes were applied correctly
            self._verify_applied_changes(applied_changes, changes_to_apply)
            
            # Create and return successful response
            response = ApplyResponse(
                modified_document=modified_document,
                applied_changes=applied_changes,
                message=self._generate_apply_message(applied_changes),
                status="success"
            )
            
            self.logger.info(f"Applied {len(applied_changes)} changes successfully for session: {request.session_id}")
            return response.model_dump()
            
        except ValidationException as e:
            self.logger.warning(f"Validation error in apply: {e.message}")
            return self._create_error_response("validation", e.error_code, e.message, e.details)
            
        except SessionException as e:
            self.logger.error(f"Session error in apply: {e.message}")
            return self._create_error_response("session", e.error_code, e.message, e.details)
            
        except ProcessingException as e:
            self.logger.error(f"Processing error in apply: {e.message}")
            return self._create_error_response("processing", e.error_code, e.message, e.details)
            
        except Exception as e:
            self.logger.error(f"Unexpected error in apply: {e}", exc_info=True)
            return self._create_error_response(
                "processing", 
                "UNEXPECTED_ERROR", 
                f"An unexpected error occurred: {str(e)}"
            )
    
    def _validate_request(self, request_data: Dict[str, Any]) -> ApplyRequest:
        """Validate and parse the apply request.
        
        Args:
            request_data: Raw request data
            
        Returns:
            Validated ApplyRequest object
            
        Raises:
            ValidationException: If request validation fails
        """
        try:
            return ApplyRequest.model_validate(request_data)
        except Exception as e:
            raise ValidationException(
                error_code="INVALID_REQUEST",
                message=f"Invalid apply request: {str(e)}",
                details={
                    "validation_error": str(e),
                    "received_data": request_data
                }
            )
    
    def _get_session(self, session_id: str):
        """Retrieve session data from session manager.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            PreviewSession object
            
        Raises:
            SessionException: If session retrieval fails
        """
        try:
            return self.session_manager.get_session(session_id)
        except SessionException:
            # Re-raise session exceptions as-is
            raise
        except Exception as e:
            raise SessionException(
                error_code="SESSION_RETRIEVAL_FAILED",
                message=f"Failed to retrieve session: {str(e)}",
                details={
                    "session_id": session_id,
                    "error": str(e)
                }
            )
    
    def _verify_document_state(self, session_id: str, original_document: Dict[str, Any]) -> None:
        """Verify that the document hasn't changed since the preview was generated.
        
        Args:
            session_id: Session ID for verification
            original_document: Original document from session
            
        Raises:
            SessionException: If document state verification fails
        """
        try:
            # The session manager's verify_document_unchanged method expects the current document
            # Since we're applying to the original document from the session, we verify against itself
            self.session_manager.verify_document_unchanged(session_id, original_document)
        except SessionException:
            # Re-raise session exceptions as-is
            raise
        except Exception as e:
            raise SessionException(
                error_code="DOCUMENT_VERIFICATION_FAILED",
                message=f"Failed to verify document state: {str(e)}",
                details={
                    "session_id": session_id,
                    "error": str(e)
                }
            )
    
    def _determine_changes_to_apply(
        self, 
        proposed_changes: List[ProposedChange], 
        confirmed_changes: Optional[List[str]]
    ) -> List[ProposedChange]:
        """Determine which changes should be applied based on confirmation.
        
        Args:
            proposed_changes: All proposed changes from the session
            confirmed_changes: List of change IDs to apply, or None for all
            
        Returns:
            List of changes to apply
            
        Raises:
            ValidationException: If confirmed changes contain invalid IDs
        """
        if confirmed_changes is None:
            # Apply all changes if no specific confirmation provided
            return proposed_changes
        
        # Create lookup for proposed changes by ID
        change_lookup = {change.id: change for change in proposed_changes}
        
        # Validate that all confirmed change IDs exist
        invalid_ids = []
        changes_to_apply = []
        
        for change_id in confirmed_changes:
            if change_id not in change_lookup:
                invalid_ids.append(change_id)
            else:
                changes_to_apply.append(change_lookup[change_id])
        
        if invalid_ids:
            raise ValidationException(
                error_code="INVALID_CHANGE_IDS",
                message=f"Invalid change IDs specified: {', '.join(invalid_ids)}",
                details={
                    "invalid_ids": invalid_ids,
                    "available_ids": list(change_lookup.keys()),
                    "suggestions": [
                        "Check that the change IDs match those from the preview response",
                        "Generate a new preview if the session has expired",
                        "Ensure all change IDs are strings"
                    ]
                }
            )
        
        return changes_to_apply
    
    def _apply_changes(
        self, 
        original_document: Dict[str, Any], 
        changes_to_apply: List[ProposedChange]
    ) -> tuple[Dict[str, Any], List[AppliedChange]]:
        """Apply the specified changes to the document.
        
        Args:
            original_document: Original JSON document
            changes_to_apply: List of changes to apply
            
        Returns:
            Tuple of (modified_document, applied_changes)
            
        Raises:
            ProcessingException: If change application fails
        """
        try:
            # Convert original document to map format
            original_map = self.json_processor.json2map(original_document)
            
            # Create lookup for map entries by path for efficient updates
            map_lookup = {}
            for entry in original_map:
                path_key = tuple(entry.path)
                map_lookup[path_key] = entry
            
            # Track applied changes
            applied_changes = []
            
            # Apply each change to the map
            for change in changes_to_apply:
                path_key = tuple(change.path)
                
                if path_key not in map_lookup:
                    self.logger.warning(f"Change path not found in document: {change.path}")
                    continue
                
                map_entry = map_lookup[path_key]
                
                # Verify current value matches expected value
                if map_entry.value != change.current_value:
                    self.logger.warning(
                        f"Current value mismatch for change {change.id}: "
                        f"expected '{change.current_value}', found '{map_entry.value}'"
                    )
                    # Update with actual current value for tracking
                    actual_current_value = map_entry.value
                else:
                    actual_current_value = change.current_value
                
                # Apply the change
                old_value = map_entry.value
                map_entry.value = change.proposed_value
                
                # Track the applied change
                applied_change = AppliedChange(
                    id=change.id,
                    path=change.path,
                    old_value=old_value,
                    new_value=change.proposed_value,
                    applied_at=datetime.now(UTC)
                )
                applied_changes.append(applied_change)
                
                self.logger.debug(f"Applied change {change.id}: '{old_value}' -> '{change.proposed_value}'")
            
            # Reconstruct the document from the modified map
            modified_document = self.json_processor.map2json(original_document, original_map)
            
            return modified_document, applied_changes
            
        except ProcessingException:
            # Re-raise processing exceptions as-is
            raise
        except Exception as e:
            raise ProcessingException(
                error_code="CHANGE_APPLICATION_FAILED",
                message=f"Failed to apply changes to document: {str(e)}",
                details={
                    "error": str(e),
                    "changes_count": len(changes_to_apply)
                }
            )
    
    def _verify_applied_changes(
        self, 
        applied_changes: List[AppliedChange], 
        expected_changes: List[ProposedChange]
    ) -> None:
        """Verify that changes were applied correctly.
        
        Args:
            applied_changes: List of changes that were applied
            expected_changes: List of changes that were expected to be applied
            
        Raises:
            ProcessingException: If verification fails
        """
        try:
            # Check that we applied the expected number of changes
            if len(applied_changes) != len(expected_changes):
                raise ProcessingException(
                    error_code="CHANGE_COUNT_MISMATCH",
                    message=f"Expected to apply {len(expected_changes)} changes, but applied {len(applied_changes)}",
                    details={
                        "expected_count": len(expected_changes),
                        "applied_count": len(applied_changes),
                        "applied_ids": [change.id for change in applied_changes],
                        "expected_ids": [change.id for change in expected_changes]
                    }
                )
            
            # Create lookup for applied changes by ID
            applied_lookup = {change.id: change for change in applied_changes}
            
            # Verify each expected change was applied correctly
            for expected_change in expected_changes:
                if expected_change.id not in applied_lookup:
                    raise ProcessingException(
                        error_code="MISSING_APPLIED_CHANGE",
                        message=f"Expected change {expected_change.id} was not applied",
                        details={
                            "missing_change_id": expected_change.id,
                            "expected_path": expected_change.path
                        }
                    )
                
                applied_change = applied_lookup[expected_change.id]
                
                # Verify the new value matches what was expected
                if applied_change.new_value != expected_change.proposed_value:
                    raise ProcessingException(
                        error_code="APPLIED_VALUE_MISMATCH",
                        message=f"Applied value for change {expected_change.id} doesn't match expected value",
                        details={
                            "change_id": expected_change.id,
                            "expected_value": expected_change.proposed_value,
                            "applied_value": applied_change.new_value,
                            "path": expected_change.path
                        }
                    )
            
            self.logger.debug(f"Successfully verified {len(applied_changes)} applied changes")
            
        except ProcessingException:
            # Re-raise processing exceptions as-is
            raise
        except Exception as e:
            raise ProcessingException(
                error_code="CHANGE_VERIFICATION_FAILED",
                message=f"Failed to verify applied changes: {str(e)}",
                details={"error": str(e)}
            )
    
    def _generate_apply_message(self, applied_changes: List[AppliedChange]) -> str:
        """Generate a human-readable message about the applied changes.
        
        Args:
            applied_changes: List of changes that were applied
            
        Returns:
            Human-readable message describing the applied changes
        """
        if not applied_changes:
            return "No changes were applied to the document."
        
        change_count = len(applied_changes)
        if change_count == 1:
            change = applied_changes[0]
            path_str = " -> ".join(change.path)
            return f"Successfully applied 1 change: Updated '{path_str}' from '{change.old_value}' to '{change.new_value}'"
        else:
            # Group changes by path for better readability
            path_counts = {}
            for change in applied_changes:
                path_key = " -> ".join(change.path[:-1]) if len(change.path) > 1 else "root"
                path_counts[path_key] = path_counts.get(path_key, 0) + 1
            
            if len(path_counts) == 1:
                path_name = list(path_counts.keys())[0]
                return f"Successfully applied {change_count} changes in '{path_name}'"
            else:
                return f"Successfully applied {change_count} changes across {len(path_counts)} different sections"
    
    def _create_no_changes_response(
        self, 
        original_document: Dict[str, Any], 
        session_id: str
    ) -> Dict[str, Any]:
        """Create a response for when no changes need to be applied.
        
        Args:
            original_document: Original document (unchanged)
            session_id: Session ID for reference
            
        Returns:
            Response dictionary indicating no changes applied
        """
        response = ApplyResponse(
            modified_document=original_document,
            applied_changes=[],
            message="No changes were applied. Either no changes were confirmed or all specified change IDs were invalid.",
            status="no_changes"
        )
        
        self.logger.info(f"No changes applied for session: {session_id}")
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
            error_type: Type of error (validation, session, processing)
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
    
    def get_tool_schema(self) -> Dict[str, Any]:
        """Get the MCP tool schema for json_editor_apply.
        
        Returns:
            Tool schema dictionary for MCP registration
        """
        return {
            "name": "json_editor_apply",
            "description": "Apply previously previewed changes to a JSON document",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID from preview operation"
                    },
                    "confirmed_changes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of change IDs to apply. If omitted, all changes are applied"
                    }
                },
                "required": ["session_id"]
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the apply tool.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                "status": "healthy",
                "components": {}
            }
            
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