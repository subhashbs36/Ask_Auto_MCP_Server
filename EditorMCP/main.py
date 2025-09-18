"""
JSON Editor REST API Server
Minimal entry point for the modular JSON Editor REST API.
"""

import logging
import asyncio
import uvicorn
from src.api.app import create_app


async def main():
    """Main entry point for the JSON Editor REST API server."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting JSON Editor REST API server...")
    
    # Create the FastAPI app
    app = create_app()
    
    # Configure uvicorn server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )
    
    # Create and run async server
    server = uvicorn.Server(config)
    
    try:
        logger.info("Server starting on http://0.0.0.0:8000")
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())