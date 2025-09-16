"""Configuration loader for the JSON Editor MCP tool."""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import ValidationError
from dotenv import load_dotenv

from .models import ServerConfig, LLMConfig, RedisConfig, PromptsConfig, GuardrailsConfig


class ConfigurationError(Exception):
    """Raised when configuration loading or validation fails."""
    pass


class ConfigLoader:
    """Loads and validates configuration from multiple sources."""
    
    def __init__(self, config_file: Optional[str] = None, env_file: Optional[str] = None):
        """Initialize the configuration loader.
        
        Args:
            config_file: Optional path to YAML configuration file
            env_file: Optional path to .env file (defaults to .env in current directory)
        """
        self.config_file = config_file or "config.yaml"
        self.env_file = env_file or ".env"
        
        # Load .env file if it exists
        self._load_env_file()
    
    def _load_env_file(self) -> None:
        """Load environment variables from .env file if it exists."""
        env_path = Path(self.env_file)
        if env_path.exists():
            load_dotenv(env_path)
        else:
            # Try to find .env file in current working directory or config file directory
            cwd_env = Path.cwd() / ".env"
            if cwd_env.exists():
                load_dotenv(cwd_env)
            elif self.config_file:
                config_dir_env = Path(self.config_file).parent / ".env"
                if config_dir_env.exists():
                    load_dotenv(config_dir_env)
    
    def load_config(self) -> ServerConfig:
        """Load configuration from environment variables and YAML file.
        
        Returns:
            ServerConfig: Validated server configuration
            
        Raises:
            ConfigurationError: If configuration loading or validation fails
        """
        try:
            # Start with default configuration
            config_data = {}
            
            # Load from YAML file if it exists
            yaml_config = self._load_yaml_config()
            if yaml_config:
                config_data.update(yaml_config)
            
            # Override with environment variables
            env_config = self._load_env_config()
            config_data = self._merge_configs(config_data, env_config)
            
            # Validate and create ServerConfig
            return ServerConfig(**config_data)
            
        except ValidationError as e:
            error_details = self._format_validation_errors(e)
            raise ConfigurationError(f"Configuration validation failed:\n{error_details}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")
    
    def _load_yaml_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file.
        
        Returns:
            Dict containing YAML configuration or None if file doesn't exist
        """
        config_path = Path(self.config_file)
        if not config_path.exists():
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {self.config_file}: {str(e)}")
        except Exception as e:
            raise ConfigurationError(f"Failed to read {self.config_file}: {str(e)}")
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables.
        
        Returns:
            Dict containing environment-based configuration
        """
        config = {}
        
        # LLM Configuration
        llm_config = {}
        if os.getenv('LLM_PROVIDER'):
            llm_config['provider'] = os.getenv('LLM_PROVIDER')
        if os.getenv('LLM_API_KEY'):
            llm_config['api_key'] = os.getenv('LLM_API_KEY')
        # Support direct API key environment variables
        elif os.getenv('GEMINI_API_KEY'):
            llm_config['api_key'] = os.getenv('GEMINI_API_KEY')
        elif os.getenv('OPENAI_API_KEY'):
            llm_config['api_key'] = os.getenv('OPENAI_API_KEY')
        if os.getenv('LLM_ENDPOINT'):
            llm_config['endpoint'] = os.getenv('LLM_ENDPOINT')
        if os.getenv('LLM_MODEL'):
            llm_config['model'] = os.getenv('LLM_MODEL')
        if os.getenv('LLM_TIMEOUT'):
            llm_config['timeout'] = int(os.getenv('LLM_TIMEOUT'))
        if os.getenv('LLM_MAX_RETRIES'):
            llm_config['max_retries'] = int(os.getenv('LLM_MAX_RETRIES'))
        if os.getenv('LLM_RETRY_DELAY'):
            llm_config['retry_delay'] = float(os.getenv('LLM_RETRY_DELAY'))
        
        if llm_config:
            config['llm_config'] = llm_config
        
        # Redis Configuration
        redis_config = {}
        if os.getenv('REDIS_HOST'):
            redis_config['host'] = os.getenv('REDIS_HOST')
        if os.getenv('REDIS_PORT'):
            redis_config['port'] = int(os.getenv('REDIS_PORT'))
        if os.getenv('REDIS_PASSWORD'):
            redis_config['password'] = os.getenv('REDIS_PASSWORD')
        if os.getenv('REDIS_DB'):
            redis_config['db'] = int(os.getenv('REDIS_DB'))
        if os.getenv('REDIS_CONNECTION_TIMEOUT'):
            redis_config['connection_timeout'] = int(os.getenv('REDIS_CONNECTION_TIMEOUT'))
        if os.getenv('REDIS_SOCKET_TIMEOUT'):
            redis_config['socket_timeout'] = int(os.getenv('REDIS_SOCKET_TIMEOUT'))
        if os.getenv('REDIS_MAX_CONNECTIONS'):
            redis_config['max_connections'] = int(os.getenv('REDIS_MAX_CONNECTIONS'))
        
        if redis_config:
            config['redis_config'] = redis_config
        
        # Prompts Configuration
        prompts_config = {}
        if os.getenv('SYSTEM_PROMPT_FILE'):
            prompts_config['system_prompt_file'] = os.getenv('SYSTEM_PROMPT_FILE')
        if os.getenv('EDIT_INSTRUCTION_TEMPLATE'):
            prompts_config['edit_instruction_template'] = os.getenv('EDIT_INSTRUCTION_TEMPLATE')
        if os.getenv('GUARDRAILS_PROMPT_FILE'):
            prompts_config['guardrails_prompt_file'] = os.getenv('GUARDRAILS_PROMPT_FILE')
        
        if prompts_config:
            config['prompts_config'] = prompts_config
        
        # Guardrails Configuration
        guardrails_config = {}
        if os.getenv('GUARDRAILS_ENABLED'):
            guardrails_config['enabled'] = os.getenv('GUARDRAILS_ENABLED').lower() == 'true'
        if os.getenv('MAX_CHANGES_PER_REQUEST'):
            guardrails_config['max_changes_per_request'] = int(os.getenv('MAX_CHANGES_PER_REQUEST'))
        if os.getenv('FORBIDDEN_PATTERNS'):
            guardrails_config['forbidden_patterns'] = os.getenv('FORBIDDEN_PATTERNS').split(',')
        if os.getenv('ALLOWED_JSON_TYPES'):
            guardrails_config['allowed_json_types'] = os.getenv('ALLOWED_JSON_TYPES').split(',')
        if os.getenv('PREVENT_DELETIONS'):
            guardrails_config['prevent_deletions'] = os.getenv('PREVENT_DELETIONS').lower() == 'true'
        if os.getenv('DELETION_KEYWORDS'):
            guardrails_config['deletion_keywords'] = os.getenv('DELETION_KEYWORDS').split(',')
        if os.getenv('ALLOW_EMPTY_VALUES'):
            guardrails_config['allow_empty_values'] = os.getenv('ALLOW_EMPTY_VALUES').lower() == 'true'
        if os.getenv('MAX_INSTRUCTION_LENGTH'):
            guardrails_config['max_instruction_length'] = int(os.getenv('MAX_INSTRUCTION_LENGTH'))
        
        if guardrails_config:
            config['guardrails_config'] = guardrails_config
        
        # Server Configuration
        if os.getenv('MAX_DOCUMENT_SIZE'):
            config['max_document_size'] = int(os.getenv('MAX_DOCUMENT_SIZE'))
        if os.getenv('LOG_LEVEL'):
            config['log_level'] = os.getenv('LOG_LEVEL')
        if os.getenv('SESSION_TTL'):
            config['session_ttl'] = int(os.getenv('SESSION_TTL'))
        
        return config
    
    def _merge_configs(self, yaml_config: Dict[str, Any], env_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge YAML and environment configurations with env taking precedence.
        
        Args:
            yaml_config: Configuration from YAML file
            env_config: Configuration from environment variables
            
        Returns:
            Merged configuration dictionary
        """
        merged = yaml_config.copy()
        
        for key, value in env_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Merge nested dictionaries
                merged[key] = {**merged[key], **value}
            else:
                # Override with environment value
                merged[key] = value
        
        return merged
    
    def _format_validation_errors(self, error: ValidationError) -> str:
        """Format Pydantic validation errors into readable messages.
        
        Args:
            error: Pydantic ValidationError
            
        Returns:
            Formatted error message string
        """
        error_messages = []
        for err in error.errors():
            field_path = " -> ".join(str(loc) for loc in err['loc'])
            message = err['msg']
            error_messages.append(f"  {field_path}: {message}")
        
        return "\n".join(error_messages)
    
    def load_from_file(self, config_file: str) -> ServerConfig:
        """Load configuration from a specific YAML file.
        
        Args:
            config_file: Path to YAML configuration file
            
        Returns:
            ServerConfig: Validated server configuration
            
        Raises:
            ConfigurationError: If configuration loading or validation fails
        """
        try:
            config_path = Path(config_file)
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_file}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Substitute environment variables
                content = self._substitute_env_vars(content)
                config_data = yaml.safe_load(content) or {}
            
            return ServerConfig(**config_data)
            
        except ValidationError as e:
            error_details = self._format_validation_errors(e)
            raise ConfigurationError(f"Configuration validation failed:\n{error_details}")
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in {config_file}: {str(e)}")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                raise
            raise ConfigurationError(f"Failed to load configuration from {config_file}: {str(e)}")
    
    def load_from_env(self) -> ServerConfig:
        """Load configuration from environment variables only.
        
        Returns:
            ServerConfig: Validated server configuration
            
        Raises:
            ConfigurationError: If configuration loading or validation fails
        """
        try:
            env_config = self._load_env_config_structured()
            return ServerConfig(**env_config)
            
        except ValidationError as e:
            error_details = self._format_validation_errors(e)
            raise ConfigurationError(f"Configuration validation failed:\n{error_details}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration from environment: {str(e)}")
    
    def load_from_file_and_env(self, config_file: str) -> ServerConfig:
        """Load configuration from file and merge with environment variables.
        
        Args:
            config_file: Path to YAML configuration file
            
        Returns:
            ServerConfig: Validated server configuration
            
        Raises:
            ConfigurationError: If configuration loading or validation fails
        """
        try:
            # Load from file
            config_path = Path(config_file)
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_file}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Substitute environment variables
                content = self._substitute_env_vars(content)
                file_config = yaml.safe_load(content) or {}
            
            # Load from environment
            env_config = self._load_env_config_structured()
            
            # Merge configurations
            merged_config = self._merge_configs(file_config, env_config)
            
            return ServerConfig(**merged_config)
            
        except ValidationError as e:
            error_details = self._format_validation_errors(e)
            raise ConfigurationError(f"Configuration validation failed:\n{error_details}")
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in {config_file}: {str(e)}")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                raise
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")
    
    def validate_prompt_files(self, prompts_config: PromptsConfig) -> None:
        """Validate that prompt files exist.
        
        Args:
            prompts_config: Prompts configuration to validate
            
        Raises:
            FileNotFoundError: If any prompt file is missing
        """
        files_to_check = [
            prompts_config.system_prompt_file,
            prompts_config.guardrails_prompt_file
        ]
        
        for file_path in files_to_check:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Prompt file not found: {file_path}")
    
    def _substitute_env_vars(self, content: str) -> str:
        """Substitute environment variables in YAML content.
        
        Args:
            content: YAML content with potential environment variable references
            
        Returns:
            Content with environment variables substituted
        """
        # Pattern to match ${VAR_NAME} or ${VAR_NAME:-default_value}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_expr = match.group(1)
            if ':-' in var_expr:
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name.strip(), default_value.strip())
            else:
                var_name = var_expr.strip()
                value = os.getenv(var_name)
                return value if value is not None else match.group(0)
        
        return re.sub(pattern, replace_var, content)
    
    def _load_env_config_structured(self) -> Dict[str, Any]:
        """Load configuration from environment variables with structured format.
        
        Returns:
            Dict containing environment-based configuration
        """
        config = {}
        
        # Parse environment variables with JSON_EDITOR_ prefix
        for key, value in os.environ.items():
            if key.startswith('JSON_EDITOR_'):
                # Remove prefix and convert to nested structure
                config_key = key[12:]  # Remove 'JSON_EDITOR_'
                self._set_nested_value(config, config_key, value)
        
        # Debug print to see what we parsed
        # print(f"Parsed env config: {config}")
        
        return config
    
    def _set_nested_value(self, config: Dict[str, Any], key_path: str, value: str) -> None:
        """Set a nested configuration value from a flat environment variable key.
        
        Args:
            config: Configuration dictionary to update
            key_path: Dot-separated key path (e.g., 'LLM_CONFIG_PROVIDER')
            value: String value to set
        """
        # Convert key path to nested structure
        parts = key_path.lower().split('_')
        
        # Handle special case for config sections
        if len(parts) >= 2 and parts[1] == 'config':
            # Convert LLM_CONFIG_PROVIDER to llm_config.provider
            section_name = f"{parts[0]}_config"
            if section_name not in config:
                config[section_name] = {}
            
            # Set the nested value - handle multi-part keys like API_KEY
            current = config[section_name]
            remaining_parts = parts[2:]
            
            # If we have multiple remaining parts, join them with underscore
            if len(remaining_parts) > 1:
                final_key = '_'.join(remaining_parts)
            else:
                final_key = remaining_parts[0] if remaining_parts else 'value'
            
            current[final_key] = self._convert_env_value(value)
        else:
            # Handle direct server-level config values like LOG_LEVEL, MAX_DOCUMENT_SIZE
            if len(parts) == 2 and parts[0] in ['log', 'max', 'session']:
                # Handle LOG_LEVEL -> log_level, MAX_DOCUMENT_SIZE -> max_document_size
                key_name = '_'.join(parts)
                config[key_name] = self._convert_env_value(value)
            elif len(parts) == 1:
                # Handle single values like LOG_LEVEL
                config[parts[0]] = self._convert_env_value(value)
            else:
                # Handle other nested structures
                current = config
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                final_key = parts[-1]
                current[final_key] = self._convert_env_value(value)
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string value to appropriate type.
        
        Args:
            value: String value from environment variable
            
        Returns:
            Converted value (int, float, bool, or string)
        """
        # Try boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Try integer conversion
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float conversion
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def validate_config_file(self, config_file: str) -> bool:
        """Validate a configuration file without loading it.
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            True if configuration is valid
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        original_file = self.config_file
        try:
            self.config_file = config_file
            self.load_config()
            return True
        finally:
            self.config_file = original_file


def load_config(config_file: Optional[str] = None, env_file: Optional[str] = None) -> ServerConfig:
    """Convenience function to load configuration.
    
    Args:
        config_file: Optional path to YAML configuration file
        env_file: Optional path to .env file
        
    Returns:
        ServerConfig: Validated server configuration
        
    Raises:
        ConfigurationError: If configuration loading or validation fails
    """
    loader = ConfigLoader(config_file, env_file)
    return loader.load_config()


def create_example_config() -> Dict[str, Any]:
    """Create an example configuration dictionary.
    
    Returns:
        Dictionary containing example configuration
    """
    return {
        "llm_config": {
            "provider": "gemini",
            "api_key": "your-api-key-here",
            "model": "gemini-pro",
            "timeout": 30,
            "max_retries": 3,
            "retry_delay": 1.0
        },
        "redis_config": {
            "host": "localhost",
            "port": 6379,
            "password": None,
            "db": 0,
            "connection_timeout": 5,
            "socket_timeout": 5,
            "max_connections": 10
        },
        "prompts_config": {
            "system_prompt_file": "prompts/system_prompt.txt",
            "edit_instruction_template": "prompts/templates/edit_instruction.txt",
            "guardrails_prompt_file": "prompts/guardrails_prompt.txt"
        },
        "guardrails_config": {
            "enabled": True,
            "max_changes_per_request": 50,
            "forbidden_patterns": [],
            "allowed_json_types": ["string", "number", "boolean", "array", "object"],
            "prevent_deletions": True,
            "deletion_keywords": ["delete", "remove", "clear", "erase", "eliminate"],
            "allow_empty_values": True,
            "max_instruction_length": 5000
        },
        "max_document_size": 10485760,
        "log_level": "INFO",
        "session_ttl": 3600
    }