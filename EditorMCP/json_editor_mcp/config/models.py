"""Configuration models for the JSON Editor MCP tool."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class LLMConfig(BaseModel):
    """Configuration for LLM service providers."""
    
    provider: str = Field(..., description="LLM provider: 'gemini', 'openai', or 'custom'")
    api_key: Optional[str] = Field(None, description="API key for the LLM service")
    endpoint: Optional[str] = Field(None, description="Custom endpoint URL for LLM service")
    model: str = Field(..., description="Model name to use")
    timeout: int = Field(30, description="Request timeout in seconds", ge=1, le=300)
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom headers for authentication")
    auth_token: Optional[str] = Field(None, description="Alternative authentication token")
    retry_attempts: int = Field(3, description="Maximum number of retry attempts", ge=0, le=10)
    backoff_factor: float = Field(2.0, description="Exponential backoff factor", ge=1.0, le=10.0)
    max_retries: int = Field(3, description="Maximum number of retry attempts", ge=0, le=10)
    retry_delay: float = Field(1.0, description="Initial retry delay in seconds", ge=0.1, le=60.0)
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        """Validate that provider is one of the supported options."""
        allowed_providers = {'gemini', 'openai', 'custom'}
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of: {', '.join(allowed_providers)}")
        return v
    
    @model_validator(mode='after')
    def validate_provider_requirements(self):
        """Validate provider-specific requirements."""
        if self.provider == 'custom' and not self.endpoint:
            raise ValueError("Endpoint is required when using custom provider")
        
        if self.provider in {'gemini', 'openai'} and not self.api_key:
            raise ValueError(f"API key is required for {self.provider} provider")
        
        return self


class RedisConfig(BaseModel):
    """Configuration for Redis session storage."""
    
    host: str = Field("localhost", description="Redis server hostname")
    port: int = Field(6379, description="Redis server port", ge=1, le=65535)
    password: Optional[str] = Field(None, description="Redis server password")
    db: int = Field(0, description="Redis database number", ge=0, le=15)
    connection_timeout: int = Field(5, description="Connection timeout in seconds", ge=1, le=60)
    socket_timeout: int = Field(5, description="Socket timeout in seconds", ge=1, le=60)
    max_connections: int = Field(10, description="Maximum connections in pool", ge=1, le=100)
    session_expiration: int = Field(86400, description="Session expiration time in seconds", ge=60, le=604800)


class PromptsConfig(BaseModel):
    """Configuration for prompt management."""
    
    system_prompt_file: str = Field(
        "prompts/system_prompt.txt",
        description="Path to system prompt file"
    )
    edit_instruction_template: str = Field(
        "prompts/templates/edit_instruction.txt",
        description="Path to edit instruction template"
    )
    guardrails_prompt_file: str = Field(
        "prompts/guardrails_prompt.txt",
        description="Path to guardrails prompt file"
    )
    templates: Optional[Dict[str, str]] = Field(
        None,
        description="Additional template files for different scenarios"
    )
    
    @field_validator('system_prompt_file', 'edit_instruction_template', 'guardrails_prompt_file')
    @classmethod
    def validate_file_paths(cls, v):
        """Validate that file paths are not empty."""
        if not v or not v.strip():
            raise ValueError("Prompt file paths cannot be empty")
        return v.strip()


class GuardrailsConfig(BaseModel):
    """Configuration for guardrails and validation."""
    
    enabled: bool = Field(True, description="Enable guardrails validation")
    max_changes_per_request: int = Field(
        50, 
        description="Maximum number of changes per request", 
        ge=1, 
        le=1000
    )
    forbidden_patterns: List[str] = Field(
        default_factory=list,
        description="List of forbidden patterns in instructions"
    )
    allowed_json_types: List[str] = Field(
        default_factory=lambda: ["string", "number", "boolean", "array", "object"],
        description="List of allowed JSON value types"
    )
    prevent_deletions: bool = Field(
        True, 
        description="Prevent complete deletion of JSON keys/fields"
    )
    deletion_keywords: List[str] = Field(
        default_factory=lambda: ["delete", "remove", "clear", "erase", "eliminate"],
        description="Keywords that indicate deletion operations"
    )
    allow_empty_values: bool = Field(
        True, 
        description="Allow setting values to empty string"
    )
    max_instruction_length: int = Field(
        5000, 
        description="Maximum length of instruction text", 
        ge=10, 
        le=50000
    )
    
    @field_validator('allowed_json_types')
    @classmethod
    def validate_json_types(cls, v):
        """Validate that JSON types are valid."""
        valid_types = {"string", "number", "boolean", "array", "object", "null"}
        invalid_types = set(v) - valid_types
        if invalid_types:
            raise ValueError(f"Invalid JSON types: {', '.join(invalid_types)}")
        return v


class PerformanceConfig(BaseModel):
    """Configuration for performance settings."""
    
    max_concurrent_requests: int = Field(
        10, 
        description="Maximum concurrent requests", 
        ge=1, 
        le=100
    )
    request_timeout: int = Field(
        120, 
        description="Request processing timeout in seconds", 
        ge=10, 
        le=600
    )
    memory_limit_mb: int = Field(
        512, 
        description="Memory limit for JSON processing in MB", 
        ge=64, 
        le=4096
    )
    max_nesting_depth: int = Field(
        100, 
        description="Maximum JSON nesting depth", 
        ge=10, 
        le=1000
    )


class MonitoringConfig(BaseModel):
    """Configuration for monitoring and metrics."""
    
    enabled: bool = Field(False, description="Enable metrics collection")
    metrics_endpoint: str = Field("/metrics", description="Metrics export endpoint")
    health_endpoint: str = Field("/health", description="Health check endpoint")
    track_requests: bool = Field(True, description="Request tracking")
    track_performance: bool = Field(True, description="Performance monitoring")
    track_llm_performance: bool = Field(True, description="LLM provider performance tracking")
    track_errors: bool = Field(True, description="Error rate tracking")
    alert_thresholds: Optional[Dict[str, float]] = Field(
        None, description="Custom alert thresholds"
    )
    monitoring_interval_seconds: int = Field(
        30, description="Monitoring check interval", ge=10, le=300
    )
    report_interval_seconds: int = Field(
        300, description="Periodic report interval", ge=60, le=3600
    )
    max_history_size: int = Field(
        1000, description="Maximum history size for metrics", ge=100, le=10000
    )


class ServerConfig(BaseModel):
    """Main configuration container for the JSON Editor MCP server."""
    
    llm_config: LLMConfig = Field(..., description="LLM service configuration")
    redis_config: Optional[RedisConfig] = Field(
        None,
        description="Optional Redis configuration for persistent session storage"
    )
    prefer_redis: bool = Field(
        False,
        description="Prefer Redis over memory storage when both are available"
    )
    # Note: Configuration sections with defaults
    prompts_config: PromptsConfig = Field(
        default=PromptsConfig(
            system_prompt_file="prompts/system_prompt.txt",
            edit_instruction_template="prompts/templates/edit_instruction.txt", 
            guardrails_prompt_file="prompts/guardrails_prompt.txt",
            templates=None
        ),
        description="Prompts configuration"
    )
    guardrails_config: GuardrailsConfig = Field(
        default=GuardrailsConfig(
            enabled=True,
            max_changes_per_request=50,
            forbidden_patterns=[],
            allowed_json_types=["string", "number", "boolean", "array", "object"],
            prevent_deletions=True,
            deletion_keywords=["delete", "remove", "clear", "erase", "eliminate"],
            allow_empty_values=True,
            max_instruction_length=5000
        ),
        description="Guardrails configuration"
    )
    performance_config: Optional[PerformanceConfig] = Field(
        default=PerformanceConfig(
            max_concurrent_requests=10,
            request_timeout=120,
            memory_limit_mb=512,
            max_nesting_depth=100
        ),
        description="Performance configuration"
    )
    monitoring_config: Optional[MonitoringConfig] = Field(
        default=MonitoringConfig(
            enabled=False,
            metrics_endpoint="/metrics",
            health_endpoint="/health",
            track_requests=True,
            track_performance=True,
            track_llm_performance=True,
            track_errors=True,
            alert_thresholds=None,
            monitoring_interval_seconds=30,
            report_interval_seconds=300,
            max_history_size=1000
        ),
        description="Monitoring configuration"
    )
    server_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional server configuration"
    )
    max_document_size: int = Field(
        10485760,  # 10MB
        description="Maximum document size in bytes",
        ge=1024,  # 1KB minimum
        le=104857600  # 100MB maximum
    )
    log_level: str = Field(
        "INFO",
        description="Logging level"
    )
    session_ttl: int = Field(
        3600,  # 1 hour
        description="Session TTL in seconds",
        ge=60,  # 1 minute minimum
        le=86400  # 24 hours maximum
    )
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate that log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    model_config = {
        "validate_assignment": True,
        "extra": "forbid",  # Forbid extra fields
        "use_enum_values": True
    }