"""Metrics collection and monitoring for JSON Editor MCP Tool."""

import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import statistics
import logging


class MetricType(Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """Individual metric value with timestamp."""
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    name: str
    metric_type: MetricType
    current_value: Optional[float] = None
    total_count: int = 0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None
    p95_value: Optional[float] = None
    p99_value: Optional[float] = None
    last_updated: Optional[datetime] = None


class MetricsCollector:
    """Thread-safe metrics collector for performance monitoring."""
    
    def __init__(self, max_history: int = 1000):
        """Initialize metrics collector.
        
        Args:
            max_history: Maximum number of historical values to keep per metric
        """
        self.max_history = max_history
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric.
        
        Args:
            name: Metric name
            value: Value to increment by
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._get_metric_key(name, labels)
            self._counters[key] += value
            
            metric_value = MetricValue(
                value=self._counters[key],
                timestamp=datetime.now(),
                labels=labels or {}
            )
            self._metrics[key].append(metric_value)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value.
        
        Args:
            name: Metric name
            value: Current value
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._get_metric_key(name, labels)
            self._gauges[key] = value
            
            metric_value = MetricValue(
                value=value,
                timestamp=datetime.now(),
                labels=labels or {}
            )
            self._metrics[key].append(metric_value)
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram value.
        
        Args:
            name: Metric name
            value: Value to record
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._get_metric_key(name, labels)
            
            metric_value = MetricValue(
                value=value,
                timestamp=datetime.now(),
                labels=labels or {}
            )
            self._metrics[key].append(metric_value)
    
    def record_timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None):
        """Record a timer duration.
        
        Args:
            name: Metric name
            duration: Duration in seconds
            labels: Optional labels for the metric
        """
        self.record_histogram(f"{name}_duration_seconds", duration, labels)
    
    def get_metric_summary(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[MetricSummary]:
        """Get summary statistics for a metric.
        
        Args:
            name: Metric name
            labels: Optional labels filter
            
        Returns:
            MetricSummary if metric exists, None otherwise
        """
        with self._lock:
            key = self._get_metric_key(name, labels)
            
            if key not in self._metrics:
                return None
            
            values = [mv.value for mv in self._metrics[key]]
            
            if not values:
                return None
            
            # Determine metric type
            metric_type = MetricType.HISTOGRAM
            if key in self._counters:
                metric_type = MetricType.COUNTER
            elif key in self._gauges:
                metric_type = MetricType.GAUGE
            elif "_duration_seconds" in name:
                metric_type = MetricType.TIMER
            
            summary = MetricSummary(
                name=name,
                metric_type=metric_type,
                current_value=values[-1] if values else None,
                total_count=len(values),
                min_value=min(values),
                max_value=max(values),
                avg_value=statistics.mean(values),
                last_updated=self._metrics[key][-1].timestamp if self._metrics[key] else None
            )
            
            # Calculate percentiles for histograms and timers
            if metric_type in [MetricType.HISTOGRAM, MetricType.TIMER] and len(values) >= 2:
                sorted_values = sorted(values)
                summary.p95_value = self._percentile(sorted_values, 95)
                summary.p99_value = self._percentile(sorted_values, 99)
            
            return summary
    
    def get_all_metrics(self) -> Dict[str, MetricSummary]:
        """Get summaries for all metrics.
        
        Returns:
            Dictionary of metric name to MetricSummary
        """
        with self._lock:
            summaries = {}
            
            # Get all unique metric names (without labels)
            metric_names = set()
            for key in self._metrics.keys():
                base_name = key.split('{')[0]  # Remove label part
                metric_names.add(base_name)
            
            for name in metric_names:
                summary = self.get_metric_summary(name)
                if summary:
                    summaries[name] = summary
            
            return summaries
    
    def clear_metrics(self):
        """Clear all collected metrics."""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
    
    def get_metrics_since(self, since: datetime) -> Dict[str, List[MetricValue]]:
        """Get all metric values since a specific time.
        
        Args:
            since: Timestamp to filter from
            
        Returns:
            Dictionary of metric name to list of MetricValue
        """
        with self._lock:
            filtered_metrics = {}
            
            for key, values in self._metrics.items():
                filtered_values = [mv for mv in values if mv.timestamp >= since]
                if filtered_values:
                    base_name = key.split('{')[0]
                    filtered_metrics[base_name] = filtered_values
            
            return filtered_metrics
    
    def _get_metric_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Generate a unique key for a metric with labels.
        
        Args:
            name: Metric name
            labels: Optional labels
            
        Returns:
            Unique metric key
        """
        if not labels:
            return name
        
        # Sort labels for consistent key generation
        label_str = ','.join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile value from sorted list.
        
        Args:
            sorted_values: List of values in ascending order
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value
        """
        if not sorted_values:
            return 0.0
        
        index = (percentile / 100.0) * (len(sorted_values) - 1)
        
        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(sorted_values) - 1)
            weight = index - lower_index
            
            return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight


