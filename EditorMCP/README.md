# JSON Editor REST API

A professional, modular REST API for editing JSON documents using natural language with LLM integration.

## Project Structure

```
EditorMCP/
├── main.py                     # Minimal entry point
├── src/                        # Source code
│   └── api/                    # REST API components
│       ├── __init__.py         # Package marker
│       ├── app.py              # FastAPI application factory
│       ├── models.py           # Pydantic models
│       ├── routes.py           # Route handlers
│       └── server.py           # Business logic server
├── json_editor_mcp/            # MCP server components
├── config.yaml                 # Configuration file
├── requirements.txt            # Dependencies
└── Dockerfile                  # Container configuration
```

## Features

- **LLM Integration**: Supports Gemini, OpenAI, and custom providers
- **Change Detection**: Sophisticated validation and preview
- **Session Management**: Automatic cleanup and tracking
- **Error Handling**: Comprehensive logging and monitoring
- **Guardrails**: Safety checks and validation
- **Performance**: Metrics and health monitoring

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export GEMINI_API_KEY="your-api-key"
   ```

3. Run the server:
   ```bash
   python main.py
   ```

4. Access the API:
   - **Docs**: http://localhost:8000/docs
   - **Health**: http://localhost:8000/health
   - **Info**: http://localhost:8000/info

## API Endpoints

- `POST /preview` - Preview proposed changes
- `POST /apply` - Apply changes from a session
- `GET /health` - Health check with component status
- `GET /info` - Server information and configuration
- `GET /sessions` - List active sessions
- `DELETE /sessions/{id}` - Delete a specific session

## Architecture

The application follows a clean, modular architecture:

- **Entry Point** (`main.py`): Minimal server startup
- **Application Factory** (`src/api/app.py`): FastAPI app configuration
- **Models** (`src/api/models.py`): Pydantic request/response models
- **Routes** (`src/api/routes.py`): HTTP route handlers
- **Server** (`src/api/server.py`): Core business logic

This structure ensures:
- ✅ **Separation of Concerns**: Each module has a single responsibility
- ✅ **Maintainability**: Easy to find and modify specific functionality
- ✅ **Testability**: Each component can be tested independently
- ✅ **Scalability**: Clean dependencies and modular design