# Setup and Configuration Guide

## Prerequisites

### System Requirements

- **Python**: 3.11 or higher
- **Redis**: 6.0 or higher (for session storage)
- **Memory**: Minimum 4GB RAM (8GB recommended for production)
- **Storage**: 10GB available disk space
- **Network**: Stable internet connection for LLM API calls

### Required Dependencies

- `pydantic` (>=2.0.0) - Data validation and models
- `redis` (>=4.0.0) - Session storage
- `mcp` - Model Context Protocol SDK
- `aiohttp` or `httpx` - HTTP client for LLM APIs
- `pyyaml` - Configuration file parsing
- `python-dotenv` - Environment variable loading

### LLM Provider Requirements

Choose one or more LLM providers:

#### Google Gemini
- Google Cloud account with Gemini API access
- API key from Google AI Studio or Google Cloud Console
- `google-generativeai` package

#### OpenAI
- OpenAI account with API access
- API key from OpenAI platform
- `openai` package

#### Custom LLM Endpoint
- Access to a custom LLM server endpoint
- Authentication credentials (API key, token, or custom headers)
- Compatible API format (OpenAI-compatible recommended)

## Installation

### Option 1: From Source

1. **Clone the repository:**
```bash
git clone <repository-url>
cd json-editor-mcp-tool
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Install Redis:**

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS (with Homebrew):**
```bash
brew install redis
brew services start redis
```

**Windows:**
```bash
# Using Windows Subsystem for Linux (WSL) or Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### Option 2: Using Docker

1. **Clone the repository:**
```bash
git clone <repository-url>
cd json-editor-mcp-tool
```

2. **Build and run with Docker Compose:**
```bash
docker-compose up -d
```

This will start both the MCP server and Redis automatically.

### Option 3: Using pip (when published)

```bash
pip install json-editor-mcp-tool
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# LLM Provider Configuration
LLM_PROVIDER=gemini  # Options: gemini, openai, custom
LLM_MODEL=gemini-pro
LLM_TIMEOUT=30
LLM_RETRY_ATTEMPTS=3
LLM_BACKOFF_FACTOR=2.0

# Provider-specific API Keys
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Custom LLM Configuration (if using custom provider)
CUSTOM_LLM_ENDPOINT=https://your-llm-endpoint.com/v1/chat/completions
CUSTOM_LLM_AUTH_TOKEN=your_auth_token
CUSTOM_LLM_MODEL=your_model_name

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # Leave empty if no password
REDIS_CONNECTION_POOL_SIZE=10

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
LOG_LEVEL=INFO
MAX_DOCUMENT_SIZE=10485760  # 10MB in bytes

# Guardrails Configuration
GUARDRAILS_ENABLED=true
MAX_CHANGES_PER_REQUEST=50
```

### Configuration File (config.yaml)

Create a `config.yaml` file for more detailed configuration:

```yaml
# Server Configuration
server:
  host: "0.0.0.0"
  port: 8080
  log_level: "INFO"
  max_document_size: 10485760  # 10MB
  request_timeout: 300  # 5 minutes

# LLM Provider Configuration
llm:
  provider: "gemini"  # Options: gemini, openai, custom
  model: "gemini-pro"
  timeout: 30
  retry_attempts: 3
  backoff_factor: 2.0
  
  # Provider-specific settings
  gemini:
    api_key: "${GEMINI_API_KEY}"
    model: "gemini-pro"
    temperature: 0.1
    max_tokens: 4096
  
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4"
    temperature: 0.1
    max_tokens: 4096
    organization: ""  # Optional
  
  custom:
    endpoint: "${CUSTOM_LLM_ENDPOINT}"
    auth_token: "${CUSTOM_LLM_AUTH_TOKEN}"
    model: "${CUSTOM_LLM_MODEL}"
    headers:
      "Content-Type": "application/json"
      "Authorization": "Bearer ${CUSTOM_LLM_AUTH_TOKEN}"

# Redis Configuration
redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null
  connection_pool_size: 10
  socket_timeout: 5
  socket_connect_timeout: 5
  retry_on_timeout: true
  health_check_interval: 30

# Prompts Configuration
prompts:
  system_prompt_file: "prompts/system_prompt.txt"
  guardrails_prompt_file: "prompts/guardrails_prompt.txt"
  instruction_templates:
    edit: "prompts/templates/edit_instruction.txt"
    replace: "prompts/templates/replace_instruction.txt"
    update: "prompts/templates/update_instruction.txt"

# Guardrails Configuration
guardrails:
  enabled: true
  max_changes_per_request: 50
  max_instruction_length: 1000
  forbidden_patterns:
    - "delete all"
    - "remove everything"
    - "clear all data"
  allowed_json_types:
    - "object"
    - "array"
    - "string"
    - "number"
    - "boolean"
    - "null"
  document_size_limits:
    max_size: 52428800  # 50MB
    max_depth: 100
    max_keys: 10000

# Monitoring Configuration
monitoring:
  enabled: true
  metrics_port: 9090
  health_check_endpoint: "/health"
  readiness_check_endpoint: "/ready"
  log_requests: true
  log_responses: false  # Set to true for debugging
  performance_tracking: true
```

