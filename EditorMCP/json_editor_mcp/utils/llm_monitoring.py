"""LLM provider performance monitoring and tracking."""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, NamedTuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum

from .metrics import MetricsCollector, get_metrics_collector


class LLMRequestStatus(Enum):
    """Status of LLM requests."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_ERROR = "auth_error"
    INVALID_RESPONSE = "invalid_response"


@dataclass
class LLMRequestMetrics:
    """Metrics for a single LLM request."""
    provider: str
    model: str
    request_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    status: Optional[LLMRequestStatus] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    rate_limit_delay: Optional[float] = None


@dataclass
class LLMProviderStats:
    """Aggregated statistics for an LLM provider."""
    provider: str
    model: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    rate_limited_requests: int = 0
    auth_error_requests: int = 0
    invalid_response_requests: int = 0
    total_duration: float = 0.0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_retries: int = 0
    avg_duration: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    tokens_per_second: float = 0.0
    last_request_time: Optional[datetime] = None
    recent_errors: List[str] = field(default_factory=list)


class LLMPerformanceMonitor:
    """Monitor for tracking LLM provider performance and reliability."""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None, max_history: int = 1000):
        """Initialize LLM performance monitor.
        
        Args:
            metrics_collector: MetricsCollector instance to use
            max_history: Maximum number of request records to keep per provider
        """
        self.metrics = metrics_collector or get_metrics_collector()
        self.logger = logging.getLogger(__name__)
        self.max_history = max_history
        
        # Store request history per provider
        self._request_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._provider_stats: Dict[str, LLMProviderStats] = {}
        
        # Track active requests
        self._active_requests: Dict[str, LLMRequestMetrics] = {}
    
    def start_request(self, provider: str, model: str, request_id: str, 
                     prompt_tokens: Optional[int] = None) -> LLMRequestMetrics:
        """Start tracking an LLM request.
        
        Args:
            provider: LLM provider name
            model: Model name
            request_id: Unique request identifier
            prompt_tokens: Number of prompt tokens (if known)
            
        Returns:
            LLMRequestMetrics object for this request
        """
        request_metrics = LLMRequestMetrics(
            provider=provider,
            model=model,
            request_id=request_id,
            start_time=datetime.now(),
            prompt_tokens=prompt_tokens
        )
        
        self._active_requests[request_id] = request_metrics
        
        # Record request start metrics
        labels = {"provider": provider, "model": model}
        self.metrics.increment_counter("llm_requests_started_total", 1.0, labels)
        
        self.logger.debug(f"Started tracking LLM request {request_id} for {provider}/{model}")
        return request_metrics
    
    def complete_request(self, request_id: str, status: LLMRequestStatus,
                        completion_tokens: Optional[int] = None,
                        error_message: Optional[str] = None,
                        retry_count: int = 0,
                        rate_limit_delay: Optional[float] = None) -> Optional[LLMRequestMetrics]:
        """Complete tracking an LLM request.
        
        Args:
            request_id: Request identifier
            status: Final status of the request
            completion_tokens: Number of completion tokens (if applicable)
            error_message: Error message (if failed)
            retry_count: Number of retries performed
            rate_limit_delay: Total delay due to rate limiting
            
        Returns:
            Completed LLMRequestMetrics object, or None if request not found
        """
        if request_id not in self._active_requests:
            self.logger.warning(f"Attempted to complete unknown request {request_id}")
            return None
        
        request_metrics = self._active_requests.pop(request_id)
        request_metrics.end_time = datetime.now()
        request_metrics.duration_seconds = (request_metrics.end_time - request_metrics.start_time).total_seconds()
        request_metrics.status = status
        request_metrics.completion_tokens = completion_tokens
        request_metrics.error_message = error_message
        request_metrics.retry_count = retry_count
        request_metrics.rate_limit_delay = rate_limit_delay
        
        # Calculate total tokens
        if request_metrics.prompt_tokens and completion_tokens:
            request_metrics.total_tokens = request_metrics.prompt_tokens + completion_tokens
        
        # Store in history
        provider_key = f"{request_metrics.provider}/{request_metrics.model}"
        self._request_history[provider_key].append(request_metrics)
        
        # Update provider statistics
        self._update_provider_stats(request_metrics)
        
        # Record completion metrics
        labels = {
            "provider": request_metrics.provider,
            "model": request_metrics.model,
            "status": status.value
        }
        
        self.metrics.increment_counter("llm_requests_completed_total", 1.0, labels)
        self.metrics.record_timer("llm_request_duration_seconds", request_metrics.duration_seconds, labels)
        
        if request_metrics.total_tokens:
            self.metrics.record_histogram("llm_tokens_total", request_metrics.total_tokens, labels)
        
        if retry_count > 0:
            self.metrics.record_histogram("llm_retry_count", retry_count, labels)
        
        if rate_limit_delay:
            self.metrics.record_histogram("llm_rate_limit_delay_seconds", rate_limit_delay, labels)
        
        # Log completion
        if status == LLMRequestStatus.SUCCESS:
            self.logger.debug(f"Completed LLM request {request_id}: {request_metrics.duration_seconds:.3f}s")
        else:
            self.logger.warning(f"Failed LLM request {request_id}: {status.value} - {error_message}")
        
        return request_metrics
    
    def get_provider_stats(self, provider: str, model: Optional[str] = None) -> Optional[LLMProviderStats]:
        """Get statistics for a specific provider/model.
        
        Args:
            provider: Provider name
            model: Optional model name (if None, returns aggregated stats for provider)
            
        Returns:
            LLMProviderStats object or None if not found
        """
        if model:
            key = f"{provider}/{model}"
            return self._provider_stats.get(key)
        else:
            # Aggregate stats across all models for this provider
            provider_stats = None
            for key, stats in self._provider_stats.items():
                if stats.provider == provider:
                    if provider_stats is None:
                        provider_stats = LLMProviderStats(provider=provider, model="*")
                    
                    # Aggregate the stats
                    provider_stats.total_requests += stats.total_requests
                    provider_stats.successful_requests += stats.successful_requests
                    provider_stats.failed_requests += stats.failed_requests
                    provider_stats.timeout_requests += stats.timeout_requests
                    provider_stats.rate_limited_requests += stats.rate_limited_requests
                    provider_stats.auth_error_requests += stats.auth_error_requests
                    provider_stats.invalid_response_requests += stats.invalid_response_requests
                    provider_stats.total_duration += stats.total_duration
                    provider_stats.total_tokens += stats.total_tokens
                    provider_stats.total_prompt_tokens += stats.total_prompt_tokens
                    provider_stats.total_completion_tokens += stats.total_completion_tokens
                    provider_stats.total_retries += stats.total_retries
                    
                    if stats.last_request_time:
                        if not provider_stats.last_request_time or stats.last_request_time > provider_stats.last_request_time:
                            provider_stats.last_request_time = stats.last_request_time
                    
                    provider_stats.recent_errors.extend(stats.recent_errors[-5:])  # Keep recent errors
            
            # Calculate aggregated rates
            if provider_stats and provider_stats.total_requests > 0:
                provider_stats.success_rate = provider_stats.successful_requests / provider_stats.total_requests
                provider_stats.error_rate = provider_stats.failed_requests / provider_stats.total_requests
                provider_stats.avg_duration = provider_stats.total_duration / provider_stats.total_requests
                
                if provider_stats.total_duration > 0:
                    provider_stats.tokens_per_second = provider_stats.total_tokens / provider_stats.total_duration
            
            return provider_stats
    
    def get_all_provider_stats(self) -> Dict[str, LLMProviderStats]:
        """Get statistics for all providers.
        
        Returns:
            Dictionary mapping provider/model keys to LLMProviderStats
        """
        return dict(self._provider_stats)
    
    def get_recent_requests(self, provider: str, model: str, 
                          since: Optional[datetime] = None, limit: int = 100) -> List[LLMRequestMetrics]:
        """Get recent requests for a provider/model.
        
        Args:
            provider: Provider name
            model: Model name
            since: Optional timestamp to filter from
            limit: Maximum number of requests to return
            
        Returns:
            List of recent LLMRequestMetrics
        """
        key = f"{provider}/{model}"
        
        if key not in self._request_history:
            return []
        
        requests = list(self._request_history[key])
        
        # Filter by timestamp if provided
        if since:
            requests = [r for r in requests if r.start_time >= since]
        
        # Sort by start time (most recent first) and limit
        requests.sort(key=lambda r: r.start_time, reverse=True)
        return requests[:limit]
    
    def get_performance_report(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate comprehensive LLM performance report.
        
        Args:
            since: Optional timestamp to filter metrics from
            
        Returns:
            Dictionary containing performance report
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "providers": {},
            "summary": {
                "total_providers": 0,
                "total_requests": 0,
                "overall_success_rate": 0.0,
                "overall_error_rate": 0.0,
                "avg_response_time": 0.0
            },
            "alerts": []
        }
        
        total_requests = 0
        total_successful = 0
        total_duration = 0.0
        
        # Generate report for each provider
        for key, stats in self._provider_stats.items():
            # Filter by time if specified
            if since and stats.last_request_time and stats.last_request_time < since:
                continue
            
            provider_report = {
                "provider": stats.provider,
                "model": stats.model,
                "total_requests": stats.total_requests,
                "success_rate": stats.success_rate,
                "error_rate": stats.error_rate,
                "avg_duration": stats.avg_duration,
                "tokens_per_second": stats.tokens_per_second,
                "total_retries": stats.total_retries,
                "last_request": stats.last_request_time.isoformat() if stats.last_request_time else None,
                "recent_errors": stats.recent_errors[-3:],  # Last 3 errors
                "status_breakdown": {
                    "successful": stats.successful_requests,
                    "failed": stats.failed_requests,
                    "timeout": stats.timeout_requests,
                    "rate_limited": stats.rate_limited_requests,
                    "auth_error": stats.auth_error_requests,
                    "invalid_response": stats.invalid_response_requests
                }
            }
            
            # Check for performance issues
            alerts = []
            if stats.success_rate < 0.95 and stats.total_requests > 10:
                alerts.append(f"Low success rate: {stats.success_rate:.2%}")
            
            if stats.avg_duration > 30.0:
                alerts.append(f"High average response time: {stats.avg_duration:.1f}s")
            
            if stats.rate_limited_requests > stats.total_requests * 0.1:
                alerts.append("High rate limiting frequency")
            
            provider_report["alerts"] = alerts
            report["alerts"].extend([f"{key}: {alert}" for alert in alerts])
            
            report["providers"][key] = provider_report
            
            # Aggregate for summary
            total_requests += stats.total_requests
            total_successful += stats.successful_requests
            total_duration += stats.total_duration
        
        # Calculate overall summary
        report["summary"]["total_providers"] = len(report["providers"])
        report["summary"]["total_requests"] = total_requests
        
        if total_requests > 0:
            report["summary"]["overall_success_rate"] = total_successful / total_requests
            report["summary"]["overall_error_rate"] = (total_requests - total_successful) / total_requests
            report["summary"]["avg_response_time"] = total_duration / total_requests
        
        return report
    
    def clear_history(self, provider: Optional[str] = None, model: Optional[str] = None):
        """Clear request history and statistics.
        
        Args:
            provider: Optional provider to clear (if None, clears all)
            model: Optional model to clear (requires provider)
        """
        if provider and model:
            key = f"{provider}/{model}"
            if key in self._request_history:
                self._request_history[key].clear()
            if key in self._provider_stats:
                del self._provider_stats[key]
        elif provider:
            # Clear all models for this provider
            keys_to_remove = [key for key in self._request_history.keys() if key.startswith(f"{provider}/")]
            for key in keys_to_remove:
                self._request_history[key].clear()
                if key in self._provider_stats:
                    del self._provider_stats[key]
        else:
            # Clear everything
            self._request_history.clear()
            self._provider_stats.clear()
        
        self.logger.info(f"Cleared LLM monitoring history for {provider or 'all providers'}")
    
    def _update_provider_stats(self, request_metrics: LLMRequestMetrics):
        """Update provider statistics with completed request.
        
        Args:
            request_metrics: Completed request metrics
        """
        key = f"{request_metrics.provider}/{request_metrics.model}"
        
        if key not in self._provider_stats:
            self._provider_stats[key] = LLMProviderStats(
                provider=request_metrics.provider,
                model=request_metrics.model
            )
        
        stats = self._provider_stats[key]
        
        # Update counters
        stats.total_requests += 1
        stats.last_request_time = request_metrics.end_time
        
        if request_metrics.status == LLMRequestStatus.SUCCESS:
            stats.successful_requests += 1
        else:
            stats.failed_requests += 1
            
            # Track specific error types
            if request_metrics.status == LLMRequestStatus.TIMEOUT:
                stats.timeout_requests += 1
            elif request_metrics.status == LLMRequestStatus.RATE_LIMITED:
                stats.rate_limited_requests += 1
            elif request_metrics.status == LLMRequestStatus.AUTHENTICATION_ERROR:
                stats.auth_error_requests += 1
            elif request_metrics.status == LLMRequestStatus.INVALID_RESPONSE:
                stats.invalid_response_requests += 1
            
            # Keep recent error messages
            if request_metrics.error_message:
                stats.recent_errors.append(request_metrics.error_message)
                if len(stats.recent_errors) > 10:
                    stats.recent_errors = stats.recent_errors[-10:]
        
        # Update timing and token stats
        if request_metrics.duration_seconds:
            stats.total_duration += request_metrics.duration_seconds
        
        if request_metrics.total_tokens:
            stats.total_tokens += request_metrics.total_tokens
        
        if request_metrics.prompt_tokens:
            stats.total_prompt_tokens += request_metrics.prompt_tokens
        
        if request_metrics.completion_tokens:
            stats.total_completion_tokens += request_metrics.completion_tokens
        
        stats.total_retries += request_metrics.retry_count
        
        # Calculate derived metrics
        if stats.total_requests > 0:
            stats.success_rate = stats.successful_requests / stats.total_requests
            stats.error_rate = stats.failed_requests / stats.total_requests
            stats.avg_duration = stats.total_duration / stats.total_requests
            
            if stats.total_duration > 0:
                stats.tokens_per_second = stats.total_tokens / stats.total_duration


class LLMRequestTracker:
    """Context manager for tracking LLM requests."""
    
    def __init__(self, monitor: LLMPerformanceMonitor, provider: str, model: str, 
                 request_id: str, prompt_tokens: Optional[int] = None):
        """Initialize request tracker.
        
        Args:
            monitor: LLMPerformanceMonitor instance
            provider: LLM provider name
            model: Model name
            request_id: Unique request identifier
            prompt_tokens: Number of prompt tokens
        """
        self.monitor = monitor
        self.provider = provider
        self.model = model
        self.request_id = request_id
        self.prompt_tokens = prompt_tokens
        self.request_metrics = None
    
    def __enter__(self):
        """Start tracking the request."""
        self.request_metrics = self.monitor.start_request(
            self.provider, self.model, self.request_id, self.prompt_tokens
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete tracking the request."""
        if exc_type is None:
            # Success case
            self.monitor.complete_request(self.request_id, LLMRequestStatus.SUCCESS)
        else:
            # Error case - determine error type
            error_message = str(exc_val) if exc_val else "Unknown error"
            
            if "timeout" in error_message.lower():
                status = LLMRequestStatus.TIMEOUT
            elif "rate limit" in error_message.lower() or "429" in error_message:
                status = LLMRequestStatus.RATE_LIMITED
            elif "auth" in error_message.lower() or "401" in error_message or "403" in error_message:
                status = LLMRequestStatus.AUTHENTICATION_ERROR
            elif "invalid" in error_message.lower() or "malformed" in error_message.lower():
                status = LLMRequestStatus.INVALID_RESPONSE
            else:
                status = LLMRequestStatus.ERROR
            
            self.monitor.complete_request(self.request_id, status, error_message=error_message)
    
    def set_completion_tokens(self, tokens: int):
        """Set the number of completion tokens for this request.
        
        Args:
            tokens: Number of completion tokens
        """
        if self.request_metrics:
            self.request_metrics.completion_tokens = tokens
    
    def set_retry_count(self, count: int):
        """Set the retry count for this request.
        
        Args:
            count: Number of retries performed
        """
        if self.request_metrics:
            self.request_metrics.retry_count = count
    
    def set_rate_limit_delay(self, delay: float):
        """Set the total rate limit delay for this request.
        
        Args:
            delay: Total delay in seconds due to rate limiting
        """
        if self.request_metrics:
            self.request_metrics.rate_limit_delay = delay


# Global LLM performance monitor instance
_global_llm_monitor: Optional[LLMPerformanceMonitor] = None


def get_llm_monitor() -> LLMPerformanceMonitor:
    """Get the global LLM performance monitor instance."""
    global _global_llm_monitor
    
    if _global_llm_monitor is None:
        _global_llm_monitor = LLMPerformanceMonitor()
    
    return _global_llm_monitor


def track_llm_request(provider: str, model: str, request_id: str, 
                     prompt_tokens: Optional[int] = None) -> LLMRequestTracker:
    """Create a context manager for tracking an LLM request.
    
    Args:
        provider: LLM provider name
        model: Model name
        request_id: Unique request identifier
        prompt_tokens: Number of prompt tokens
        
    Returns:
        LLMRequestTracker context manager
    """
    return LLMRequestTracker(get_llm_monitor(), provider, model, request_id, prompt_tokens)