class PerformanceMonitor:
    """Monitor for tracking performance metrics and alerting."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        """Initialize performance monitor.
        
        Args:
            metrics_collector: MetricsCollector instance to use
        """
        self.metrics = metrics_collector
        self.logger = logging.getLogger(__name__)
        self._alert_thresholds: Dict[str, Dict[str, float]] = {}
        self._alert_callbacks: Dict[str, List[Callable]] = defaultdict(list)
    
    def set_alert_threshold(self, metric_name: str, threshold_type: str, value: float):
        """Set alert threshold for a metric.
        
        Args:
            metric_name: Name of the metric to monitor
            threshold_type: Type of threshold ('max', 'min', 'avg_max', 'p95_max', etc.)
            value: Threshold value
        """
        if metric_name not in self._alert_thresholds:
            self._alert_thresholds[metric_name] = {}
        
        self._alert_thresholds[metric_name][threshold_type] = value
        self.logger.info(f"Set alert threshold for {metric_name}.{threshold_type}: {value}")
    
    def add_alert_callback(self, metric_name: str, callback: Callable[[str, str, float, float], None]):
        """Add callback function for metric alerts.
        
        Args:
            metric_name: Name of the metric to monitor
            callback: Function to call when threshold is exceeded
                     Signature: callback(metric_name, threshold_type, current_value, threshold_value)
        """
        self._alert_callbacks[metric_name].append(callback)
    
    def check_alerts(self):
        """Check all metrics against their thresholds and trigger alerts."""
        for metric_name, thresholds in self._alert_thresholds.items():
            summary = self.metrics.get_metric_summary(metric_name)
            
            if not summary:
                continue
            
            for threshold_type, threshold_value in thresholds.items():
                current_value = self._get_threshold_value(summary, threshold_type)
                
                if current_value is not None and self._should_alert(current_value, threshold_value, threshold_type):
                    self._trigger_alert(metric_name, threshold_type, current_value, threshold_value)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report.
        
        Returns:
            Dictionary containing performance metrics and analysis
        """
        all_metrics = self.metrics.get_all_metrics()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "metrics_count": len(all_metrics),
            "metrics": {},
            "alerts": [],
            "performance_analysis": {}
        }
        
        # Add metric summaries
        for name, summary in all_metrics.items():
            report["metrics"][name] = {
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
        
        # Check for performance issues
        self._analyze_performance(report, all_metrics)
        
        return report
    
    def _get_threshold_value(self, summary: MetricSummary, threshold_type: str) -> Optional[float]:
        """Get the appropriate value from metric summary for threshold comparison.
        
        Args:
            summary: MetricSummary to extract value from
            threshold_type: Type of threshold
            
        Returns:
            Value to compare against threshold, or None if not available
        """
        if threshold_type == "max":
            return summary.max_value
        elif threshold_type == "min":
            return summary.min_value
        elif threshold_type == "avg_max":
            return summary.avg_value
        elif threshold_type == "p95_max":
            return summary.p95_value
        elif threshold_type == "p99_max":
            return summary.p99_value
        elif threshold_type == "current_max":
            return summary.current_value
        else:
            return summary.current_value
    
    def _should_alert(self, current_value: float, threshold_value: float, threshold_type: str) -> bool:
        """Determine if an alert should be triggered.
        
        Args:
            current_value: Current metric value
            threshold_value: Threshold to compare against
            threshold_type: Type of threshold
            
        Returns:
            True if alert should be triggered
        """
        if "max" in threshold_type:
            return current_value > threshold_value
        elif "min" in threshold_type:
            return current_value < threshold_value
        else:
            return current_value > threshold_value
    
    def _trigger_alert(self, metric_name: str, threshold_type: str, current_value: float, threshold_value: float):
        """Trigger alert for metric threshold violation.
        
        Args:
            metric_name: Name of the metric
            threshold_type: Type of threshold violated
            current_value: Current metric value
            threshold_value: Threshold that was violated
        """
        alert_message = (
            f"Alert: {metric_name}.{threshold_type} = {current_value:.3f} "
            f"exceeds threshold {threshold_value:.3f}"
        )
        
        self.logger.warning(alert_message, extra={
            "alert_type": "metric_threshold",
            "metric_name": metric_name,
            "threshold_type": threshold_type,
            "current_value": current_value,
            "threshold_value": threshold_value
        })
        
        # Call registered callbacks
        for callback in self._alert_callbacks.get(metric_name, []):
            try:
                callback(metric_name, threshold_type, current_value, threshold_value)
            except Exception as e:
                self.logger.error(f"Error in alert callback for {metric_name}: {e}")
    
    def _analyze_performance(self, report: Dict[str, Any], metrics: Dict[str, MetricSummary]):
        """Analyze performance metrics and add insights to report.
        
        Args:
            report: Report dictionary to add analysis to
            metrics: Dictionary of metric summaries
        """
        analysis = report["performance_analysis"]
        
        # Analyze request processing times
        for name, summary in metrics.items():
            if "_duration_seconds" in name and summary.metric_type == MetricType.TIMER:
                if summary.avg_value and summary.avg_value > 5.0:  # > 5 seconds average
                    analysis[f"{name}_slow"] = {
                        "issue": "Slow processing time",
                        "avg_duration": summary.avg_value,
                        "recommendation": "Consider optimizing the operation or increasing resources"
                    }
                
                if summary.p99_value and summary.p99_value > 30.0:  # > 30 seconds p99
                    analysis[f"{name}_outliers"] = {
                        "issue": "High latency outliers",
                        "p99_duration": summary.p99_value,
                        "recommendation": "Investigate timeout handling and resource constraints"
                    }
        
        # Analyze error rates
        for name, summary in metrics.items():
            if "error" in name and summary.metric_type == MetricType.COUNTER:
                if summary.current_value and summary.current_value > 10:  # > 10 errors
                    analysis[f"{name}_high"] = {
                        "issue": "High error count",
                        "error_count": summary.current_value,
                        "recommendation": "Review error logs and investigate root causes"
                    }


class TimerContext:
    """Context manager for timing operations."""
    
    def __init__(self, metrics_collector: MetricsCollector, metric_name: str, 
                 labels: Optional[Dict[str, str]] = None):
        """Initialize timer context.
        
        Args:
            metrics_collector: MetricsCollector to record timing to
            metric_name: Name of the metric to record
            labels: Optional labels for the metric
        """
        self.metrics = metrics_collector
        self.metric_name = metric_name
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and record duration."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.metrics.record_timer(self.metric_name, duration, self.labels)


# Global metrics collector instance
_global_metrics_collector: Optional[MetricsCollector] = None
_global_performance_monitor: Optional[PerformanceMonitor] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _global_metrics_collector
    
    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()
    
    return _global_metrics_collector


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _global_performance_monitor
    
    if _global_performance_monitor is None:
        _global_performance_monitor = PerformanceMonitor(get_metrics_collector())
    
    return _global_performance_monitor


def timer(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator for timing function execution.
    
    Args:
        metric_name: Name of the metric to record
        labels: Optional labels for the metric
    
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with TimerContext(get_metrics_collector(), metric_name, labels):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def setup_default_alerts():
    """Set up default performance alert thresholds."""
    monitor = get_performance_monitor()
    
    # Request processing time alerts
    monitor.set_alert_threshold("preview_request_duration_seconds", "avg_max", 10.0)
    monitor.set_alert_threshold("preview_request_duration_seconds", "p95_max", 30.0)
    monitor.set_alert_threshold("apply_request_duration_seconds", "avg_max", 5.0)
    monitor.set_alert_threshold("apply_request_duration_seconds", "p95_max", 15.0)
    
    # LLM performance alerts
    monitor.set_alert_threshold("llm_request_duration_seconds", "avg_max", 15.0)
    monitor.set_alert_threshold("llm_request_duration_seconds", "p99_max", 60.0)
    
    # Error rate alerts
    monitor.set_alert_threshold("request_errors_total", "current_max", 50.0)
    monitor.set_alert_threshold("llm_errors_total", "current_max", 10.0)
    monitor.set_alert_threshold("session_errors_total", "current_max", 20.0)