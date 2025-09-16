"""Prompt management system for the JSON Editor MCP tool."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from json_editor_mcp.config.models import PromptsConfig
from json_editor_mcp.models.core import MapEntry
from json_editor_mcp.models.errors import ValidationException


class PromptManager:
    """Manages loading, templating, and validation of prompts for LLM interactions."""
    
    def __init__(self, config: PromptsConfig, base_path: Optional[str] = None):
        """
        Initialize the PromptManager.
        
        Args:
            config: Prompts configuration
            base_path: Base path for prompt files (defaults to current working directory)
        """
        self.config = config
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self._prompt_cache: Dict[str, str] = {}
        
    def load_system_prompt(self) -> str:
        """
        Load the system prompt from file.
        
        Returns:
            The system prompt text
            
        Raises:
            ValidationException: If the prompt file cannot be loaded or is invalid
        """
        return self._load_prompt_file(
            self.config.system_prompt_file,
            "system_prompt"
        )
    
    def load_guardrails_prompt(self) -> str:
        """
        Load the guardrails prompt from file.
        
        Returns:
            The guardrails prompt text
            
        Raises:
            ValidationException: If the prompt file cannot be loaded or is invalid
        """
        return self._load_prompt_file(
            self.config.guardrails_prompt_file,
            "guardrails_prompt"
        )
    
    def create_instruction_prompt(
        self, 
        instruction: str, 
        map_entries: List[MapEntry]
    ) -> str:
        """
        Create a formatted instruction prompt with context injection.
        
        Args:
            instruction: The user's natural language instruction
            map_entries: List of map entries from the JSON document
            
        Returns:
            The formatted instruction prompt
            
        Raises:
            ValidationException: If template loading or formatting fails
        """
        # Load the instruction template
        template = self._load_prompt_file(
            self.config.edit_instruction_template,
            "edit_instruction_template"
        )
        
        # Sanitize the instruction
        sanitized_instruction = self.sanitize_instruction(instruction)
        
        # Format map entries for display
        formatted_entries = self._format_map_entries(map_entries)
        
        # Inject context into template
        try:
            formatted_prompt = template.format(
                instruction=sanitized_instruction,
                map_entries=formatted_entries
            )
            return formatted_prompt
        except KeyError as e:
            raise ValidationException(
                "TEMPLATE_FORMAT_ERROR",
                f"Template formatting error: missing placeholder {e}",
                {"template_file": self.config.edit_instruction_template}
            )
    
    def create_full_prompt(
        self, 
        instruction: str, 
        map_entries: List[MapEntry],
        include_guardrails: bool = True
    ) -> str:
        """
        Create a complete prompt combining system prompt, guardrails, and instruction.
        
        Args:
            instruction: The user's natural language instruction
            map_entries: List of map entries from the JSON document
            include_guardrails: Whether to include guardrails prompt
            
        Returns:
            The complete formatted prompt
            
        Raises:
            ValidationException: If prompt creation fails
        """
        components = []
        
        # Add system prompt
        system_prompt = self.load_system_prompt()
        components.append(system_prompt)
        
        # Add guardrails if requested
        if include_guardrails:
            guardrails_prompt = self.load_guardrails_prompt()
            components.append(f"\n## Safety Guidelines\n{guardrails_prompt}")
        
        # Add instruction prompt
        instruction_prompt = self.create_instruction_prompt(instruction, map_entries)
        components.append(f"\n## Current Task\n{instruction_prompt}")
        
        return "\n\n".join(components)
    
    def sanitize_instruction(self, instruction: str) -> str:
        """
        Sanitize user instruction to prevent prompt injection and malicious patterns.
        
        Args:
            instruction: The raw user instruction
            
        Returns:
            Sanitized instruction text
            
        Raises:
            ValidationException: If instruction contains forbidden patterns
        """
        if not instruction or not instruction.strip():
            raise ValidationException("EMPTY_INSTRUCTION", "Instruction cannot be empty")
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', instruction.strip())
        
        # Check for forbidden patterns
        forbidden_patterns = [
            r'```.*?```',  # Code blocks
            r'<script.*?</script>',  # Script tags
            r'javascript:',  # JavaScript URLs
            r'data:.*?base64',  # Data URLs
            r'eval\s*\(',  # Eval calls
            r'exec\s*\(',  # Exec calls
            r'__.*?__',  # Double underscore patterns (except our deletion marker)
        ]
        
        for pattern in forbidden_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE | re.DOTALL):
                # Allow our deletion marker
                if pattern == r'__.*?__' and sanitized == '__DELETE_FIELD__':
                    continue
                raise ValidationException(
                    "FORBIDDEN_PATTERN",
                    f"Instruction contains forbidden pattern: {pattern}",
                    {"instruction": instruction}
                )
        
        # Limit length
        max_length = 5000
        if len(sanitized) > max_length:
            raise ValidationException(
                "INSTRUCTION_TOO_LONG",
                f"Instruction too long: {len(sanitized)} characters (max: {max_length})",
                {"instruction_length": len(sanitized)}
            )
        
        return sanitized
    
    def validate_prompt_files(self) -> Dict[str, bool]:
        """
        Validate that all configured prompt files exist and are readable.
        
        Returns:
            Dictionary mapping file names to validation status
        """
        files_to_check = {
            "system_prompt": self.config.system_prompt_file,
            "guardrails_prompt": self.config.guardrails_prompt_file,
            "edit_instruction_template": self.config.edit_instruction_template,
        }
        
        validation_results = {}
        
        for file_type, file_path in files_to_check.items():
            try:
                full_path = self.base_path / file_path
                validation_results[file_type] = (
                    full_path.exists() and 
                    full_path.is_file() and 
                    full_path.stat().st_size > 0
                )
            except Exception:
                validation_results[file_type] = False
        
        return validation_results
    
    def clear_cache(self) -> None:
        """Clear the internal prompt cache."""
        self._prompt_cache.clear()
    
    def _load_prompt_file(self, file_path: str, cache_key: str) -> str:
        """
        Load a prompt file with caching.
        
        Args:
            file_path: Path to the prompt file
            cache_key: Key for caching the prompt
            
        Returns:
            The prompt file content
            
        Raises:
            ValidationException: If the file cannot be loaded
        """
        # Check cache first
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]
        
        try:
            full_path = self.base_path / file_path
            
            if not full_path.exists():
                raise ValidationException(
                    "PROMPT_FILE_NOT_FOUND",
                    f"Prompt file not found: {file_path}",
                    {"file_path": str(full_path)}
                )
            
            if not full_path.is_file():
                raise ValidationException(
                    "PROMPT_PATH_NOT_FILE",
                    f"Prompt path is not a file: {file_path}",
                    {"file_path": str(full_path)}
                )
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                raise ValidationException(
                    "PROMPT_FILE_EMPTY",
                    f"Prompt file is empty: {file_path}",
                    {"file_path": str(full_path)}
                )
            
            # Cache the content
            self._prompt_cache[cache_key] = content
            return content
            
        except OSError as e:
            raise ValidationException(
                "PROMPT_FILE_READ_ERROR",
                f"Failed to read prompt file {file_path}: {str(e)}",
                {"file_path": file_path, "error": str(e)}
            )
    
    def _format_map_entries(self, map_entries: List[MapEntry]) -> str:
        """
        Format map entries for display in prompts.
        
        Args:
            map_entries: List of map entries to format
            
        Returns:
            Formatted string representation of map entries
        """
        if not map_entries:
            return "No map entries available."
        
        formatted_entries = []
        for entry in map_entries:
            path_str = " -> ".join(entry.path) if entry.path else "root"
            formatted_entries.append(
                f"ID: {entry.id}\n"
                f"Path: {path_str}\n"
                f"Value: {entry.value}\n"
            )
        
        return "\n".join(formatted_entries)