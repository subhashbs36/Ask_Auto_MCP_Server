"""OpenAI LLM service adapter implementation."""

import json
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from pydantic import BaseModel, ValidationError

from .interface import LLMServiceInterface
from ..models.core import MapEntry, ProposedChange
from ..models.errors import LLMException
from ..config.models import LLMConfig


class ProposedChangesResponse(BaseModel):
    """Response model for proposed changes from OpenAI."""
    changes: List[Dict[str, Any]]
    has_changes: bool = True
    message: Optional[str] = None


class SuggestionsResponse(BaseModel):
    """Response model for instruction suggestions from OpenAI."""
    suggestions: List[str]
    message: Optional[str] = None


class OpenAILLMService(LLMServiceInterface):
    """OpenAI LLM service adapter using OpenAI SDK."""
    
    def __init__(self, config: LLMConfig):
        """Initialize OpenAI service with configuration."""
        super().__init__(config)
        self.client = AsyncOpenAI(api_key=self.config.api_key)
        self.logger = logging.getLogger(__name__)
    
    def validate_config(self) -> None:
        """Validate OpenAI-specific configuration."""
        if not self.config.api_key:
            raise ValueError("API key is required for OpenAI provider")
        
        if not self.config.model:
            raise ValueError("Model name is required for OpenAI provider")
        
        # Validate model name format (basic check for common OpenAI models)
        valid_prefixes = ['gpt-', 'text-', 'davinci', 'curie', 'babbage', 'ada']
        if not any(self.config.model.startswith(prefix) for prefix in valid_prefixes):
            self.logger.warning(f"Model name '{self.config.model}' doesn't match common OpenAI model patterns")
    
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(LLMException),
    )
    async def _call_openai_api(
        self, 
        prompt: str, 
        response_model: type[BaseModel]
    ) -> BaseModel:
        """Make API call to OpenAI with retry logic.
        
        Args:
            prompt: The prompt to send to OpenAI
            response_model: Pydantic model for response validation
            
        Returns:
            Validated response model instance
            
        Raises:
            LLMException: If API call fails or response is invalid
        """
        try:
            # Make API call to OpenAI
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON editor assistant. Always respond with valid JSON in the requested format."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent responses
                timeout=self.config.timeout,
            )
        except Exception as e:
            self.logger.error(f"OpenAI API call error: {e}")
            raise LLMException("OPENAI_API_ERROR", f"OpenAI API call failed: {e}")
        
        # Parse and validate response
        try:
            response_text = response.choices[0].message.content
            
            if not response_text:
                raise ValueError("Empty response from OpenAI API")
            
            # Parse JSON response
            parsed_json = json.loads(response_text.strip())
            
        except Exception as e:
            self.logger.error(f"Failed to parse OpenAI response: {e}")
            self.logger.error(f"Raw response: {response_text}")
            raise LLMException("OPENAI_PARSE_ERROR", f"Failed to parse OpenAI response: {e}")
        
        # Validate against response model
        try:
            validated = response_model.model_validate(parsed_json)
        except ValidationError as ve:
            self.logger.error(f"OpenAI response validation error: {ve}")
            self.logger.error(f"Raw parsed JSON: {parsed_json}")
            raise LLMException("OPENAI_VALIDATION_ERROR", f"OpenAI response validation error: {ve}")
        
        return validated
    
    async def get_proposed_changes(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[ProposedChange]:
        """Get proposed changes from OpenAI for the given instruction.
        
        Args:
            map_entries: List of map entries representing the JSON document
            instruction: Natural language instruction for editing
            
        Returns:
            List of proposed changes
            
        Raises:
            LLMException: If OpenAI service fails or returns invalid response
        """
        # Build the prompt for OpenAI
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
            response = await self._call_openai_api(prompt, ProposedChangesResponse)
            
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
                    self.logger.warning(f"Invalid change data from OpenAI: {e}")
                    continue
            
            return proposed_changes
            
        except Exception as e:
            self.logger.error(f"Error getting proposed changes from OpenAI: {e}")
            raise LLMException("OPENAI_CHANGES_ERROR", f"Failed to get proposed changes: {e}")
    
    async def handle_ambiguous_instruction(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[str]:
        """Generate suggestions for ambiguous instructions using OpenAI.
        
        Args:
            map_entries: List of map entries representing the JSON document
            instruction: Ambiguous natural language instruction
            
        Returns:
            List of suggested clarifications
            
        Raises:
            LLMException: If OpenAI service fails
        """
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
            response = await self._call_openai_api(prompt, SuggestionsResponse)
            return response.suggestions
            
        except Exception as e:
            self.logger.error(f"Error getting suggestions from OpenAI: {e}")
            raise LLMException("OPENAI_SUGGESTIONS_ERROR", f"Failed to get instruction suggestions: {e}")
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get OpenAI-specific retry configuration."""
        base_config = super().get_retry_config()
        
        # Add OpenAI-specific retry settings
        base_config.update({
            "provider": "openai",
            "exponential_base": 2,
            "max_wait": 60,  # OpenAI can have longer delays
            "jitter": True,
            "rate_limit_aware": True,
        })
        
        return base_config