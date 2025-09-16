"""Gemini LLM service adapter implementation."""

import json
import re
import logging
import time
from typing import List, Dict, Any, Optional
from google import genai
from pydantic import BaseModel, ValidationError

from .interface import LLMServiceInterface
from ..models.core import MapEntry, ProposedChange
from ..models.errors import LLMException
from ..config.models import LLMConfig
from ..utils.error_handler import with_error_handling, RetryConfig
from ..utils.service_error_handlers import LLMErrorHandler
from ..utils.logging_config import get_logger, log_performance_metrics, log_error_with_context


class ProposedChangesResponse(BaseModel):
    """Response model for proposed changes from Gemini."""
    changes: List[Dict[str, Any]]
    has_changes: bool = True
    message: Optional[str] = None


class SuggestionsResponse(BaseModel):
    """Response model for instruction suggestions from Gemini."""
    suggestions: List[str]
    message: Optional[str] = None


class GeminiLLMService(LLMServiceInterface):
    """Gemini LLM service adapter using Google GenAI SDK."""
    
    def __init__(self, config: LLMConfig):
        """Initialize Gemini service with configuration."""
        super().__init__(config)
        self.client = genai.Client(api_key=self.config.api_key)
        self.logger = get_logger(__name__)
        self.error_handler = LLMErrorHandler()
        self.retry_config = self.error_handler.get_retry_config("gemini")
    
    def validate_config(self) -> None:
        """Validate Gemini-specific configuration."""
        try:
            if not self.config.api_key:
                raise LLMException(
                    "MISSING_API_KEY",
                    "API key is required for Gemini provider",
                    {"provider": "gemini"}
                )
            
            if not self.config.model:
                raise LLMException(
                    "MISSING_MODEL",
                    "Model name is required for Gemini provider",
                    {"provider": "gemini"}
                )
            
            # Validate model name format (basic check)
            if not self.config.model.startswith('gemini'):
                self.logger.warning(f"Model name '{self.config.model}' doesn't start with 'gemini'")
                
        except Exception as e:
            if isinstance(e, LLMException):
                raise
            error_response = self.error_handler.handle_authentication_error("gemini", e)
            raise LLMException(error_response.error_code, error_response.message, error_response.details)
    
    async def _call_gemini_api(
        self, 
        prompt: str, 
        response_model: type[BaseModel]
    ) -> BaseModel:
        """Make API call to Gemini with comprehensive error handling.
        
        Args:
            prompt: The prompt to send to Gemini
            response_model: Pydantic model for response validation
            
        Returns:
            Validated response model instance
            
        Raises:
            LLMException: If API call fails or response is invalid
        """
        start_time = time.time()
        prompt_size = len(prompt)
        
        try:
            # Make API call to Gemini
            api_resp = await self.client.aio.models.generate_content(
                model=self.config.model,
                contents=f"{prompt}\n\nPlease ensure your response is valid JSON matching the requested format.",
            )
            
            duration = time.time() - start_time
            
            # Log successful API interaction
            response_size = len(getattr(api_resp, 'text', '')) if hasattr(api_resp, 'text') else 0
            log_performance_metrics(
                self.logger, 
                "gemini_api_call", 
                duration,
                prompt_size=prompt_size,
                response_size=response_size,
                model=self.config.model
            )
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Handle specific Gemini API errors
            error_str = str(e).lower()
            
            if "authentication" in error_str or "api key" in error_str:
                error_response = self.error_handler.handle_authentication_error("gemini", e)
                raise LLMException(error_response.error_code, error_response.message, error_response.details)
            
            elif "rate limit" in error_str or "quota" in error_str:
                error_response = self.error_handler.handle_rate_limit_error("gemini", e)
                raise LLMException(error_response.error_code, error_response.message, error_response.details)
            
            elif "model" in error_str and ("not found" in error_str or "invalid" in error_str):
                error_response = self.error_handler.handle_model_error("gemini", self.config.model, e)
                raise LLMException(error_response.error_code, error_response.message, error_response.details)
            
            else:
                log_error_with_context(
                    self.logger, e, 
                    {"provider": "gemini", "model": self.config.model, "prompt_size": prompt_size},
                    "gemini_api_call"
                )
                raise LLMException(
                    "GEMINI_API_ERROR", 
                    f"Gemini API call failed: {str(e)}",
                    {"provider": "gemini", "model": self.config.model, "duration": duration}
                )
        
        # Parse and validate response
        try:
            response_text = api_resp.text
            
            if not response_text:
                error_response = self.error_handler.handle_response_parsing_error("gemini", api_resp, 
                                                                                ValueError("Empty response"))
                raise LLMException(error_response.error_code, error_response.message, error_response.details)
            
            # Extract JSON from markdown code blocks if present
            if "```json" in response_text and "```" in response_text:
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1).strip()
                else:
                    error_response = self.error_handler.handle_response_parsing_error("gemini", response_text,
                                                                                    ValueError("Could not extract JSON from markdown"))
                    raise LLMException(error_response.error_code, error_response.message, error_response.details)
            else:
                json_content = response_text.strip()
            
            # Parse JSON
            parsed_json = json.loads(json_content)
            
        except json.JSONDecodeError as e:
            error_response = self.error_handler.handle_response_parsing_error("gemini", response_text, e)
            raise LLMException(error_response.error_code, error_response.message, error_response.details)
        except Exception as e:
            if isinstance(e, LLMException):
                raise
            error_response = self.error_handler.handle_response_parsing_error("gemini", response_text, e)
            raise LLMException(error_response.error_code, error_response.message, error_response.details)
        
        # Validate against response model
        try:
            validated = response_model.model_validate(parsed_json)
        except ValidationError as ve:
            log_error_with_context(
                self.logger, ve,
                {"provider": "gemini", "model": self.config.model, "parsed_json": parsed_json},
                "gemini_response_validation"
            )
            error_response = self.error_handler.handle_response_parsing_error("gemini", parsed_json, ve)
            raise LLMException(error_response.error_code, error_response.message, error_response.details)
        
        return validated
    
    @with_error_handling(context="gemini_get_proposed_changes")
    async def get_proposed_changes(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[ProposedChange]:
        """Get proposed changes from Gemini for the given instruction.
        
        Args:
            map_entries: List of map entries representing the JSON document
            instruction: Natural language instruction for editing
            
        Returns:
            List of proposed changes
            
        Raises:
            LLMException: If Gemini service fails or returns invalid response
        """
        start_time = time.time()
        
        # Build the prompt for Gemini
        map_text = "\n".join([
            f"ID: {entry.id}, Path: {' -> '.join(entry.path)}, Value: {entry.value}"
            for entry in map_entries
        ])
        
        prompt = f"""You are a JSON editor assistant. Given a JSON document represented as a map of entries and a natural language instruction, identify which entries need to be modified and propose the changes.

JSON Document Map:
{map_text}

Instruction: {instruction}

Analyze the instruction and identify which entries need to be changed. For each change, provide:
- id: The ID of the map entry to change
- path: The JSON path as a list of strings
- current_value: The current value at that path
- proposed_value: The new value to set
- confidence: A confidence score between 0.0 and 1.0

Return your response in this JSON format:
{{
    "changes": [
        {{
            "id": "entry_id",
            "path": ["key1", "key2"],
            "current_value": "current value",
            "proposed_value": "new value",
            "confidence": 0.95
        }}
    ],
    "has_changes": true,
    "message": "Optional message about the changes"
}}

If no changes are needed, return:
{{
    "changes": [],
    "has_changes": false,
    "message": "No changes needed"
}}"""
        
        try:
            response = await self._call_gemini_api(prompt, ProposedChangesResponse)
            
            # Convert response to ProposedChange objects
            proposed_changes = []
            for change_data in response.changes:
                try:
                    proposed_change = ProposedChange(
                        id=change_data["id"],
                        path=change_data["path"],
                        current_value=change_data["current_value"],
                        proposed_value=change_data["proposed_value"],
                        confidence=change_data.get("confidence", 1.0)
                    )
                    proposed_changes.append(proposed_change)
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Invalid change data from Gemini: {e}")
                    continue
            
            duration = time.time() - start_time
            log_performance_metrics(
                self.logger,
                "get_proposed_changes",
                duration,
                map_entries_count=len(map_entries),
                instruction_length=len(instruction),
                changes_count=len(proposed_changes)
            )
            
            return proposed_changes
            
        except Exception as e:
            if isinstance(e, LLMException):
                raise
            log_error_with_context(
                self.logger, e,
                {"provider": "gemini", "instruction_length": len(instruction), "map_entries_count": len(map_entries)},
                "get_proposed_changes"
            )
            raise LLMException(
                "GEMINI_CHANGES_ERROR", 
                f"Failed to get proposed changes: {str(e)}",
                {"provider": "gemini", "operation": "get_proposed_changes"}
            )
    
    @with_error_handling(context="gemini_handle_ambiguous_instruction")
    async def handle_ambiguous_instruction(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[str]:
        """Generate suggestions for ambiguous instructions using Gemini.
        
        Args:
            map_entries: List of map entries representing the JSON document
            instruction: Ambiguous natural language instruction
            
        Returns:
            List of suggested clarifications
            
        Raises:
            LLMException: If Gemini service fails
        """
        start_time = time.time()
        
        # Build context about available fields
        available_fields = set()
        for entry in map_entries:
            available_fields.update(entry.path)
        
        fields_text = ", ".join(sorted(available_fields))
        
        prompt = f"""You are a JSON editor assistant. The user provided an instruction that might be ambiguous or unclear. Help clarify what they might want to do.

Available fields in the JSON document: {fields_text}

User instruction: "{instruction}"

The instruction seems ambiguous. Provide 3-5 specific suggestions for what the user might want to do. Each suggestion should be a clear, actionable instruction that could be used to edit the JSON document.

Return your response in this JSON format:
{{
    "suggestions": [
        "Clear suggestion 1",
        "Clear suggestion 2", 
        "Clear suggestion 3"
    ],
    "message": "Optional explanation of why the instruction was ambiguous"
}}"""
        
        try:
            response = await self._call_gemini_api(prompt, SuggestionsResponse)
            
            duration = time.time() - start_time
            log_performance_metrics(
                self.logger,
                "handle_ambiguous_instruction",
                duration,
                instruction_length=len(instruction),
                available_fields_count=len(available_fields),
                suggestions_count=len(response.suggestions)
            )
            
            return response.suggestions
            
        except Exception as e:
            if isinstance(e, LLMException):
                raise
            log_error_with_context(
                self.logger, e,
                {"provider": "gemini", "instruction": instruction, "available_fields_count": len(available_fields)},
                "handle_ambiguous_instruction"
            )
            raise LLMException(
                "GEMINI_SUGGESTIONS_ERROR", 
                f"Failed to get instruction suggestions: {str(e)}",
                {"provider": "gemini", "operation": "handle_ambiguous_instruction"}
            )
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get Gemini-specific retry configuration."""
        base_config = super().get_retry_config()
        
        # Add Gemini-specific retry settings
        base_config.update({
            "provider": "gemini",
            "exponential_base": 2,
            "max_wait": 30,
            "jitter": True,
        })
        
        return base_config