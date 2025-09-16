"""Health check and monitoring endpoints for JSON Editor MCP Tool."""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .monitoring_config import get_monitoring_manager
from .metrics import get_metrics_collector, get_performance_monitor
from .llm_monitoring import get_llm_monitor
from ..config.models import ServerConfig


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    component: str
    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    details: Optional[Dict[str, Any]] = None
    response_time_ms: Optional[float] = None


class HealthChecker:
    """Comprehensive health checker for all system components."""
    
    def __init__(self, config: ServerConfig):
        """Initialize health checker.
        
        Args:
            config: Server configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def check_all_components(self) -> Dict[str, Any]:
        """Perform comprehensive health check of all components.
        
        Returns:
            Dictionary containing health check results
        """
        start_time = time.time()
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {},
            "summary": {
                "total_components": 0,
                "healthy_components": 0,
                "degraded_components": 0,
                "unhealthy_components": 0
            },
            "response_time_ms": 0.0
        }
        
        # List of health checks to perform
        health_checks = [
            self._check_metrics_collector,
            self._check_performance_monitor,
            self._check_llm_monitor,
            self._check_monitoring_manager,
            self._check_logging_system,
            self._check_configuration,
            self._check_system_resources
        ]
        
        # Perform all health checks
        for check_func in health_checks:
            try:
                result = check_func()
                health_report["components"][result.component] = {
                    "status": result.status,
                    "message": result.message,
                    "details": result.details or {},
                    "response_time_ms": result.response_time_ms
                }
                
                # Update summary counts
                health_report["summary"]["total_components"] += 1
                if result.status == "healthy":
                    health_report["summary"]["healthy_components"] += 1
                elif result.status == "degraded":
                    health_report["summary"]["degraded_components"] += 1
                else:
                    health_report["summary"]["unhealthy_components"] += 1
                
                # Update overall status
                if result.status == "unhealthy":
                    health_report["overall_status"] = "unhealthy"
                elif result.status == "degraded" and health_report["overall_status"] != "unhealthy":
                    health_report["overall_status"] = "degraded"
                    
            except Exception as e:
                self.logger.error(f"Error in health check {check_func.__name__}: {e}")
                health_report["components"][check_func.__name__] = {
                    "status": "unhealthy",
                    "message": f"Health check failed: {str(e)}",
                    "details": {"error": str(e)},
                    "response_time_ms": None
                }
                health_report["summary"]["total_components"] += 1
                health_report["summary"]["unhealthy_components"] += 1
                health_report["overall_status"] = "unhealthy"
        
        # Calculate total response time
        health_report["response_time_ms"] = (time.time() - start_time) * 1000
        
        return health_report
    
    def check_readiness(self) -> Dict[str, Any]:
        """Check if the system is ready to serve requests.
        
        Returns:
            Dictionary containing readiness status
        """
        readiness = {
            "timestamp": datetime.now().isoformat(),
            "ready": True,
            "checks": {}
        }
        
        # Critical components that must be healthy for readiness
        critical_checks = [
            ("configuration", self._check_configuration),
            ("logging", self._check_logging_system),
            ("metrics", self._check_metrics_collector)
        ]
        
        for check_name, check_func in critical_checks:
            try:
                result = check_func()
                readiness["checks"][check_name] = {
                    "status": result.status,
                    "message": result.message
                }
                
                if result.status == "unhealthy":
                    readiness["ready"] = False
                    
            except Exception as e:
                readiness["checks"][check_name] = {
                    "status": "unhealthy",
                    "message": f"Check failed: {str(e)}"
                }
                readiness["ready"] = False
        
        return readiness
    
    def check_liveness(self) -> Dict[str, Any]:
        """Check if the system is alive and responsive.
        
        Returns:
            Dictionary containing liveness status
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "alive": True,
            "uptime_seconds": time.time() - getattr(self, '_start_time', time.time()),
            "message": "System is alive and responsive"
        }
    
    def _check_metrics_collector(self) -> HealthCheckResult:
        """Check metrics collector health."""
        start_time = time.time()
        
        try:
            metrics_collector = get_metrics_collector()
            
            # Test basic functionality
            test_metric = "health_check_test"
            metrics_collector.increment_counter(test_metric, 1.0)
            summary = metrics_collector.get_metric_summary(test_metric)
            
            if summary and summary.current_value == 1.0:
                status = "healthy"
                message = "Metrics collector is functioning normally"
                details = {
                    "total_metrics": len(metrics_collector.get_all_metrics()),
                    "test_passed": True
                }
            else:
                status = "degraded"
                message = "Metrics collector test failed"
                details = {"test_passed": False}
            
        except Exception as e:
            status = "unhealthy"
            message = f"Metrics collector error: {str(e)}"
            details = {"error": str(e)}
        
        response_time = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            component="metrics_collector",
            status=status,
            message=message,
            details=details,
            response_time_ms=response_time
        )
    
    def _check_performance_monitor(self) -> HealthCheckResult:
        """Check performance monitor health."""
        start_time = time.time()
        
        try:
            performance_monitor = get_performance_monitor()
            
            # Get performance report
            report = performance_monitor.get_performance_report()
            
            if report:
                alerts_count = len(report.get("alerts", []))
                status = "healthy" if alerts_count == 0 else "degraded"
                message = f"Performance monitor active with {alerts_count} alerts"
                details = {
                    "alerts_count": alerts_count,
                    "metrics_count": report.get("metrics_count", 0)
                }
            else:
                status = "degraded"
                message = "Performance monitor returned empty report"
                details = {}
            
        except Exception as e:
            status = "unhealthy"
            message = f"Performance monitor error: {str(e)}"
            details = {"error": str(e)}
        
        response_time = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            component="performance_monitor",
            status=status,
            message=message,
            details=details,
            response_time_ms=response_time
        )
    
    def _check_llm_monitor(self) -> HealthCheckResult:
        """Check LLM monitor health."""
        start_time = time.time()
        
        try:
            llm_monitor = get_llm_monitor()
            
            # Get LLM performance report
            report = llm_monitor.get_performance_report()
            
            if report:
                providers_count = len(report.get("providers", {}))
                total_requests = report.get("summary", {}).get("total_requests", 0)
                
                status = "healthy"
                message = f"LLM monitor tracking {providers_count} providers, {total_requests} total requests"
                details = {
                    "providers_count": providers_count,
                    "total_requests": total_requests,
                    "success_rate": report.get("summary", {}).get("overall_success_rate", 0.0)
                }
            else:
                status = "degraded"
                message = "LLM monitor returned empty report"
                details = {}
            
        except Exception as e:
            status = "unhealthy"
            message = f"LLM monitor error: {str(e)}"
            details = {"error": str(e)}
        
        response_time = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            component="llm_monitor",
            status=status,
            message=message,
            details=details,
            response_time_ms=response_time
        )
    
    def _check_monitoring_manager(self) -> HealthCheckResult:
        """Check monitoring manager health."""
        start_time = time.time()
        
        try:
            monitoring_manager = get_monitoring_manager()
            
            if monitoring_manager:
                health_status = monitoring_manager.get_health_status()
                
                if health_status["status"] == "healthy":
                    status = "healthy"
                    message = "Monitoring manager is healthy"
                elif health_status["status"] == "degraded":
                    status = "degraded"
                    message = "Monitoring manager is degraded"
                else:
                    status = "unhealthy"
                    message = "Monitoring manager is unhealthy"
                
                details = {
                    "components_count": len(health_status.get("components", {})),
                    "alerts_count": len(health_status.get("alerts", [])),
                    "monitoring_active": health_status.get("components", {}).get("monitoring_thread", {}).get("active", False)
                }
            else:
                status = "degraded"
                message = "Monitoring manager not initialized"
                details = {"initialized": False}
            
        except Exception as e:
            status = "unhealthy"
            message = f"Monitoring manager error: {str(e)}"
            details = {"error": str(e)}
        
        response_time = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            component="monitoring_manager",
            status=status,
            message=message,
            details=details,
            response_time_ms=response_time
        )
    
    def _check_logging_system(self) -> HealthCheckResult:
        """Check logging system health."""
        start_time = time.time()
        
        try:
            # Test logging functionality
            test_logger = logging.getLogger("health_check_test")
            test_logger.info("Health check test log message")
            
            # Check log level configuration
            root_logger = logging.getLogger()
            current_level = root_logger.getEffectiveLevel()
            expected_level = getattr(logging, self.config.log_level.upper())
            
            if current_level == expected_level:
                status = "healthy"
                message = f"Logging system configured correctly at {self.config.log_level} level"
                details = {
                    "log_level": self.config.log_level,
                    "handlers_count": len(root_logger.handlers),
                    "effective_level": current_level
                }
            else:
                status = "degraded"
                message = f"Log level mismatch: expected {expected_level}, got {current_level}"
                details = {
                    "expected_level": expected_level,
                    "actual_level": current_level
                }
            
        except Exception as e:
            status = "unhealthy"
            message = f"Logging system error: {str(e)}"
            details = {"error": str(e)}
        
        response_time = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            component="logging_system",
            status=status,
            message=message,
            details=details,
            response_time_ms=response_time
        )
    
    def _check_configuration(self) -> HealthCheckResult:
        """Check configuration health."""
        start_time = time.time()
        
        try:
            # Validate configuration
            config_issues = []
            
            # Check LLM configuration
            if not self.config.llm_config.provider:
                config_issues.append("LLM provider not configured")
            
            if not self.config.llm_config.model:
                config_issues.append("LLM model not configured")
            
            # Check Redis configuration
            if not self.config.redis_config.host:
                config_issues.append("Redis host not configured")
            
            # Check document size limits
            if self.config.max_document_size <= 0:
                config_issues.append("Invalid document size limit")
            
            if config_issues:
                status = "degraded"
                message = f"Configuration issues found: {', '.join(config_issues)}"
                details = {"issues": config_issues}
            else:
                status = "healthy"
                message = "Configuration is valid"
                details = {
                    "llm_provider": self.config.llm_config.provider,
                    "llm_model": self.config.llm_config.model,
                    "max_document_size": self.config.max_document_size,
                    "log_level": self.config.log_level
                }
            
        except Exception as e:
            status = "unhealthy"
            message = f"Configuration validation error: {str(e)}"
            details = {"error": str(e)}
        
        response_time = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            component="configuration",
            status=status,
            message=message,
            details=details,
            response_time_ms=response_time
        )
    
    def _check_system_resources(self) -> HealthCheckResult:
        """Check system resource usage."""
        start_time = time.time()
        
        try:
            import psutil
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Determine status based on resource usage
            issues = []
            
            if cpu_percent > 90:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            if memory.percent > 90:
                issues.append(f"High memory usage: {memory.percent:.1f}%")
            
            if disk.percent > 90:
                issues.append(f"High disk usage: {disk.percent:.1f}%")
            
            if issues:
                status = "degraded"
                message = f"Resource constraints detected: {', '.join(issues)}"
            else:
                status = "healthy"
                message = "System resources are within normal limits"
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3)
            }
            
        except ImportError:
            # psutil not available
            status = "degraded"
            message = "System resource monitoring not available (psutil not installed)"
            details = {"psutil_available": False}
            
        except Exception as e:
            status = "unhealthy"
            message = f"System resource check error: {str(e)}"
            details = {"error": str(e)}
        
        response_time = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            component="system_resources",
            status=status,
            message=message,
            details=details,
            response_time_ms=response_time
        )


def create_health_checker(config: ServerConfig) -> HealthChecker:
    """Create a health checker instance.
    
    Args:
        config: Server configuration
        
    Returns:
        HealthChecker instance
    """
    return HealthChecker(config)