#!/usr/bin/env python3
"""
Demonstration of the JSON Editor MCP Tool monitoring and metrics system.

This script shows how to:
1. Initialize comprehensive monitoring
2. Track requests and LLM performance
3. Generate health checks and metrics reports
4. Set up custom alerts
"""

import asyncio
import time
import logging
from datetime import datetime

# Import the monitoring components
from json_editor_mcp.config.models import ServerConfig, LLMConfig, MonitoringConfig
from json_editor_mcp.utils.monitoring_integration import initialize_monitoring, get_monitoring_integration
from json_editor_mcp.utils.metrics import get_metrics_collector, get_performance_monitor
from json_editor_mcp.utils.llm_monitoring import get_llm_monitor, track_llm_request
from json_editor_mcp.utils.health_check import create_health_checker


def create_demo_config() -> ServerConfig:
    """Create a demo configuration for testing monitoring."""
    
    llm_config = LLMConfig(
        provider="gemini",
        model="gemini-pro",
        api_key="demo-key"
    )
    
    monitoring_config = MonitoringConfig(
        enabled=True,
        track_requests=True,
        track_performance=True,
        track_llm_performance=True,
        track_errors=True,
        monitoring_interval_seconds=30,
        report_interval_seconds=60
    )
    
    return ServerConfig(
        llm_config=llm_config,
        monitoring_config=monitoring_config,
        log_level="INFO"
    )


async def simulate_llm_requests():
    """Simulate some LLM requests for monitoring demonstration."""
    
    llm_monitor = get_llm_monitor()
    
    print("Simulating LLM requests...")
    
    # Simulate successful requests
    for i in range(5):
        request_id = f"demo_request_{i}"
        
        with track_llm_request("gemini", "gemini-pro", request_id, prompt_tokens=100) as tracker:
            # Simulate processing time
            await asyncio.sleep(0.5 + i * 0.1)  # Variable processing time
            
            # Set completion tokens
            tracker.set_completion_tokens(50 + i * 10)
    
    # Simulate a failed request
    try:
        with track_llm_request("gemini", "gemini-pro", "demo_error_request", prompt_tokens=150):
            await asyncio.sleep(0.2)
            raise Exception("Simulated LLM error")
    except Exception:
        pass  # Error is automatically tracked by the context manager
    
    print("LLM request simulation complete")


def simulate_request_processing():
    """Simulate request processing for metrics demonstration."""
    
    metrics_collector = get_metrics_collector()
    
    print("Simulating request processing...")
    
    # Simulate preview requests
    for i in range(10):
        request_id = f"preview_request_{i}"
        
        # Record request start
        start_time = time.time()
        metrics_collector.increment_counter("requests_started_total", 1.0, {"operation": "preview"})
        
        # Simulate processing
        processing_time = 0.1 + i * 0.05  # Variable processing time
        time.sleep(processing_time)
        
        # Record completion
        duration = time.time() - start_time
        status = "success" if i < 8 else "error"  # Simulate some errors
        
        labels = {"operation": "preview", "status": status}
        metrics_collector.increment_counter("requests_completed_total", 1.0, labels)
        metrics_collector.record_timer("preview_request_duration_seconds", duration, labels)
        
        # Record document processing metrics
        doc_size = 1000 + i * 500  # Variable document sizes
        changes_count = 1 + i // 2  # Variable change counts
        
        metrics_collector.record_histogram("document_size_bytes", doc_size, {"operation": "preview"})
        metrics_collector.record_histogram("changes_count", changes_count, {"operation": "preview"})
    
    print("Request processing simulation complete")


def demonstrate_health_checks(config: ServerConfig):
    """Demonstrate health check functionality."""
    
    print("\n=== Health Check Demonstration ===")
    
    health_checker = create_health_checker(config)
    
    # Comprehensive health check
    print("Running comprehensive health check...")
    health_report = health_checker.check_all_components()
    
    print(f"Overall Status: {health_report['overall_status']}")
    print(f"Components Checked: {health_report['summary']['total_components']}")
    print(f"Healthy: {health_report['summary']['healthy_components']}")
    print(f"Degraded: {health_report['summary']['degraded_components']}")
    print(f"Unhealthy: {health_report['summary']['unhealthy_components']}")
    
    # Show component details
    for component, details in health_report['components'].items():
        status_emoji = "✅" if details['status'] == 'healthy' else "⚠️" if details['status'] == 'degraded' else "❌"
        print(f"  {status_emoji} {component}: {details['message']}")
    
    # Readiness check
    print("\nRunning readiness check...")
    readiness = health_checker.check_readiness()
    ready_emoji = "✅" if readiness['ready'] else "❌"
    print(f"{ready_emoji} System Ready: {readiness['ready']}")
    
    # Liveness check
    print("\nRunning liveness check...")
    liveness = health_checker.check_liveness()
    alive_emoji = "✅" if liveness['alive'] else "❌"
    print(f"{alive_emoji} System Alive: {liveness['alive']}")