### Prompt Files

Create the required prompt files:

**prompts/system_prompt.txt:**
```text
You are a JSON document editor that helps users modify JSON structures using natural language instructions.

Your task is to:
1. Analyze the provided JSON document structure
2. Understand the user's natural language instruction
3. Identify which specific text nodes need to be modified
4. Propose precise changes without modifying the overall structure

Guidelines:
- Only modify text values, not JSON structure (keys, arrays, objects)
- Be precise about which fields to change
- Maintain data types when possible
- If the instruction is ambiguous, ask for clarification
- Support all modification operations: edit, update, replace, change, delete, remove, swap
- Handle nested objects and arrays correctly
- Preserve JSON formatting and structure

Response format: Provide a list of specific changes with paths and new values.
```

**prompts/guardrails_prompt.txt:**
```text
Safety and validation rules for JSON editing:

1. Input Validation:
   - Verify JSON document is valid and parseable
   - Check document size limits
   - Validate instruction length and content

2. Modification Rules:
   - Allow all types of modifications including deletion and removal
   - Support field/key deletion and removal operations
   - Allow complete data replacement and swapping
   - Maintain JSON structure integrity
   - Preserve data type consistency where appropriate

3. Security Checks:
   - Sanitize user instructions for malicious patterns
   - Prevent code injection attempts
   - Validate against forbidden modification patterns (if configured)
   - Ensure modifications stay within allowed JSON types

4. Error Handling:
   - Provide clear error messages for invalid operations
   - Suggest corrections for ambiguous instructions
   - Handle edge cases gracefully

5. Performance Limits:
   - Respect maximum changes per request
   - Handle large documents efficiently
   - Implement timeout protection
```

## Running the Server

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Start Redis (if not running)
redis-server

# Run the MCP server
python run_server.py

# Or with specific configuration
python run_server.py --config config.yaml
```

### Production Mode

```bash
# Using gunicorn (install with: pip install gunicorn)
gunicorn --bind 0.0.0.0:8080 --workers 4 run_server:app

# Or using uvicorn (install with: pip install uvicorn)
uvicorn run_server:app --host 0.0.0.0 --port 8080 --workers 4
```

### Docker Mode

```bash
# Build the image
docker build -t json-editor-mcp .

# Run with Docker Compose
docker-compose up -d

# Or run manually
docker run -d \
  -p 8080:8080 \
  -e GEMINI_API_KEY=your_api_key \
  -e REDIS_HOST=redis \
  --name json-editor-mcp \
  json-editor-mcp
```

## Verification

### Health Checks

Test that the server is running correctly:

```bash
# Health check
curl http://localhost:8080/health

# Readiness check
curl http://localhost:8080/ready

# MCP tool listing
curl -X POST http://localhost:8080/mcp/tools \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/list"}'
```

### Basic Functionality Test

Test the preview functionality:

```bash
curl -X POST http://localhost:8080/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "json_editor_preview",
      "arguments": {
        "document": {"name": "John Doe", "age": 30},
        "instruction": "Change the age to 31"
      }
    }
  }'
