#!/usr/bin/env python3
"""
JSON Editor MCP Server - Main Entry Point

This script starts the MCP server that provides JSON editing capabilities
through natural language instructions via the Model Context Protocol.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from json_editor_mcp.config.loader import ConfigLoader
from json_editor_mcp.server import MCPServer


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("json_editor_mcp.log")
        ]
    )


async def main(config_path: Optional[str] = None) -> None:
    """Main entry point for the MCP server."""
    try:
        # Load configuration
        config_loader = ConfigLoader()
        if config_path:
            config = config_loader.load_from_file(config_path)
        else:
            # Try to load from config.yaml first, then fall back to environment
            try:
                config = config_loader.load_from_file("config.yaml")
            except FileNotFoundError:
                config = config_loader.load_from_env()
        
        # Setup logging
        setup_logging(config.log_level)
        logger = logging.getLogger(__name__)
        
        logger.info("Starting JSON Editor MCP Server")
        logger.info(f"LLM Provider: {config.llm_config.provider}")
        logger.info(f"Redis Host: {config.redis_config.host}:{config.redis_config.port}")
        
        # Create and start MCP server
        server = MCPServer(config)
        await server.run_stdio()
        
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="JSON Editor MCP Server")
    parser.add_argument(
        "--config", 
        type=str, 
        help="Path to configuration file (YAML)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Override log level if provided
    if args.log_level:
        import os
        os.environ["LOG_LEVEL"] = args.log_level
    
    asyncio.run(main(args.config))