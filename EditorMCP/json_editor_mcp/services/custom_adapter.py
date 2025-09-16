"""Custom LLM service adapter implementation for custom endpoints."""

import json
import logging
from typing import List, Dict, Any, Optional
import aiohttp
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
    """Response model for proposed changes from custom LLM."""
    changes: List[Dict[str, Any]]
    has_changes: bool = True
    message: Optional[str] = None


class SuggestionsResponse(BaseModel):
    """Response model for instruction suggestions from custom LLM."""
    suggestions: List[str]
    message: Optional[str] = None


class CustomLLMService(LLMServiceInterface):
    """Custom LLM service adapter for custom endpoints."""
    
    def __init__(self, config: LLMConfig):
        """Initialize custom LLM service with configuration."""
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        
        # Set up authentication headers
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "JSON-Editor-MCP-Tool/1.0"
        }
        
        # Add authentication headers based on configuration
        if self.config.api_key:
            self.headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        # Add any custom headers from config
        if hasattr(self.config, 'custom_headers') and self.config.custom_headers:
            self.headers.update(self.config.custom_headers)
    
    def validate_config(self) -> None:
        """Validate custom LLM-specific configuration."""
        if not self.config.endpoint:
            raise ValueError("Endpoint URL is required for custom provider")
        
        if not self.config.model:
            raise ValueError("Model name is required for custom provider")
        
        # Validate endpoint URL format
        if not (self.config.endpoint.startswith('http://') or 
                self.config.endpoint.startswith('https://')):
            raise ValueError("Endpoint must be a valid HTTP/HTTPS URL")
    
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(LLMException),
    )
    async def _call_custom_api(
        self, 
        prompt: str, 
        response_model: type[BaseModel]
    ) -> BaseModel:
        """Make API call to custom LLM endpoint with retry logic.
        
        Args:
            prompt: The prompt to send to the custom LLM
            response_model: Pydantic model for response validation
            
        Returns:
            Validated response model instance
            
        Raises:
            LLMException: If API call fails or response is invalid
        """
        # Prepare request payload (OpenAI-compatible format by default)
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a JSON editor assistant. Always respond with valid JSON in the requested format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
        }
        
        try:
            # Make HTTP request to custom endpoint
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.config.endpoint,
                    headers=self.headers,
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")
                    
                    response_data = await response.json()
                    
        except Exception as e:
            self.logger.error(f"Custom LLM API call error: {e}")
            raise LLMException("CUSTOM_API_ERROR", f"Custom LLM API call failed: {e}")
        
        # Parse response (assuming OpenAI-compatible format)
        try:
            if "choices" in response_data and len(response_data["choices"]) > 0:
                response_text = response_data["choices"][0]["message"]["content"]
            elif "response" in response_data:
                # Alternative response format
                response_text = response_data["response"]
            elif "text" in response_data:
                # Another alternative format
                response_text = response_data["text"]
            else:
                raise ValueError(f"Unexpected response format: {response_data}")
            
            if not response_text:
                raise ValueError("Empty response from custom LLM API")
            
            # Parse JSON response
            parsed_json = json.loads(response_text.strip())
            
        except Exception as e:
            self.logger.error(f"Failed to parse custom LLM response: {e}")
            self.logger.error(f"Raw response: {response_data}")
            raise LLMException("CUSTOM_PARSE_ERROR", f"Failed to parse custom LLM response: {e}")
        
        # Validate against response model
        try:
            validated = response_model.model_validate(parsed_json)
        except ValidationError as ve:
            self.logger.error(f"Custom LLM response validation error: {ve}")
            self.logger.error(f"Raw parsed JSON: {parsed_json}")
            raise LLMException("CUSTOM_VALIDATION_ERROR", f"Custom LLM response validation error: {ve}")
        
        return validated
    
    async def get_proposed_changes(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[ProposedChange]:
        """Get proposed changes from custom LLM for the given instruction.
        
        Args:
            map_entries: List of map entries representing the JSON document
            instruction: Natural language instruction for editing
            
        Returns:
            List of proposed changes
            
        Raises:
            LLMException: If custom LLM service fails or returns invalid response
        """
        # Build the prompt for custom LLM
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
            response = await self._call_custom_api(prompt, ProposedChangesResponse)
            
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
                    self.logger.warning(f"Invalid change data from custom LLM: {e}")
                    continue
            
            return proposed_changes
            
        except Exception as e:
            self.logger.error(f"Error getting proposed changes from custom LLM: {e}")
            raise LLMException("CUSTOM_CHANGES_ERROR", f"Failed to get proposed changes: {e}")
    
    async def handle_ambiguous_instruction(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[str]:
        """Generate suggestions for ambiguous instructions using custom LLM.
        
        Args:
            map_entries: List of map entries representing the JSON document
            instruction: Ambiguous natural language instruction
            
        Returns:
            List of suggested clarifications
            
        Raises:
            LLMException: If custom LLM service fails
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
            response = await self._call_custom_api(prompt, SuggestionsResponse)
            return response.suggestions
            
        except Exception as e:
            self.logger.error(f"Error getting suggestions from custom LLM: {e}")
            raise LLMException("CUSTOM_SUGGESTIONS_ERROR", f"Failed to get instruction suggestions: {e}")
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get custom LLM-specific retry configuration."""
        base_config = super().get_retry_config()
        
        # Add custom LLM-specific retry settings
        base_config.update({
            "provider": "custom",
            "endpoint": self.config.endpoint,
            "exponential_base": 2,
            "max_wait": 45,
            "jitter": True,
            "http_timeout": self.config.timeout,
        })
        
        return base_config