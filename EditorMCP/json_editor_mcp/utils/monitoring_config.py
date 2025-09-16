"""Monitoring and metrics configuration for JSON Editor MCP Tool."""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from .logging_config import setup_logging, get_logger, ErrorTrackingHandler
from .metrics import MetricsCollector, PerformanceMonitor, setup_default_alerts
from .llm_monitoring import LLMPerformanceMonitor, get_llm_monitor
from ..config.models import ServerConfig


class MonitoringManager:
    """Central manager for all monitoring and metrics collection."""
    
    def __init__(self, config: ServerConfig):
        """Initialize monitoring manager with configuration.
        
        Args:
            config: Server configuration containing monitoring settings
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.metrics_collector = MetricsCollector()
        self.performance_monitor = PerformanceMonitor(self.metrics_collector)
        self.llm_monitor = LLMPerformanceMonitor(self.metrics_collector)
        self.error_tracker: Optional[ErrorTrackingHandler] = None
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Alert callbacks
        self._alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Setup monitoring
        self._setup_logging()
        self._setup_metrics()
        self._setup_alerts()
    
    def start_monitoring(self):
        """Start background monitoring processes."""
        if self._monitoring_active:
            self.logger.warning("Monitoring is already active")
            return
        
        self._monitoring_active = True
        self._shutdown_event.clear()
        
        # Start monitoring thread
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="MonitoringThread",
            daemon=True
        )
        self._monitoring_thread.start()
        
        self.logger.info("Started monitoring and metrics collection")
    
    def stop_monitoring(self):
        """Stop background monitoring processes."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        self._shutdown_event.set()
        
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5.0)
        
        self.logger.info("Stopped monitoring and metrics collection")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the system.
        
        Returns:
            Dictionary containing health status information
        """
        health = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "components": {},
            "metrics_summary": {},
            "alerts": []
        }
        
        try:
            # Check metrics collector
            metrics_summary = self.metrics_collector.get_all_metrics()
            health["components"]["metrics_collector"] = {
                "status": "healthy",
                "metrics_count": len(metrics_summary)
            }
            health["metrics_summary"] = {
                name: {
                    "current_value": summary.current_value,
                    "total_count": summary.total_count,
                    "last_updated": summary.last_updated.isoformat() if summary.last_updated else None
                }
                for name, summary in metrics_summary.items()
            }
            
            # Check LLM monitor
            llm_stats = self.llm_monitor.get_all_provider_stats()
            health["components"]["llm_monitor"] = {
                "status": "healthy",
                "providers_count": len(llm_stats),
                "total_requests": sum(stats.total_requests for stats in llm_stats.values())
            }
            
            # Check error tracker
            if self.error_tracker:
                error_summary = self.error_tracker.get_error_summary()
                health["components"]["error_tracker"] = {
                    "status": "healthy",
                    "total_errors": sum(error_summary["total_errors_by_logger"].values()),
                    "recent_errors": len(error_summary["recent_error_count"])
                }
                
                # Add alerts for high error rates
                total_errors = sum(error_summary["total_errors_by_logger"].values())
                if total_errors > 50:
                    health["alerts"].append(f"High error count: {total_errors} total errors")
                    health["status"] = "degraded"
            
            # Check monitoring thread
            health["components"]["monitoring_thread"] = {
                "status": "healthy" if self._monitoring_active else "stopped",
                "active": self._monitoring_active
            }
            
            # Performance checks
            performance_report = self.performance_monitor.get_performance_report()
            if performance_report.get("alerts"):
                health["alerts"].extend(performance_report["alerts"])
                health["status"] = "degraded"
            
            # LLM performance checks
            llm_report = self.llm_monitor.get_performance_report()
            if llm_report.get("alerts"):
                health["alerts"].extend(llm_report["alerts"])
                health["status"] = "degraded"
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
            self.logger.error(f"Error getting health status: {e}")
        
        return health
    
    def get_metrics_report(self, include_history: bool = False) -> Dict[str, Any]:
        """Get comprehensive metrics report.
        
        Args:
            include_history: Whether to include historical data
            
        Returns:
            Dictionary containing metrics report
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "general_metrics": {},
            "llm_performance": {},
            "error_tracking": {},
            "system_health": {}
        }
        
        try:
            # General metrics
            all_metrics = self.metrics_collector.get_all_metrics()
            report["general_metrics"] = {
                name: {
                    "type": summary.metric_type.value,
                    "current_value": summary.current_value,
                    "total_count": summary.total_count,
                    "min_value": summary.min_value,
                    "max_value": summary.max_value,
                    "avg_value": summary.avg_value,
                    "p95_value": summary.p95_value,
                    "p99_value": summary.p99_value,
                    "last_updated": summary.last_updated.isoformat() if summary.last_updated else None
                }
                for name, summary in all_metrics.items()
            }
            
            # LLM performance
            report["llm_performance"] = self.llm_monitor.get_performance_report()
            
            # Error tracking
            if self.error_tracker:
                report["error_tracking"] = self.error_tracker.get_error_summary()
            
            # System health
            report["system_health"] = self.get_health_status()
            
            # Performance analysis
            report["performance_analysis"] = self.performance_monitor.get_performance_report()
            
        except Exception as e:
            report["error"] = str(e)
            self.logger.error(f"Error generating metrics report: {e}")
        
        return report
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add callback function for alerts.
        
        Args:
            callback: Function to call when alerts are triggered
                     Signature: callback(alert_type, alert_data)
        """
        self._alert_callbacks.append(callback)
    
    def record_request_start(self, operation: str, request_id: str, **labels):
        """Record the start of a request operation.
        
        Args:
            operation: Operation name (e.g., 'preview', 'apply')
            request_id: Unique request identifier
            **labels: Additional labels for the metric
        """
        labels.update({"operation": operation, "request_id": request_id})
        self.metrics_collector.increment_counter("requests_started_total", 1.0, labels)
        
        # Store start time for duration calculation
        if not hasattr(self, '_request_start_times'):
            self._request_start_times = {}
        self._request_start_times[request_id] = time.time()
    
    def record_request_complete(self, operation: str, request_id: str, 
                              status: str, error_type: Optional[str] = None, **labels):
        """Record the completion of a request operation.
        
        Args:
            operation: Operation name
            request_id: Unique request identifier
            status: Request status ('success', 'error', etc.)
            error_type: Type of error if status is 'error'
            **labels: Additional labels for the metric
        """
        labels.update({"operation": operation, "status": status})
        if error_type:
            labels["error_type"] = error_type
        
        self.metrics_collector.increment_counter("requests_completed_total", 1.0, labels)
        
        # Record duration if we have start time
        if hasattr(self, '_request_start_times') and request_id in self._request_start_times:
            duration = time.time() - self._request_start_times[request_id]
            self.metrics_collector.record_timer(f"{operation}_request_duration_seconds", duration, labels)
            del self._request_start_times[request_id]
        
        # Record errors
        if status == "error":
            error_labels = {"operation": operation}
            if error_type:
                error_labels["error_type"] = error_type
            self.metrics_collector.increment_counter("request_errors_total", 1.0, error_labels)
    
    def record_llm_request(self, provider: str, model: str, request_id: str, 
                          prompt_tokens: Optional[int] = None):
        """Record an LLM request for monitoring.
        
        Args:
            provider: LLM provider name
            model: Model name
            request_id: Unique request identifier
            prompt_tokens: Number of prompt tokens
            
        Returns:
            LLMRequestTracker context manager
        """
        return self.llm_monitor.start_request(provider, model, request_id, prompt_tokens)
    
    def record_document_processing(self, operation: str, document_size: int, 
                                 processing_time: float, changes_count: Optional[int] = None):
        """Record document processing metrics.
        
        Args:
            operation: Processing operation name
            document_size: Size of document in bytes
            processing_time: Processing time in seconds
            changes_count: Number of changes processed
        """
        labels = {"operation": operation}
        
        self.metrics_collector.record_histogram("document_size_bytes", document_size, labels)
        self.metrics_collector.record_timer(f"{operation}_processing_duration_seconds", processing_time, labels)
        
        if changes_count is not None:
            self.metrics_collector.record_histogram("changes_count", changes_count, labels)
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_config = setup_logging(
            log_level=self.config.log_level,
            log_file=None,  # Could be configured from config
            enable_json_logging=False,  # Could be configured from config
            enable_error_tracking=True,
            enable_debug_logging=True
        )
        
        self.error_tracker = log_config.get("error_tracker")
        self.logger.info(f"Configured logging with level {self.config.log_level}")
    
    def _setup_metrics(self):
        """Setup metrics collection."""
        # Set up default performance thresholds
        if self.config.monitoring_config and self.config.monitoring_config.enabled:
            setup_default_alerts()
            self.logger.info("Configured default performance alerts")
    
    def _setup_alerts(self):
        """Setup alert thresholds and callbacks."""
        # Add default alert callback for logging
        def log_alert(alert_type: str, alert_data: Dict[str, Any]):
            self.logger.warning(f"Alert triggered: {alert_type}", extra=alert_data)
        
        self.add_alert_callback(log_alert)
        
        # Configure specific thresholds based on config
        if self.config.monitoring_config and self.config.monitoring_config.enabled:
            # Request processing time thresholds
            self.performance_monitor.set_alert_threshold(
                "preview_request_duration_seconds", "avg_max", 10.0
            )
            self.performance_monitor.set_alert_threshold(
                "apply_request_duration_seconds", "avg_max", 5.0
            )
            
            # Error rate thresholds
            self.performance_monitor.set_alert_threshold(
                "request_errors_total", "current_max", 25.0
            )
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        self.logger.debug("Started monitoring loop")
        
        while not self._shutdown_event.is_set():
            try:
                # Check alerts every 30 seconds
                self.performance_monitor.check_alerts()
                
                # Generate periodic reports every 5 minutes
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    self._generate_periodic_report()
                
                # Sleep for 30 seconds
                if self._shutdown_event.wait(30):
                    break
                    
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                # Continue monitoring even if there's an error
                if self._shutdown_event.wait(30):
                    break
        
        self.logger.debug("Monitoring loop stopped")
    
    def _generate_periodic_report(self):
        """Generate and log periodic monitoring report."""
        try:
            report = self.get_metrics_report()
            
            # Log summary statistics
            general_metrics = report.get("general_metrics", {})
            llm_performance = report.get("llm_performance", {})
            
            summary = {
                "metrics_count": len(general_metrics),
                "llm_providers": len(llm_performance.get("providers", {})),
                "total_requests": llm_performance.get("summary", {}).get("total_requests", 0),
                "overall_success_rate": llm_performance.get("summary", {}).get("overall_success_rate", 0.0)
            }
            
            self.logger.info("Periodic monitoring report", extra=summary)
            
            # Trigger alerts if needed
            alerts = []
            
            # Check for performance issues
            if summary["overall_success_rate"] < 0.95 and summary["total_requests"] > 10:
                alerts.append({
                    "type": "low_success_rate",
                    "message": f"Overall success rate is {summary['overall_success_rate']:.2%}",
                    "data": summary
                })
            
            # Trigger alert callbacks
            for alert in alerts:
                for callback in self._alert_callbacks:
                    try:
                        callback(alert["type"], alert)
                    except Exception as e:
                        self.logger.error(f"Error in alert callback: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error generating periodic report: {e}")


def setup_monitoring(config: ServerConfig) -> MonitoringManager:
    """Setup comprehensive monitoring for the JSON Editor MCP Tool.
    
    Args:
        config: Server configuration
        
    Returns:
        Configured MonitoringManager instance
    """
    manager = MonitoringManager(config)
    
    # Start monitoring if enabled
    if config.monitoring_config and config.monitoring_config.enabled:
        manager.start_monitoring()
    
    return manager


# Global monitoring manager instance
_global_monitoring_manager: Optional[MonitoringManager] = None


def get_monitoring_manager() -> Optional[MonitoringManager]:
    """Get the global monitoring manager instance."""
    return _global_monitoring_manager


def set_monitoring_manager(manager: MonitoringManager):
    """Set the global monitoring manager instance."""
    global _global_monitoring_manager
    _global_monitoring_manager = manager