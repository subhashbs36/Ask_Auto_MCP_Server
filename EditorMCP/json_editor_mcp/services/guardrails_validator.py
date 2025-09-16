"""Guardrails and validation system for JSON Editor MCP Tool."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

from ..config.models import GuardrailsConfig
from ..models.errors import ValidationException, ProcessingException
from ..models.core import ProposedChange


class ValidationResult(BaseModel):
    """Result of guardrails validation."""
    
    is_valid: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    warnings: List[str] = []
    sanitized_instruction: Optional[str] = None
    blocked_changes: List[str] = []  # IDs of changes that were blocked


class GuardrailsValidator:
    """Validates instructions and proposed changes against guardrails policies."""
    
    def __init__(self, config: GuardrailsConfig):
        """Initialize the guardrails validator with configuration.
        
        Args:
            config: Guardrails configuration settings
        """
        self.config = config
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        # Compile forbidden patterns
        self._forbidden_patterns = []
        for pattern in self.config.forbidden_patterns:
            try:
                self._forbidden_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                # Log warning but continue - don't fail initialization
                print(f"Warning: Invalid regex pattern '{pattern}': {e}")
        
        # Compile deletion keywords pattern
        if self.config.deletion_keywords:
            deletion_pattern = r'\b(?:' + '|'.join(re.escape(kw) for kw in self.config.deletion_keywords) + r')\b'
            self._deletion_pattern = re.compile(deletion_pattern, re.IGNORECASE)
        else:
            self._deletion_pattern = None
        
        # Malicious patterns to detect
        self._malicious_patterns = [
            re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
            re.compile(r'javascript:', re.IGNORECASE),
            re.compile(r'on\w+\s*=', re.IGNORECASE),  # Event handlers
            re.compile(r'eval\s*\(', re.IGNORECASE),
            re.compile(r'exec\s*\(', re.IGNORECASE),
            re.compile(r'__import__', re.IGNORECASE),
            re.compile(r'subprocess', re.IGNORECASE),
            re.compile(r'os\.system', re.IGNORECASE),
        ]
    
    def validate_document_size(self, document: Dict[str, Any], max_size: int) -> ValidationResult:
        """Validate that document size is within limits.
        
        Args:
            document: JSON document to validate
            max_size: Maximum allowed size in bytes
            
        Returns:
            ValidationResult indicating if document size is valid
        """
        try:
            document_json = json.dumps(document, separators=(',', ':'))
            document_size = len(document_json.encode('utf-8'))
            
            if document_size > max_size:
                return ValidationResult(
                    is_valid=False,
                    error_code="DOCUMENT_TOO_LARGE",
                    error_message=f"Document size ({document_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
                )
            
            return ValidationResult(is_valid=True)
            
        except (TypeError, ValueError) as e:
            return ValidationResult(
                is_valid=False,
                error_code="DOCUMENT_SERIALIZATION_ERROR",
                error_message=f"Failed to serialize document for size validation: {str(e)}"
            )
    
    def sanitize_instruction(self, instruction: str) -> ValidationResult:
        """Sanitize and validate instruction text.
        
        Args:
            instruction: Raw instruction text
            
        Returns:
            ValidationResult with sanitized instruction or validation errors
        """
        if not instruction or not instruction.strip():
            return ValidationResult(
                is_valid=False,
                error_code="EMPTY_INSTRUCTION",
                error_message="Instruction cannot be empty"
            )
        
        # Check instruction length
        if len(instruction) > self.config.max_instruction_length:
            return ValidationResult(
                is_valid=False,
                error_code="INSTRUCTION_TOO_LONG",
                error_message=f"Instruction length ({len(instruction)}) exceeds maximum allowed length ({self.config.max_instruction_length})"
            )
        
        sanitized = instruction.strip()
        warnings = []
        
        # Check for malicious patterns
        for pattern in self._malicious_patterns:
            if pattern.search(sanitized):
                return ValidationResult(
                    is_valid=False,
                    error_code="MALICIOUS_PATTERN_DETECTED",
                    error_message="Instruction contains potentially malicious content"
                )
        
        # Check for forbidden patterns
        for pattern in self._forbidden_patterns:
            if pattern.search(sanitized):
                return ValidationResult(
                    is_valid=False,
                    error_code="FORBIDDEN_PATTERN",
                    error_message="Instruction contains forbidden patterns"
                )
        
        # Basic sanitization - remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        return ValidationResult(
            is_valid=True,
            sanitized_instruction=sanitized,
            warnings=warnings
        )
    
    def detect_deletion_intent(self, instruction: str) -> bool:
        """Detect if instruction indicates deletion operations.
        
        Args:
            instruction: Instruction text to analyze
            
        Returns:
            True if deletion intent is detected, False otherwise
        """
        if not self.config.prevent_deletions or not self._deletion_pattern:
            return False
        
        return bool(self._deletion_pattern.search(instruction))
    
    def validate_proposed_changes(self, changes: List[ProposedChange], instruction: str) -> ValidationResult:
        """Validate proposed changes against guardrails policies.
        
        Args:
            changes: List of proposed changes to validate
            instruction: Original instruction that generated the changes
            
        Returns:
            ValidationResult indicating if changes are valid
        """
        if not self.config.enabled:
            return ValidationResult(is_valid=True)
        
        warnings = []
        blocked_changes = []
        
        # Check number of changes
        if len(changes) > self.config.max_changes_per_request:
            return ValidationResult(
                is_valid=False,
                error_code="TOO_MANY_CHANGES",
                error_message=f"Number of proposed changes ({len(changes)}) exceeds maximum allowed ({self.config.max_changes_per_request})"
            )
        
        # Check for deletion operations
        deletion_detected = self.detect_deletion_intent(instruction)
        
        for change in changes:
            # Validate JSON value types
            if not self._is_allowed_json_type(change.proposed_value):
                blocked_changes.append(change.id)
                warnings.append(f"Change {change.id} blocked: proposed value type not allowed")
                continue
            
            # Check for deletion operations
            if self.config.prevent_deletions and deletion_detected:
                # Check if this is actually a deletion (empty value when not allowed)
                if not self.config.allow_empty_values and not change.proposed_value.strip():
                    blocked_changes.append(change.id)
                    warnings.append(f"Change {change.id} blocked: deletion/empty value not allowed")
                    continue
        
        # If all changes were blocked, return error
        if blocked_changes and len(blocked_changes) == len(changes):
            return ValidationResult(
                is_valid=False,
                error_code="ALL_CHANGES_BLOCKED",
                error_message="All proposed changes were blocked by guardrails policies",
                blocked_changes=blocked_changes,
                warnings=warnings
            )
        
        return ValidationResult(
            is_valid=True,
            blocked_changes=blocked_changes,
            warnings=warnings
        )
    
    def _is_allowed_json_type(self, value: str) -> bool:
        """Check if a value represents an allowed JSON type.
        
        Args:
            value: String representation of the value
            
        Returns:
            True if the value type is allowed, False otherwise
        """
        if not self.config.allowed_json_types:
            return True  # No restrictions
        
        # Try to parse as JSON to determine type
        try:
            parsed_value = json.loads(value)
            value_type = type(parsed_value).__name__
            
            # Map Python types to JSON types
            type_mapping = {
                'str': 'string',
                'int': 'number',
                'float': 'number',
                'bool': 'boolean',
                'list': 'array',
                'dict': 'object',
                'NoneType': 'null'
            }
            
            json_type = type_mapping.get(value_type, 'unknown')
            return json_type in self.config.allowed_json_types
            
        except (json.JSONDecodeError, ValueError):
            # If it's not valid JSON, treat as string
            return 'string' in self.config.allowed_json_types
    
    def validate_full_request(
        self, 
        document: Dict[str, Any], 
        instruction: str, 
        max_document_size: int,
        proposed_changes: Optional[List[ProposedChange]] = None
    ) -> ValidationResult:
        """Perform comprehensive validation of a request.
        
        Args:
            document: JSON document to validate
            instruction: Instruction text to validate
            max_document_size: Maximum allowed document size
            proposed_changes: Optional list of proposed changes to validate
            
        Returns:
            ValidationResult with comprehensive validation results
        """
        if not self.config.enabled:
            return ValidationResult(is_valid=True)
        
        # Validate document size
        size_result = self.validate_document_size(document, max_document_size)
        if not size_result.is_valid:
            return size_result
        
        # Sanitize and validate instruction
        instruction_result = self.sanitize_instruction(instruction)
        if not instruction_result.is_valid:
            return instruction_result
        
        # Validate proposed changes if provided
        if proposed_changes:
            changes_result = self.validate_proposed_changes(proposed_changes, instruction)
            if not changes_result.is_valid:
                return changes_result
            
            # Combine warnings
            all_warnings = instruction_result.warnings + changes_result.warnings
            
            return ValidationResult(
                is_valid=True,
                sanitized_instruction=instruction_result.sanitized_instruction,
                warnings=all_warnings,
                blocked_changes=changes_result.blocked_changes
            )
        
        return ValidationResult(
            is_valid=True,
            sanitized_instruction=instruction_result.sanitized_instruction,
            warnings=instruction_result.warnings
        )
    
    def create_validation_exception(self, result: ValidationResult) -> ValidationException:
        """Create a ValidationException from a ValidationResult.
        
        Args:
            result: ValidationResult that failed validation
            
        Returns:
            ValidationException with appropriate error details
        """
        details = {}
        if result.warnings:
            details['warnings'] = result.warnings
        if result.blocked_changes:
            details['blocked_changes'] = result.blocked_changes
        
        return ValidationException(
            error_code=result.error_code or "VALIDATION_FAILED",
            message=result.error_message or "Validation failed",
            details=details
        )