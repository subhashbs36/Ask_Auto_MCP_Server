# Monitoring and Logging System

The JSON Editor MCP Tool includes a comprehensive monitoring and logging system that provides:

- **Structured logging** with configurable levels and output formats
- **Metrics collection** for request processing times and system performance
- **LLM provider performance monitoring** with detailed tracking
- **Error rate tracking** and alerting capabilities
- **Health checks** for system components
- **Request/response logging** for debugging

## Quick Start

### Basic Setup

```python
from json_editor_mcp.config.models import ServerConfig, MonitoringConfig
from json_editor_mcp.utils.monitoring_integration import initialize_monitoring

# Configure monitoring
config = ServerConfig(
    monitoring_config=MonitoringConfig(
        enabled=True,
        track_requests=True,
        track_performance=True,
        track_llm_performance=True
    ),
    log_level="INFO"
)

# Initialize monitoring system
result = initialize_monitoring(config)
print(f"Monitoring initialized: {result['status']}")
```

### Server Integration

```python
from json_editor_mcp.utils.server_monitoring import ServerMonitoringMixin

class MyMCPServer(ServerMonitoringMixin):
    def __init__(self, config):
        super().__init__(config)
        
        # Initialize monitoring
        self.initialize_server_monitoring()
    
    def get_health(self):
        return self.get_server_health()
    
    def get_metrics(self):
        return self.get_server_metrics()
```

## Core Components

### 1. Metrics Collection

The metrics system tracks various performance indicators:

```python
from json_editor_mcp.utils.metrics import get_metrics_collector, timer

metrics = get_metrics_collector()

# Counter metrics
metrics.increment_counter("requests_total", 1.0, {"operation": "preview"})

# Histogram metrics
metrics.record_histogram("document_size_bytes", 1024)

# Timer metrics (using decorator)
@timer("operation_duration_seconds")
def my_operation():
    # Your code here
    pass

# Timer metrics (using context manager)
from json_editor_mcp.utils.metrics import TimerContext

with TimerContext(metrics, "manual_operation", {"type": "preview"}):
    # Your code here
    pass
```

### 2. LLM Performance Monitoring

Track LLM provider performance and reliability:

```python
from json_editor_mcp.utils.llm_monitoring import track_llm_request

# Track LLM requests
with track_llm_request("gemini", "gemini-pro", "request_123", prompt_tokens=100) as tracker:
    # Make LLM request
    response = await llm_service.get_response(prompt)
    
    # Set completion tokens
    tracker.set_completion_tokens(50)
    tracker.set_retry_count(1)  # If retries were needed

# Get LLM performance report
from json_editor_mcp.utils.llm_monitoring import get_llm_monitor

llm_monitor = get_llm_monitor()
report = llm_monitor.get_performance_report()
```

### 3. Health Checks

Comprehensive health monitoring for all system components:

```python
from json_editor_mcp.utils.health_check import create_health_checker

health_checker = create_health_checker(config)

# Comprehensive health check
health = health_checker.check_all_components()
print(f"Overall status: {health['overall_status']}")

# Readiness check (for Kubernetes)
readiness = health_checker.check_readiness()
print(f"Ready: {readiness['ready']}")

# Liveness check (for Kubernetes)
liveness = health_checker.check_liveness()
print(f"Alive: {liveness['alive']}")
```

### 4. Structured Logging

Advanced logging with JSON formatting and error tracking:

```python
from json_editor_mcp.utils.logging_config import get_logger, log_performance_metrics

logger = get_logger(__name__)

# Standard logging
logger.info("Operation completed successfully")

# Performance logging
log_performance_metrics(
    logger, "preview_operation", 
    duration=1.5, 
    request_id="req_123",
    changes_count=5
)

# Error logging with context
from json_editor_mcp.utils.logging_config import log_error_with_context

try:
    # Your code
    pass
except Exception as e:
    log_error_with_context(
        logger, e,
        {"request_id": "req_123", "operation": "preview"},
        "handle_preview"
    )
```

## Configuration

### Monitoring Configuration

```python
from json_editor_mcp.config.models import MonitoringConfig

monitoring_config = MonitoringConfig(
    enabled=True,                           # Enable monitoring
    track_requests=True,                    # Track request metrics
    track_performance=True,                 # Track performance metrics
    track_llm_performance=True,             # Track LLM performance
    track_errors=True,                      # Track error rates
    monitoring_interval_seconds=30,         # Check interval
    report_interval_seconds=300,            # Report interval
    max_history_size=1000,                  # Max metrics history
    alert_thresholds={                      # Custom alert thresholds
        "avg_response_time": 5.0,
        "error_rate": 0.05
    }
)
```

### Logging Configuration

```python
from json_editor_mcp.utils.logging_config import setup_logging

log_config = setup_logging(
    log_level="INFO",                       # Log level
    log_file="logs/app.log",               # Optional log file
    enable_json_logging=True,              # JSON format
    enable_error_tracking=True,            # Error tracking
    enable_debug_logging=True              # Debug logging
)
```

## Metrics Reference

### Request Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|---------|
| `requests_started_total` | Counter | Total requests started | `operation`, `request_id` |
| `requests_completed_total` | Counter | Total requests completed | `operation`, `status` |
| `request_errors_total` | Counter | Total request errors | `operation`, `error_type` |
| `*_request_duration_seconds` | Timer | Request processing time | `operation`, `status` |

