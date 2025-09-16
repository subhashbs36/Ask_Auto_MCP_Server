# JSON Editor MCP Tool Documentation

This directory contains comprehensive documentation for the JSON Editor MCP Tool, a Model Context Protocol server that provides natural language-based JSON document editing capabilities.

## Overview

The JSON Editor MCP Tool enables EditAgent and other MCP-compatible systems to modify complex JSON structures using human-readable instructions through a standardized two-phase workflow:

1. **Preview Phase**: Analyze the JSON document and natural language instruction to generate proposed changes
2. **Apply Phase**: Apply confirmed changes to produce the modified JSON document

## Key Features

- **Natural Language Processing**: Edit JSON documents using plain English instructions
- **Two-Phase Safety**: Preview changes before applying them for user confirmation
- **Multi-Provider LLM Support**: Compatible with Gemini, OpenAI, and custom LLM endpoints
- **Session Management**: Secure state management between preview and apply operations
- **MCP Protocol Compliance**: Full compatibility with Model Context Protocol standards
- **Comprehensive Error Handling**: Robust error handling with detailed feedback
- **Scalable Architecture**: Modular design supporting horizontal scaling

## Documentation Structure

### Architecture Documentation
- [`architecture/README.md`](architecture/README.md) - Documentation index and navigation
- [`architecture/architecture-overview.md`](architecture/architecture-overview.md) - High-level system architecture
- [`architecture/component-diagrams.drawio`](architecture/component-diagrams.drawio) - Visual architecture diagrams
- [`architecture/sequence-diagrams.drawio`](architecture/sequence-diagrams.drawio) - Interaction flow diagrams
- [`architecture/sequence-diagrams.md`](architecture/sequence-diagrams.md) - Detailed sequence documentation
- [`architecture/system-architecture.drawio`](architecture/system-architecture.drawio) - Complete system diagrams

### API and Integration
- [`architecture/api-documentation.md`](architecture/api-documentation.md) - Complete MCP tool schemas and API reference
- Integration examples for EditAgent and custom clients
- Error response formats and handling guidelines

### Setup and Configuration
- [`architecture/setup-configuration-guide.md`](architecture/setup-configuration-guide.md) - Complete setup and configuration guide
- [`architecture/deployment-architecture.md`](architecture/deployment-architecture.md) - Deployment options and infrastructure

## Quick Start

### For Users
1. **Setup**: Follow the [Setup Guide](architecture/setup-configuration-guide.md) to install and configure the tool
2. **Configuration**: Configure your preferred LLM provider (Gemini, OpenAI, or custom)
3. **Integration**: Integrate with EditAgent or your MCP-compatible client

### For Developers
1. **Architecture**: Review the [Architecture Overview](architecture/architecture-overview.md) to understand the system design
2. **API Reference**: Check the [API Documentation](architecture/api-documentation.md) for integration details
3. **Deployment**: Use the [Deployment Guide](architecture/deployment-architecture.md) for production setup

## Core Concepts

### JSON-to-Map Conversion
The tool converts JSON documents into an editable map format that preserves structure while enabling targeted text modifications:

```json
// Original JSON
{"user": {"name": "John", "age": 30}}

// Map Format
[
  {"id": "1", "path": ["user", "name"], "value": "John"},
  {"id": "2", "path": ["user", "age"], "value": "30"}
]
```

### Two-Phase Workflow
1. **Preview**: `json_editor_preview(document, instruction)` → Returns proposed changes + session ID
2. **Apply**: `json_editor_apply(session_id)` → Returns modified document

### LLM Provider Abstraction
Pluggable architecture supports multiple LLM providers through a common interface:
- **Gemini Adapter**: Google Gemini API integration
- **OpenAI Adapter**: OpenAI API integration  
- **Custom Adapter**: Support for custom LLM endpoints

## Use Cases

### EditAgent Integration
- **Input**: JSON document + natural language instruction
- **Process**: Two-phase preview/apply workflow with user confirmation
- **Output**: Modified JSON document

### Automated JSON Processing
- Bulk JSON document modifications
- Configuration file updates
- Data transformation workflows
- API response modifications

### Development and Testing
- JSON fixture generation and modification
- Configuration management
- Test data preparation
- API mocking and simulation

## Architecture Highlights

### Modular Design
- **MCP Server**: Protocol handling and tool registration
- **Tool Layer**: Preview and Apply tool implementations
- **Service Layer**: JSON processing, LLM integration, session management
- **Adapter Layer**: Provider-specific LLM implementations

### Scalability Features
- Stateless tool handlers for horizontal scaling
- Redis-based session clustering
- Provider-specific rate limiting and retry logic
- Concurrent request handling without data corruption

### Security and Reliability
- Input validation and sanitization
- Secure session ID generation
- Comprehensive error handling with retry logic
- Guardrails for safe JSON modifications

## Getting Help

### Documentation Navigation
- **New Users**: Start with [Setup Guide](architecture/setup-configuration-guide.md)
- **Integrators**: Review [API Documentation](architecture/api-documentation.md)
- **Operators**: Check [Deployment Guide](architecture/deployment-architecture.md)
- **Developers**: Study [Architecture Overview](architecture/architecture-overview.md)

### Troubleshooting
- Common issues and solutions in the [Setup Guide](architecture/setup-configuration-guide.md#troubleshooting)
- Error codes and handling in the [API Documentation](architecture/api-documentation.md#error-responses)
- Performance tuning in the [Deployment Guide](architecture/deployment-architecture.md#scaling-considerations)

### Visual References
- **System Architecture**: [System Diagrams](architecture/system-architecture.drawio)
- **Component Relationships**: [Component Diagrams](architecture/component-diagrams.drawio)
- **Interaction Flows**: [Sequence Diagrams](architecture/sequence-diagrams.drawio)

## Contributing

This documentation is part of the JSON Editor MCP Tool project. For contributions:
1. Follow the existing documentation structure and style
2. Update diagrams using draw.io format for consistency
3. Include practical examples and use cases
4. Maintain cross-references between related documents

## Version Information

This documentation corresponds to the JSON Editor MCP Tool implementation as specified in the project requirements and design documents. For the latest updates and version information, refer to the project repository.