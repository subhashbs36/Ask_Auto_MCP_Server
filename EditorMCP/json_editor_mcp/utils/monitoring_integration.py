"""Integration module for comprehensive monitoring and logging setup."""

import logging
import atexit
from typing import Optional, Dict, Any

from ..config.models import ServerConfig
from .logging_config import setup_logging, get_logger
from .monitoring_config import MonitoringManager, setup_monitoring, set_monitoring_manager
from .health_check import create_health_checker, HealthChecker
from .metrics import setup_default_alerts
from .llm_monitoring import get_llm_monitor


class MonitoringIntegration:
    """Central integration point for all monitoring, logging, and metrics."""
    
    def __init__(self, config: ServerConfig):
        """Initialize monitoring integration.
        
        Args:
            config: Server configuration
        """
        self.config = config
        self.logger: Optional[logging.Logger] = None
        self.monitoring_manager: Optional[MonitoringManager] = None
        self.health_checker: Optional[HealthChecker] = None
        self._initialized = False
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize all monitoring components.
        
        Returns:
            Dictionary containing initialization results
        """
        if self._initialized:
            return {"status": "already_initialized"}
        
        results = {
            "status": "success",
            "components": {},
            "errors": []
        }
        
        try:
            # 1. Setup logging first
            logging_result = self._setup_logging()
            results["components"]["logging"] = logging_result
            
            # Get logger after logging is configured
            self.logger = get_logger(__name__)
            self.logger.info("Starting monitoring integration initialization")
            
            # 2. Setup monitoring manager
            monitoring_result = self._setup_monitoring()
            results["components"]["monitoring"] = monitoring_result
            
            # 3. Setup health checker
            health_result = self._setup_health_checker()
            results["components"]["health_checker"] = health_result
            
            # 4. Setup default alerts
            alerts_result = self._setup_alerts()
            results["components"]["alerts"] = alerts_result
            
            # 5. Register cleanup handlers
            self._register_cleanup()
            
            self._initialized = True
            self.logger.info("Monitoring integration initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize monitoring integration: {str(e)}"
            results["status"] = "error"
            results["error"] = error_msg
            results["errors"].append(error_msg)
            
            if self.logger:
                self.logger.error(error_msg, exc_info=True)
            else:
                print(f"ERROR: {error_msg}")  # Fallback if logging not available
        
        return results
    
    def shutdown(self):
        """Shutdown all monitoring components gracefully."""
        if not self._initialized:
            return
        
        if self.logger:
            self.logger.info("Shutting down monitoring integration")
        
        try:
            # Stop monitoring manager
            if self.monitoring_manager:
                self.monitoring_manager.stop_monitoring()
                self.logger.info("Monitoring manager stopped")
            
            # Clear global references
            set_monitoring_manager(None)
            
            self._initialized = False
            
            if self.logger:
                self.logger.info("Monitoring integration shutdown complete")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during monitoring shutdown: {e}")
            else:
                print(f"ERROR during shutdown: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of all monitoring components.
        
        Returns:
            Dictionary containing status information
        """
        if not self._initialized:
            return {
                "initialized": False,
                "status": "not_initialized"
            }
        
        status = {
            "initialized": True,
            "status": "running",
            "components": {}
        }
        
        try:
            # Monitoring manager status
            if self.monitoring_manager:
                status["components"]["monitoring_manager"] = {
                    "active": self.monitoring_manager._monitoring_active,
                    "health": self.monitoring_manager.get_health_status()
                }
            
            # Health checker status
            if self.health_checker:
                status["components"]["health_checker"] = {
                    "available": True,
                    "readiness": self.health_checker.check_readiness(),
                    "liveness": self.health_checker.check_liveness()
                }
            
            # LLM monitor status
            llm_monitor = get_llm_monitor()
            if llm_monitor:
                llm_stats = llm_monitor.get_all_provider_stats()
                status["components"]["llm_monitor"] = {
                    "providers_count": len(llm_stats),
                    "total_requests": sum(stats.total_requests for stats in llm_stats.values())
                }
            
        except Exception as e:
            status["error"] = str(e)
            if self.logger:
                self.logger.error(f"Error getting monitoring status: {e}")
        
        return status
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get comprehensive monitoring and metrics report.
        
        Returns:
            Dictionary containing comprehensive report
        """
        if not self._initialized or not self.monitoring_manager:
            return {
                "error": "Monitoring not initialized",
                "initialized": self._initialized
            }
        
        try:
            # Get main metrics report
            report = self.monitoring_manager.get_metrics_report(include_history=True)
            
            # Add health check results
            if self.health_checker:
                report["health_check"] = self.health_checker.check_all_components()
            
            # Add system status
            report["system_status"] = self.get_status()
            
            return report
            
        except Exception as e:
            error_msg = f"Error generating comprehensive report: {e}"
            if self.logger:
                self.logger.error(error_msg)
            
            return {
                "error": error_msg,
                "timestamp": "unknown"
            }
    
    def _setup_logging(self) -> Dict[str, Any]:
        """Setup logging configuration."""
        try:
            log_config = setup_logging(
                log_level=self.config.log_level,
                log_file=None,  # Could be configured from config in the future
                enable_json_logging=False,  # Could be configured from config
                enable_error_tracking=True,
                enable_debug_logging=True
            )
            
            return {
                "status": "success",
                "log_level": self.config.log_level,
                "handlers_count": log_config.get("handlers_count", 0),
                "error_tracking": log_config.get("error_tracker") is not None,
                "debug_logging": log_config.get("debug_logger") is not None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _setup_monitoring(self) -> Dict[str, Any]:
        """Setup monitoring manager."""
        try:
            self.monitoring_manager = setup_monitoring(self.config)
            set_monitoring_manager(self.monitoring_manager)
            
            return {
                "status": "success",
                "monitoring_enabled": self.config.monitoring_config.enabled if self.config.monitoring_config else False,
                "active": self.monitoring_manager._monitoring_active
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _setup_health_checker(self) -> Dict[str, Any]:
        """Setup health checker."""
        try:
            self.health_checker = create_health_checker(self.config)
            
            return {
                "status": "success",
                "available": True
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _setup_alerts(self) -> Dict[str, Any]:
        """Setup default alert thresholds."""
        try:
            setup_default_alerts()
            
            return {
                "status": "success",
                "default_alerts_configured": True
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _register_cleanup(self):
        """Register cleanup handlers for graceful shutdown."""
        atexit.register(self.shutdown)


# Global monitoring integration instance
_global_monitoring_integration: Optional[MonitoringIntegration] = None


def initialize_monitoring(config: ServerConfig) -> Dict[str, Any]:
    """Initialize comprehensive monitoring for the JSON Editor MCP Tool.
    
    Args:
        config: Server configuration
        
    Returns:
        Dictionary containing initialization results
    """
    global _global_monitoring_integration
    
    if _global_monitoring_integration is not None:
        return {"status": "already_initialized"}
    
    _global_monitoring_integration = MonitoringIntegration(config)
    return _global_monitoring_integration.initialize()


def get_monitoring_integration() -> Optional[MonitoringIntegration]:
    """Get the global monitoring integration instance.
    
    Returns:
        MonitoringIntegration instance or None if not initialized
    """
    return _global_monitoring_integration


def shutdown_monitoring():
    """Shutdown monitoring integration."""
    global _global_monitoring_integration
    
    if _global_monitoring_integration:
        _global_monitoring_integration.shutdown()
        _global_monitoring_integration = None


def get_monitoring_status() -> Dict[str, Any]:
    """Get current monitoring status.
    
    Returns:
        Dictionary containing monitoring status
    """
    if _global_monitoring_integration:
        return _global_monitoring_integration.get_status()
    else:
        return {
            "initialized": False,
            "status": "not_initialized"
        }


def get_monitoring_report() -> Dict[str, Any]:
    """Get comprehensive monitoring report.
    
    Returns:
        Dictionary containing comprehensive monitoring report
    """
    if _global_monitoring_integration:
        return _global_monitoring_integration.get_comprehensive_report()
    else:
        return {
            "error": "Monitoring not initialized",
            "initialized": False
        }