### Document Processing Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|---------|
| `document_size_bytes` | Histogram | Document size distribution | `operation` |
| `changes_count` | Histogram | Number of changes per request | `operation` |
| `*_processing_duration_seconds` | Timer | Processing time by stage | `operation` |

### LLM Performance Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|---------|
| `llm_requests_started_total` | Counter | LLM requests started | `provider`, `model` |
| `llm_requests_completed_total` | Counter | LLM requests completed | `provider`, `model`, `status` |
| `llm_request_duration_seconds` | Timer | LLM request duration | `provider`, `model`, `status` |
| `llm_tokens_total` | Histogram | Token usage distribution | `provider`, `model` |
| `llm_retry_count` | Histogram | Retry attempts | `provider`, `model` |
| `llm_rate_limit_delay_seconds` | Histogram | Rate limit delays | `provider`, `model` |

## Alerting

### Default Alert Thresholds

The system includes default alert thresholds:

- **Request Processing Time**: Average > 10s, P95 > 30s
- **LLM Response Time**: Average > 15s, P99 > 60s
- **Error Rates**: > 50 total errors, > 10 LLM errors

### Custom Alerts

```python
from json_editor_mcp.utils.metrics import get_performance_monitor

monitor = get_performance_monitor()

# Set custom thresholds
monitor.set_alert_threshold("preview_request_duration_seconds", "avg_max", 5.0)
monitor.set_alert_threshold("request_errors_total", "current_max", 25.0)

# Add alert callback
def my_alert_handler(metric_name, threshold_type, current_value, threshold_value):
    print(f"ALERT: {metric_name} = {current_value} exceeds {threshold_value}")

monitor.add_alert_callback("preview_request_duration_seconds", my_alert_handler)
```

## Health Check Endpoints

The system provides standard health check endpoints:

### `/health` - Comprehensive Health Check

Returns detailed health status of all components:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "overall_status": "healthy",
  "components": {
    "metrics_collector": {
      "status": "healthy",
      "message": "Metrics collector is functioning normally"
    },
    "llm_monitor": {
      "status": "healthy", 
      "message": "LLM monitor tracking 1 providers"
    }
  },
  "response_time_ms": 45.2
}
```

### `/ready` - Readiness Check

Returns whether the system is ready to serve requests:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "ready": true,
  "checks": {
    "configuration": {"status": "healthy"},
    "logging": {"status": "healthy"},
    "metrics": {"status": "healthy"}
  }
}
```

### `/live` - Liveness Check

Returns whether the system is alive and responsive:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "alive": true,
  "uptime_seconds": 3600,
  "message": "System is alive and responsive"
}
```

## Integration Examples

### With MCP Server

```python
from json_editor_mcp.utils.server_monitoring import add_monitoring_endpoints

# Add monitoring endpoints to your MCP server
add_monitoring_endpoints(server_instance, config)

# Access endpoints
health = server_instance._health_endpoint()
metrics = server_instance._metrics_endpoint()
```

### Request Tracking

```python
from json_editor_mcp.utils.monitoring_config import get_monitoring_manager

async def handle_preview_request(request_data):
    monitoring = get_monitoring_manager()
    request_id = generate_request_id()
    
    # Record request start
    if monitoring:
        monitoring.record_request_start("preview", request_id)
    
    try:
        # Process request
        result = await process_preview(request_data)
        
        # Record success
        if monitoring:
            monitoring.record_request_complete("preview", request_id, "success")
        
        return result
        
    except Exception as e:
        # Record error
        if monitoring:
            monitoring.record_request_complete("preview", request_id, "error", type(e).__name__)
        raise
```

## Troubleshooting

### Common Issues

1. **Monitoring not starting**: Check that `monitoring_config.enabled = True`
2. **No metrics collected**: Ensure monitoring manager is initialized
3. **Health checks failing**: Check component dependencies and configuration
4. **High memory usage**: Reduce `max_history_size` in monitoring config

### Debug Logging

Enable debug logging to troubleshoot monitoring issues:

```python
import logging
logging.getLogger("json_editor_mcp.utils").setLevel(logging.DEBUG)
```

### Monitoring Status

Check monitoring system status:

```python
from json_editor_mcp.utils.monitoring_integration import get_monitoring_status

status = get_monitoring_status()
print(f"Monitoring initialized: {status['initialized']}")
print(f"Status: {status['status']}")
```

## Performance Considerations

- **Metrics Collection**: Minimal overhead (~1-2ms per operation)
- **Memory Usage**: Configurable history size (default 1000 entries per metric)
- **Storage**: Uses in-memory storage with Redis for session data
- **Thread Safety**: All components are thread-safe for concurrent use

## Best Practices

1. **Enable monitoring in production** for observability
2. **Set appropriate alert thresholds** based on your SLAs
3. **Monitor LLM provider performance** to detect issues early
4. **Use structured logging** for better log analysis
5. **Implement health checks** for container orchestration
6. **Regular monitoring reports** for capacity planning

## Example Output

Run the monitoring demo to see the system in action:

```bash
python examples/monitoring_demo.py
```

This will demonstrate all monitoring features with simulated data and show comprehensive reports.