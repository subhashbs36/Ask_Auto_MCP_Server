"""
FastAPI application factory and configuration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import (
    HealthResponse, ServerInfoResponse, PreviewResponse, ApplyResponse
)
from src.api import routes


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="JSON Editor REST API",
        description="Advanced REST API for editing JSON documents using natural language with LLM integration",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add startup event
    app.add_event_handler("startup", routes.startup_event)

    # Add routes
    app.add_api_route("/health", routes.health_check, methods=["GET"], response_model=HealthResponse)
    app.add_api_route("/info", routes.server_info, methods=["GET"], response_model=ServerInfoResponse)
    app.add_api_route("/preview", routes.preview_changes, methods=["POST"], response_model=PreviewResponse)
    app.add_api_route("/apply", routes.apply_changes, methods=["POST"], response_model=ApplyResponse)
    app.add_api_route("/sessions", routes.list_sessions, methods=["GET"])
    app.add_api_route("/sessions/{session_id}", routes.delete_session, methods=["DELETE"])
    app.add_api_route("/", routes.root, methods=["GET"])

    return app