def demonstrate_metrics_and_alerts():
    """Demonstrate metrics collection and alerting."""
    
    print("\n=== Metrics and Alerts Demonstration ===")
    
    metrics_collector = get_metrics_collector()
    performance_monitor = get_performance_monitor()
    
    # Show current metrics
    all_metrics = metrics_collector.get_all_metrics()
    print(f"Total Metrics Collected: {len(all_metrics)}")
    
    for name, summary in all_metrics.items():
        print(f"  📊 {name}:")
        print(f"    Type: {summary.metric_type.value}")
        print(f"    Current: {summary.current_value}")
        print(f"    Count: {summary.total_count}")
        if summary.avg_value:
            print(f"    Average: {summary.avg_value:.3f}")
        if summary.p95_value:
            print(f"    P95: {summary.p95_value:.3f}")
    
    # Set up custom alert
    print("\nSetting up custom alert threshold...")
    performance_monitor.set_alert_threshold("preview_request_duration_seconds", "avg_max", 0.2)
    
    # Check alerts
    print("Checking alerts...")
    performance_monitor.check_alerts()
    
    # Generate performance report
    print("\nGenerating performance report...")
    perf_report = performance_monitor.get_performance_report()
    
    if perf_report.get("alerts"):
        print("🚨 Performance Alerts:")
        for alert in perf_report["alerts"]:
            print(f"  - {alert}")
    else:
        print("✅ No performance alerts")


def demonstrate_llm_monitoring():
    """Demonstrate LLM performance monitoring."""
    
    print("\n=== LLM Performance Monitoring ===")
    
    llm_monitor = get_llm_monitor()
    
    # Get LLM performance report
    llm_report = llm_monitor.get_performance_report()
    
    print(f"Total Providers: {llm_report['summary']['total_providers']}")
    print(f"Total Requests: {llm_report['summary']['total_requests']}")
    print(f"Overall Success Rate: {llm_report['summary']['overall_success_rate']:.2%}")
    print(f"Average Response Time: {llm_report['summary']['avg_response_time']:.3f}s")
    
    # Show provider details
    for provider_key, provider_data in llm_report['providers'].items():
        print(f"\n📡 Provider: {provider_key}")
        print(f"  Success Rate: {provider_data['success_rate']:.2%}")
        print(f"  Average Duration: {provider_data['avg_duration']:.3f}s")
        print(f"  Total Requests: {provider_data['total_requests']}")
        print(f"  Tokens/Second: {provider_data['tokens_per_second']:.1f}")
        
        if provider_data['alerts']:
            print("  🚨 Alerts:")
            for alert in provider_data['alerts']:
                print(f"    - {alert}")


async def main():
    """Main demonstration function."""
    
    print("🚀 JSON Editor MCP Tool - Monitoring System Demo")
    print("=" * 50)
    
    # Create configuration
    config = create_demo_config()
    
    # Initialize monitoring
    print("Initializing monitoring system...")
    init_result = initialize_monitoring(config)
    
    if init_result["status"] != "success":
        print(f"❌ Failed to initialize monitoring: {init_result}")
        return
    
    print("✅ Monitoring system initialized successfully")
    
    # Get monitoring integration
    monitoring_integration = get_monitoring_integration()
    if not monitoring_integration:
        print("❌ Failed to get monitoring integration")
        return
    
    # Simulate some activity
    print("\n📊 Simulating system activity...")
    
    # Simulate request processing
    simulate_request_processing()
    
    # Simulate LLM requests
    await simulate_llm_requests()
    
    # Wait a moment for metrics to be processed
    time.sleep(1)
    
    # Demonstrate health checks
    demonstrate_health_checks(config)
    
    # Demonstrate metrics and alerts
    demonstrate_metrics_and_alerts()
    
    # Demonstrate LLM monitoring
    demonstrate_llm_monitoring()
    
    # Generate comprehensive report
    print("\n=== Comprehensive Monitoring Report ===")
    comprehensive_report = monitoring_integration.get_comprehensive_report()
    
    print(f"Report Timestamp: {comprehensive_report.get('timestamp', 'Unknown')}")
    print(f"System Health: {comprehensive_report.get('health_check', {}).get('overall_status', 'Unknown')}")
    print(f"Total Metrics: {len(comprehensive_report.get('general_metrics', {}))}")
    
    # Show system status
    system_status = monitoring_integration.get_status()
    print(f"Monitoring Active: {system_status.get('initialized', False)}")
    
    print("\n✅ Monitoring demonstration complete!")
    print("\nKey Features Demonstrated:")
    print("  📊 Comprehensive metrics collection")
    print("  🔍 Health checks and system monitoring")
    print("  🚨 Performance alerts and thresholds")
    print("  📡 LLM provider performance tracking")
    print("  📈 Request processing metrics")
    print("  🏥 Readiness and liveness checks")


if __name__ == "__main__":
    # Set up basic logging for the demo
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the demonstration
    asyncio.run(main())