```

Expected response should include a session ID and proposed changes.

## Troubleshooting

### Common Issues

#### 1. Redis Connection Failed
```
Error: Redis connection failed
```

**Solutions:**
- Ensure Redis server is running: `redis-cli ping`
- Check Redis configuration in config.yaml or environment variables
- Verify network connectivity to Redis host
- Check Redis authentication if password is set

#### 2. LLM API Authentication Failed
```
Error: LLM service authentication failed
```

**Solutions:**
- Verify API key is correct and active
- Check API key environment variable name
- Ensure API key has necessary permissions
- Test API key with provider's official tools

#### 3. Configuration File Not Found
```
Error: Configuration file not found
```

**Solutions:**
- Create config.yaml in the project root
- Use absolute path to configuration file
- Check file permissions
- Verify YAML syntax is correct

#### 4. Import Errors
```
ModuleNotFoundError: No module named 'mcp'
```

**Solutions:**
- Install all dependencies: `pip install -r requirements.txt`
- Activate virtual environment
- Check Python version compatibility
- Reinstall packages if needed

#### 5. Port Already in Use
```
Error: Port 8080 already in use
```

**Solutions:**
- Change port in configuration: `SERVER_PORT=8081`
- Kill process using the port: `lsof -ti:8080 | xargs kill`
- Use different port number

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in config.yaml
server:
  log_level: "DEBUG"
```

### Performance Tuning

#### For High Load

```yaml
# config.yaml
server:
  workers: 8  # Adjust based on CPU cores
  max_connections: 1000
  request_timeout: 300

redis:
  connection_pool_size: 20
  socket_timeout: 10

llm:
  timeout: 60
  retry_attempts: 5
```

#### For Large Documents

```yaml
# config.yaml
server:
  max_document_size: 104857600  # 100MB

guardrails:
  max_changes_per_request: 100
  document_size_limits:
    max_size: 104857600
    max_depth: 200
    max_keys: 50000
```

## Security Considerations

### API Key Security

- Store API keys in environment variables, not in code
- Use secure secret management in production
- Rotate API keys regularly
- Limit API key permissions to minimum required

### Network Security

- Use HTTPS in production
- Implement rate limiting
- Set up firewall rules
- Use VPN or private networks for Redis

### Input Validation

- Enable guardrails for production use
- Configure forbidden patterns appropriately
- Set reasonable document size limits
- Implement request size limits

## Monitoring and Maintenance

### Log Management

```bash
# View logs
tail -f /var/log/json-editor-mcp.log

# Rotate logs
logrotate /etc/logrotate.d/json-editor-mcp
```

### Performance Monitoring

- Monitor CPU and memory usage
- Track request response times
- Monitor LLM API usage and costs
- Set up alerts for error rates

### Backup and Recovery

- Backup Redis data regularly
- Store configuration files in version control
- Document deployment procedures
- Test disaster recovery procedures

## Integration Examples

### EditAgent Integration

```python
# Example EditAgent integration
import asyncio
from mcp_client import MCPClient

async def edit_json_with_mcp(document, instruction):
    client = MCPClient("http://localhost:8080")
    
    # Preview changes
    preview = await client.call_tool("json_editor_preview", {
        "document": document,
        "instruction": instruction
    })
    
    # Apply changes
    result = await client.call_tool("json_editor_apply", {
        "session_id": preview["session_id"]
    })
    
    return result["modified_document"]
```

### Custom Client Integration

```python
# Example custom client
import requests

def preview_json_changes(document, instruction):
    response = requests.post("http://localhost:8080/mcp/call_tool", json={
        "method": "tools/call",
        "params": {
            "name": "json_editor_preview",
            "arguments": {
                "document": document,
                "instruction": instruction
            }
        }
    })
    return response.json()
```

## Support and Resources

### Documentation
- [Architecture Overview](./architecture-overview.md)
- [API Documentation](./api-documentation.md)
- [Deployment Guide](./deployment-architecture.md)

### Community
- GitHub Issues: Report bugs and feature requests
- Discussions: Ask questions and share experiences
- Contributing: See CONTRIBUTING.md for guidelines

### Professional Support
- Enterprise support available
- Custom integration services
- Training and consulting