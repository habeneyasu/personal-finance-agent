"""
Centralized metrics tracking system for PFIP application.
Supports time-series data, cost tracking, token usage, and latency monitoring.
"""
import os
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of metrics to track."""
    COST = "cost"
    TOKENS = "tokens"
    LATENCY = "latency"
    REQUESTS = "requests"
    ERRORS = "errors"
    ACCURACY = "accuracy"

@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime
    user_id: str
    agent_name: str
    metric_type: str
    value: float
    unit: str
    metadata: Dict[str, Any] = None

class MetricsTracker:
    """Centralized metrics tracking and aggregation system."""
    
    def __init__(self):
        self.metrics: List[MetricPoint] = []
        self.session_id = str(int(time.time()))
        
    def track_metric(self, user_id: str, agent_name: str, metric_type: str,
                     value: float, unit: str, metadata: Dict[str, Any] = None):
        """Track a single metric point."""
        metric = MetricPoint(
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            agent_name=agent_name,
            metric_type=metric_type,
            value=value,
            unit=unit,
            metadata=metadata or {}
        )
        self.metrics.append(metric)
        
        # Keep only last 10000 metrics to prevent memory issues
        if len(self.metrics) > 10000:
            self.metrics = self.metrics[-10000:]
    
    def track_cost(self, user_id: str, agent_name: str, cost: float, metadata: Dict[str, Any] = None):
        """Track cost metric."""
        self.track_metric(user_id, agent_name, MetricType.COST.value, cost, "dollars", metadata)
    
    def track_tokens(self, user_id: str, agent_name: str, tokens: int, metadata: Dict[str, Any] = None):
        """Track token usage metric."""
        self.track_metric(user_id, agent_name, MetricType.TOKENS.value, tokens, "count", metadata)
    
    def track_latency(self, user_id: str, agent_name: str, latency_ms: float,
                     operation: str = None, component: str = None):
        """Track latency metric."""
        metadata = {}
        if operation:
            metadata["operation"] = operation
        if component:
            metadata["component"] = component
        self.track_metric(user_id, agent_name, MetricType.LATENCY.value, latency_ms, "milliseconds", metadata)
    
    def track_request(self, user_id: str, agent_name: str, success: bool = True,
                     error_type: str = None, request_type: str = None, 
                     fallback_used: bool = False, retry_count: int = 0):
        """Track request count and success/failure with detailed error tracking."""
        metadata = {
            "success": success,
            "request_type": request_type,
            "retry_count": retry_count,
            "fallback_used": fallback_used
        }
        if error_type:
            metadata["error_type"] = error_type
        
        if success:
            self.track_metric(user_id, agent_name, "requests", 1, "count", metadata)
            if fallback_used:
                self.track_metric(user_id, agent_name, "fallbacks", 1, "count", metadata)
        else:
            self.track_metric(user_id, agent_name, "errors", 1, "count", metadata)
            if error_type:
                self.track_metric(user_id, agent_name, f"error_{error_type}", 1, "count", metadata)
    
    def track_fallback(self, user_id: str, agent_name: str, fallback_reason: str,
                      original_error: str = None, fallback_type: str = "local"):
        """Track fallback usage when primary systems fail."""
        metadata = {
            "fallback_reason": fallback_reason,
            "fallback_type": fallback_type
        }
        if original_error:
            metadata["original_error"] = original_error
        
        self.track_metric(user_id, agent_name, "fallbacks", 1, "count", metadata)
    
    def track_retry(self, user_id: str, agent_name: str, retry_count: int,
                   success: bool = False, final_error: str = None):
        """Track retry attempts and outcomes."""
        metadata = {
            "retry_count": retry_count,
            "success": success
        }
        if final_error:
            metadata["final_error"] = final_error
        
        self.track_metric(user_id, agent_name, "retries", retry_count, "count", metadata)
        if not success:
            self.track_metric(user_id, agent_name, "failed_retries", 1, "count", metadata)
    
    def get_time_series(self, 
                       user_id: str = None,
                       agent_name: str = None,
                       metric_type: str = None,
                       start_time: datetime = None,
                       end_time: datetime = None,
                       interval: str = "hour") -> List[Dict]:
        """Get time-series data for metrics."""
        # Filter metrics based on criteria
        filtered_metrics = self.metrics.copy()
        
        if user_id:
            filtered_metrics = [m for m in filtered_metrics if m.user_id == user_id]
        
        if agent_name:
            filtered_metrics = [m for m in filtered_metrics if m.agent_name == agent_name]
        
        if metric_type:
            filtered_metrics = [m for m in filtered_metrics if m.metric_type == metric_type]
        
        if start_time:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp >= start_time]
        
        if end_time:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp <= end_time]
        
        # Group by time intervals
        time_buckets = self._create_time_buckets(start_time or datetime.now(timezone.utc) - timedelta(hours=24),
                                               end_time or datetime.now(timezone.utc),
                                               interval)
        
        series_data = []
        for bucket_start, bucket_end in time_buckets:
            bucket_metrics = [m for m in filtered_metrics 
                            if bucket_start <= m.timestamp < bucket_end]
            
            if bucket_metrics:
                if metric_type in ["cost", "tokens", "latency"]:
                    # Sum these metrics
                    total_value = sum(m.value for m in bucket_metrics)
                    avg_value = total_value / len(bucket_metrics)
                else:
                    # Count these metrics
                    total_value = len(bucket_metrics)
                    avg_value = total_value
                
                series_data.append({
                    "timestamp": bucket_start.isoformat(),
                    "value": total_value,
                    "average": avg_value,
                    "count": len(bucket_metrics)
                })
        
        return series_data
    
    def get_agent_breakdown(self, user_id: str = None, period_hours: int = 24) -> Dict[str, Any]:
        """Get metrics breakdown by agent."""
        start_time = datetime.now(timezone.utc) - timedelta(hours=period_hours)
        end_time = datetime.now(timezone.utc)
        
        # Filter metrics for the time period
        recent_metrics = [m for m in self.metrics 
                         if start_time <= m.timestamp <= end_time]
        
        if user_id:
            recent_metrics = [m for m in recent_metrics if m.user_id == user_id]
        
        # Group by agent
        agent_data = {}
        for metric in recent_metrics:
            if metric.agent_name not in agent_data:
                agent_data[metric.agent_name] = {
                    "requests": 0,
                    "errors": 0,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "avg_latency": 0.0,
                    "latency_count": 0
                }
            
            agent = agent_data[metric.agent_name]
            
            if metric.metric_type == "requests":
                agent["requests"] += int(metric.value)
            elif metric.metric_type == "errors":
                agent["errors"] += int(metric.value)
            elif metric.metric_type == "cost":
                agent["total_cost"] += metric.value
            elif metric.metric_type == "tokens":
                agent["total_tokens"] += int(metric.value)
            elif metric.metric_type == "latency":
                agent["avg_latency"] = (agent["avg_latency"] * agent["latency_count"] + metric.value) / (agent["latency_count"] + 1)
                agent["latency_count"] += 1
        
        return agent_data
    
    def get_summary_stats(self, user_id: str = None, agent_name: str = None,
                         period_hours: int = 24) -> Dict[str, Any]:
        """Get summary statistics for metrics."""
        start_time = datetime.now(timezone.utc) - timedelta(hours=period_hours)
        end_time = datetime.now(timezone.utc)
        
        # Filter metrics
        filtered_metrics = [m for m in self.metrics 
                           if start_time <= m.timestamp <= end_time]
        
        if user_id:
            filtered_metrics = [m for m in filtered_metrics if m.user_id == user_id]
        
        if agent_name:
            filtered_metrics = [m for m in filtered_metrics if m.agent_name == agent_name]
        
        # Calculate summary stats
        stats = {
            "total_requests": 0,
            "total_errors": 0,
            "total_cost": 0.0,
            "total_tokens": 0,
            "avg_latency": 0.0,
            "error_rate": 0.0,
            "period_hours": period_hours
        }
        
        requests = [m for m in filtered_metrics if m.metric_type == "requests"]
        errors = [m for m in filtered_metrics if m.metric_type == "errors"]
        costs = [m for m in filtered_metrics if m.metric_type == "cost"]
        tokens = [m for m in filtered_metrics if m.metric_type == "tokens"]
        latencies = [m for m in filtered_metrics if m.metric_type == "latency"]
        
        if requests:
            stats["total_requests"] = sum(int(r.value) for r in requests)
        
        if errors:
            stats["total_errors"] = sum(int(e.value) for e in errors)
        
        if costs:
            stats["total_cost"] = sum(c.value for c in costs)
        
        if tokens:
            stats["total_tokens"] = sum(int(t.value) for t in tokens)
        
        if latencies:
            stats["avg_latency"] = sum(l.value for l in latencies) / len(latencies)
        
        if stats["total_requests"] > 0:
            stats["error_rate"] = stats["total_errors"] / stats["total_requests"]
        
        return stats
    
    def _create_time_buckets(self, start_time: datetime, end_time: datetime,
                           interval: str) -> List[tuple]:
        """Create time buckets for time-series aggregation."""
        buckets = []
        current = start_time
        
        if interval == "minute":
            delta = timedelta(minutes=1)
        elif interval == "hour":
            delta = timedelta(hours=1)
        elif interval == "day":
            delta = timedelta(days=1)
        else:
            delta = timedelta(hours=1)
        
        while current < end_time:
            buckets.append((current, current + delta))
            current += delta
        
        return buckets

# Global metrics tracker instance
metrics_tracker = MetricsTracker()

# Decorator for automatic metrics tracking
def track_metrics(agent_name: str, 
                 track_cost: bool = True,
                 track_tokens: bool = True,
                 track_latency: bool = True):
    """Decorator to automatically track metrics for agent functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            user_id = None
            
            # Extract user_id from request if available
            if args and hasattr(args[0], 'scope'):
                # FastAPI Request object
                request = args[0]
                event = request.scope.get("aws.event", {})
                try:
                    from src.shared.auth import get_user_id_from_event
                    user_id = get_user_id_from_event(event)
                except:
                    user_id = 'anonymous'
            else:
                user_id = kwargs.get('user_id') or 'anonymous'
            
            try:
                result = await func(*args, **kwargs)
                
                # Track successful request
                metrics_tracker.track_request(user_id, agent_name, success=True)
                
                # Track latency
                if track_latency:
                    latency_ms = (time.time() - start_time) * 1000
                    metrics_tracker.track_latency(user_id, agent_name, latency_ms)
                
                # Extract metrics from result if available
                if hasattr(result, 'content') and isinstance(result.content, dict):
                    if track_cost and 'cost' in result.content:
                        metrics_tracker.track_cost(user_id, agent_name, result.content['cost'])
                    if track_tokens and 'tokens' in result.content:
                        metrics_tracker.track_tokens(user_id, agent_name, result.content['tokens'])
                
                return result
                
            except Exception as e:
                # Track failed request
                metrics_tracker.track_request(user_id, agent_name, success=False, 
                                            error_type=type(e).__name__)
                
                # Track latency even for failures
                if track_latency:
                    latency_ms = (time.time() - start_time) * 1000
                    metrics_tracker.track_latency(user_id, agent_name, latency_ms)
                
                raise
        
        return wrapper
    return decorator
