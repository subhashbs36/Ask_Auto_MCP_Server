"""Abstract interface for LLM service providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models.core import MapEntry, ProposedChange
from ..config.models import LLMConfig


class LLMServiceInterface(ABC):
    """Abstract base class for LLM service providers."""
    
    def __init__(self, config: LLMConfig):
        """Initialize the LLM service with configuration.
        
        Args:
            config: LLM configuration containing provider-specific settings
        """
        self.config = config
        self.validate_config()
    
    @abstractmethod
    def validate_config(self) -> None:
        """Validate provider-specific configuration.
        
        Raises:
            ValueError: If configuration is invalid or missing required fields
        """
        pass
    
    @abstractmethod
    async def get_proposed_changes(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[ProposedChange]:
        """Get proposed changes from LLM without applying them.
        
        Args:
            map_entries: List of map entries representing the JSON document
            instruction: Natural language instruction for editing
            
        Returns:
            List of proposed changes with confidence scores
            
        Raises:
            LLMException: If LLM service fails or returns invalid response
        """
        pass
    
    @abstractmethod
    async def handle_ambiguous_instruction(
        self, 
        map_entries: List[MapEntry], 
        instruction: str
    ) -> List[str]:
        """Generate suggestions for ambiguous instructions.
        
        Args:
            map_entries: List of map entries representing the JSON document
            instruction: Ambiguous natural language instruction
            
        Returns:
            List of suggested clarifications or alternative instructions
            
        Raises:
            LLMException: If LLM service fails
        """
        pass
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get provider-specific retry and backoff configuration.
        
        Returns:
            Dictionary containing retry configuration parameters
        """
        return {
            "max_retries": self.config.max_retries,
            "retry_delay": self.config.retry_delay,
            "timeout": self.config.timeout,
        }
    
    def get_provider_name(self) -> str:
        """Get the provider name for this service.
        
        Returns:
            Provider name string
        """
        return self.config.provider
    
    def get_model_name(self) -> str:
        """Get the model name for this service.
        
        Returns:
            Model name string
        """
        return self.config.model
    
    async def health_check(self) -> bool:
        """Check if the LLM service is healthy and accessible.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Basic health check - can be overridden by specific implementations
            return True
        except Exception:
            return False