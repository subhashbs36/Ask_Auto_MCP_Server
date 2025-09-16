"""Main entry point for the JSON Editor MCP server."""

import asyncio
import logging
import sys
from typing import Optional

import structlog

from .server import main as server_main


def setup_logging(log_level: str = "INFO") -> None:
    """Set up structured logging."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


async def main() -> None:
    """Main entry point for the MCP server."""
    setup_logging()
    logger = structlog.get_logger(__name__)
    
    logger.info("Starting JSON Editor MCP server...")
    
    try:
        # Get config path from command line arguments if provided
        config_path = sys.argv[1] if len(sys.argv) > 1 else None
        
        # Run the MCP server
        await server_main(config_path)
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server startup failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())