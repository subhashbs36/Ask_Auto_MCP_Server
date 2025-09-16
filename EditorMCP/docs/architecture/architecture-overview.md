# Architecture Overview

## System Overview

The JSON Editor MCP Tool is a Model Context Protocol server that provides natural language-based JSON document editing capabilities. The system implements a two-phase workflow: preview proposed changes, then apply confirmed changes.

## Key Design Principles

1. **Two-Phase Workflow**: Separate preview and apply operations for safe change confirmation
2. **Modular LLM Integration**: Pluggable LLM service architecture supporting multiple providers
3. **Session State Management**: Redis-based session storage for maintaining state between operations
4. **MCP Protocol Compliance**: Full compliance with Model Context Protocol standards
5. **Error Resilience**: Comprehensive error handling and graceful degradation

## Core Components

### 1. MCP Server Interface
- **Purpose**: Main entry point for MCP protocol communication
- **Responsibilities**: Tool registration, request routing, response formatting
- **Key Features**: Standardized MCP error handling, request validation

### 2. Tool Handlers
- **Preview Tool**: Generates change previews without modifying documents
- **Apply Tool**: Applies confirmed changes using session state
- **Features**: Comprehensive validation, structured responses

### 3. LLM Service Layer
- **Abstract Interface**: Common interface for all LLM providers
- **Adapters**: Gemini, OpenAI, and Custom endpoint implementations
- **Features**: Provider-specific error handling, retry logic, authentication

### 4. JSON Processing Engine
- **JSON-to-Map Conversion**: Converts JSON to editable map format
- **Change Application**: Applies modifications and reconstructs JSON
- **Features**: Path tracking, validation, error recovery

### 5. Session Management
- **Redis Storage**: Persistent session state between preview/apply
- **Session Validation**: Document state verification, concurrent session support
- **Features**: Unique session IDs, state integrity checks

### 6. Configuration System
- **Multi-Source Loading**: Environment variables, YAML files
- **Provider Configuration**: LLM-specific settings, authentication
- **Features**: Runtime validation, clear error messages

## Data Flow

```
Client Request → MCP Server → Tool Handler → JSON Processor → LLM Service
                     ↓              ↓              ↓              ↓
              Response Format ← Session Mgmt ← Change Logic ← AI Analysis
```

## Security Features

- Input validation and sanitization
- Secure session ID generation
- API key protection
- Document size limits
- Malicious pattern detection

## Scalability Considerations

- Stateless tool handlers
- Redis-based session clustering
- Provider-specific rate limiting
- Concurrent request handling
- Memory-efficient JSON processing

## Integration Points

### EditAgent Integration
The EditAgent interacts with this MCP tool through a simple pattern:
- Input: JSON document + natural language instruction
- Output: Modified JSON document

The EditAgent handles user interaction while the MCP tool handles the technical processing.

### MCP Client Integration
Any MCP-compatible client can use the tool through the standardized protocol:
- `json_editor_preview`: Preview changes
- `json_editor_apply`: Apply confirmed changes