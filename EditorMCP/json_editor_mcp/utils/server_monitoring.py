"""Server-level monitoring integration for MCP server."""

import logging
from typing import Dict, Any, Optional

from ..config.models import ServerConfig
from .monitoring_integration import initialize_monitoring, get_monitoring_integration, shutdown_monitoring


class ServerMonitoringMixin:
    """Mixin class to add monitoring capabilities to MCP server."""
    
    def __init__(self, config: ServerConfig, *args, **kwargs):
        """Initialize server with monitoring.
        
        Args:
            config: Server configuration
        """
        super().__init__(*args, **kwargs)
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._monitoring_initialized = False
    
    def initialize_server_monitoring(self) -> Dict[str, Any]:
        """Initialize monitoring for the server.
        
        Returns:
            Dictionary containing initialization results
        """
        if self._monitoring_initialized:
            return {"status": "already_initialized"}
        
        try:
            # Initialize comprehensive monitoring
            result = initialize_monitoring(self.config)
            
            if result["status"] == "success":
                self._monitoring_initialized = True
                self.logger.info("Server monitoring initialized successfully")
            else:
                self.logger.error(f"Failed to initialize server monitoring: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error initializing server monitoring: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "error": error_msg
            }
    
    def get_server_health(self) -> Dict[str, Any]:
        """Get server health status including monitoring components.
        
        Returns:
            Dictionary containing server health information
        """
        health = {
            "server_status": "running",
            "monitoring_initialized": self._monitoring_initialized,
            "timestamp": None
        }
        
        if self._monitoring_initialized:
            monitoring_integration = get_monitoring_integration()
            if monitoring_integration:
                try:
                    # Get comprehensive health check
                    if monitoring_integration.health_checker:
                        health_check = monitoring_integration.health_checker.check_all_components()
                        health.update(health_check)
                    
                    # Get monitoring status
                    monitoring_status = monitoring_integration.get_status()
                    health["monitoring_status"] = monitoring_status
                    
                except Exception as e:
                    health["monitoring_error"] = str(e)
                    self.logger.error(f"Error getting server health: {e}")
        
        return health
    
    def get_server_metrics(self) -> Dict[str, Any]:
        """Get server metrics and performance data.
        
        Returns:
            Dictionary containing server metrics
        """
        if not self._monitoring_initialized:
            return {
                "error": "Monitoring not initialized",
                "monitoring_initialized": False
            }
        
        monitoring_integration = get_monitoring_integration()
        if not monitoring_integration:
            return {
                "error": "Monitoring integration not available",
                "monitoring_initialized": self._monitoring_initialized
            }
        
        try:
            return monitoring_integration.get_comprehensive_report()
        except Exception as e:
            error_msg = f"Error getting server metrics: {e}"
            self.logger.error(error_msg)
            return {
                "error": error_msg,
                "monitoring_initialized": self._monitoring_initialized
            }
    
    def shutdown_server_monitoring(self):
        """Shutdown server monitoring gracefully."""
        if self._monitoring_initialized:
            try:
                shutdown_monitoring()
                self._monitoring_initialized = False
                self.logger.info("Server monitoring shutdown complete")
            except Exception as e:
                self.logger.error(f"Error shutting down server monitoring: {e}")


def add_monitoring_endpoints(server_instance, config: ServerConfig):
    """Add monitoring endpoints to an MCP server instance.
    
    Args:
        server_instance: MCP server instance to add endpoints to
        config: Server configuration
    """
    if not config.monitoring_config or not config.monitoring_config.enabled:
        return
    
    logger = logging.getLogger(__name__)
    
    # Add health check endpoint
    def health_endpoint():
        """Health check endpoint."""
        try:
            if hasattr(server_instance, 'get_server_health'):
                return server_instance.get_server_health()
            else:
                monitoring_integration = get_monitoring_integration()
                if monitoring_integration and monitoring_integration.health_checker:
                    return monitoring_integration.health_checker.check_all_components()
                else:
                    return {
                        "status": "healthy",
                        "message": "Basic health check - monitoring not available"
                    }
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    # Add metrics endpoint
    def metrics_endpoint():
        """Metrics endpoint."""
        try:
            if hasattr(server_instance, 'get_server_metrics'):
                return server_instance.get_server_metrics()
            else:
                monitoring_integration = get_monitoring_integration()
                if monitoring_integration:
                    return monitoring_integration.get_comprehensive_report()
                else:
                    return {
                        "error": "Monitoring not available"
                    }
        except Exception as e:
            logger.error(f"Metrics endpoint error: {e}")
            return {
                "error": str(e)
            }
    
    # Add readiness endpoint
    def readiness_endpoint():
        """Readiness check endpoint."""
        try:
            monitoring_integration = get_monitoring_integration()
            if monitoring_integration and monitoring_integration.health_checker:
                return monitoring_integration.health_checker.check_readiness()
            else:
                return {
                    "ready": True,
                    "message": "Basic readiness check - monitoring not available"
                }
        except Exception as e:
            logger.error(f"Readiness check error: {e}")
            return {
                "ready": False,
                "error": str(e)
            }
    
    # Add liveness endpoint
    def liveness_endpoint():
        """Liveness check endpoint."""
        try:
            monitoring_integration = get_monitoring_integration()
            if monitoring_integration and monitoring_integration.health_checker:
                return monitoring_integration.health_checker.check_liveness()
            else:
                return {
                    "alive": True,
                    "message": "Basic liveness check - monitoring not available"
                }
        except Exception as e:
            logger.error(f"Liveness check error: {e}")
            return {
                "alive": False,
                "error": str(e)
            }
    
    # Store endpoint functions on server instance for potential use
    server_instance._health_endpoint = health_endpoint
    server_instance._metrics_endpoint = metrics_endpoint
    server_instance._readiness_endpoint = readiness_endpoint
    server_instance._liveness_endpoint = liveness_endpoint
    
    logger.info("Added monitoring endpoints to server instance")