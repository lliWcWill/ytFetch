"""
Advanced Rate Limiting Module for Groq Dev Tier

This module provides sophisticated rate limiting strategies optimized for Groq's dev tier
with circuit breaker patterns, connection pooling, and loop prevention mechanisms.

Features:
- Circuit breaker patterns for 503 error handling
- Exponential backoff with jitter
- Request deduplication and tracking
- HTTP session pooling with httpx
- Intelligent cooldown periods
- Connection limits and timeouts
"""

import asyncio
import hashlib
import logging
import random
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    rpm: int = 400                    # Requests per minute
    burst_size: int = 10              # Burst allowance
    safety_factor: float = 0.8        # Safety margin (0.8 = 80% of limit)
    max_retries: int = 5              # Maximum retry attempts
    base_backoff: float = 1.0         # Base backoff delay
    max_backoff: float = 300.0        # Maximum backoff delay
    jitter_factor: float = 0.1        # Jitter randomization factor
    
    # Circuit breaker settings
    failure_threshold: int = 5        # Failures before opening circuit
    recovery_timeout: float = 60.0    # Time before half-open attempt
    success_threshold: int = 3        # Successes to close circuit
    
    # Connection pooling
    max_connections: int = 100        # Max total connections
    max_keepalive: int = 20          # Max keepalive connections
    timeout: float = 30.0            # Request timeout


@dataclass
class RequestMetrics:
    """Track request metrics for monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    circuit_breaker_blocks: int = 0
    deduplicated_requests: int = 0
    average_response_time: float = 0.0
    
    def update_response_time(self, response_time: float) -> None:
        """Update rolling average response time"""
        if self.successful_requests == 0:
            self.average_response_time = response_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.average_response_time = (
                alpha * response_time + (1 - alpha) * self.average_response_time
            )


class CircuitBreaker:
    """Circuit breaker for handling service failures"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.next_attempt_time = 0.0
        
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        
        elif self.state == CircuitState.OPEN:
            if current_time >= self.next_attempt_time:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False
        
        elif self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self) -> None:
        """Record successful request"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker CLOSED - service recovered")
        
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self, error: Exception) -> None:
        """Record failed request"""
        self.last_failure_time = time.time()
        self.failure_count += 1
        
        # Check if should open circuit (for 503 errors or too many failures)
        is_service_error = (
            "503" in str(error) or 
            "Service Unavailable" in str(error) or
            "rate limit" in str(error).lower()
        )
        
        if (self.failure_count >= self.config.failure_threshold or 
            (is_service_error and self.failure_count >= 2)):
            
            self.state = CircuitState.OPEN
            self.next_attempt_time = (
                self.last_failure_time + self.config.recovery_timeout
            )
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures. "
                f"Next attempt at {time.ctime(self.next_attempt_time)}"
            )


class RequestTracker:
    """Track and deduplicate requests"""
    
    def __init__(self, ttl: float = 300.0):  # 5 minute TTL
        self.ttl = ttl
        self.active_requests: Set[str] = set()
        self.request_history: deque = deque()
        self.request_times: Dict[str, float] = {}
        
    def _cleanup_expired(self) -> None:
        """Remove expired request tracking"""
        current_time = time.time()
        
        # Clean up history
        while (self.request_history and 
               current_time - self.request_history[0][1] > self.ttl):
            request_id, _ = self.request_history.popleft()
            self.active_requests.discard(request_id)
            self.request_times.pop(request_id, None)
    
    def generate_request_id(self, **kwargs) -> str:
        """Generate unique request ID for deduplication"""
        # Create hash from request parameters
        key_data = f"{kwargs.get('file_path', '')}{kwargs.get('model', '')}{kwargs.get('language', '')}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def is_duplicate(self, request_id: str) -> bool:
        """Check if request is duplicate"""
        self._cleanup_expired()
        return request_id in self.active_requests
    
    def track_request(self, request_id: str) -> None:
        """Start tracking a request"""
        current_time = time.time()
        self.active_requests.add(request_id)
        self.request_history.append((request_id, current_time))
        self.request_times[request_id] = current_time
    
    def complete_request(self, request_id: str) -> None:
        """Mark request as complete"""
        self.active_requests.discard(request_id)


class AdvancedRateLimiter:
    """Advanced rate limiter with circuit breaker and connection pooling"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.circuit_breaker = CircuitBreaker(config)
        self.request_tracker = RequestTracker()
        self.metrics = RequestMetrics()
        
        # Rate limiting state
        self.request_times: deque = deque()
        self.effective_rpm = int(config.rpm * config.safety_factor)
        
        # Backoff state
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.cooldown_until = 0.0
        
        # HTTP client with connection pooling
        self.client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"Rate limiter initialized: {self.effective_rpm} effective RPM")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling"""
        if self.client is None:
            limits = httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_keepalive
            )
            
            timeout = httpx.Timeout(
                connect=10.0,
                read=self.config.timeout,
                write=10.0,
                pool=5.0
            )
            
            self.client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                http2=True,  # Enable HTTP/2 for better multiplexing
                verify=True
            )
            
        return self.client
    
    async def close(self) -> None:
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff delay with exponential backoff and jitter"""
        base_delay = min(
            self.config.base_backoff * (2 ** attempt),
            self.config.max_backoff
        )
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(
            -self.config.jitter_factor * base_delay,
            self.config.jitter_factor * base_delay
        )
        
        return max(0.1, base_delay + jitter)
    
    def _should_wait_for_rate_limit(self) -> Tuple[bool, float]:
        """Check if should wait for rate limiting"""
        current_time = time.time()
        
        # Remove old requests
        while (self.request_times and 
               current_time - self.request_times[0] >= 60.0):
            self.request_times.popleft()
        
        # Check if we're at the limit
        if len(self.request_times) >= self.effective_rpm:
            # Calculate wait time
            oldest_request = self.request_times[0]
            wait_time = 60.0 - (current_time - oldest_request) + 0.1
            return True, max(0.1, wait_time)
        
        return False, 0.0
    
    def _should_wait_for_cooldown(self) -> Tuple[bool, float]:
        """Check if in cooldown period"""
        current_time = time.time()
        
        if current_time < self.cooldown_until:
            return True, self.cooldown_until - current_time
        
        return False, 0.0
    
    async def _wait_with_backoff(self, delay: float) -> None:
        """Wait with proper async handling"""
        if delay > 0:
            logger.debug(f"Waiting {delay:.2f}s for rate limiting")
            await asyncio.sleep(delay)
    
    def _record_request_start(self) -> None:
        """Record request start for rate limiting"""
        current_time = time.time()
        self.request_times.append(current_time)
        self.metrics.total_requests += 1
    
    def _record_request_success(self, response_time: float) -> None:
        """Record successful request"""
        self.metrics.successful_requests += 1
        self.metrics.update_response_time(response_time)
        self.circuit_breaker.record_success()
        self.consecutive_failures = 0
        self.cooldown_until = 0.0
    
    def _record_request_failure(self, error: Exception) -> None:
        """Record failed request and update backoff"""
        self.metrics.failed_requests += 1
        self.circuit_breaker.record_failure(error)
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        
        # Set cooldown for repeated failures
        if self.consecutive_failures >= 3:
            cooldown_delay = self._calculate_backoff(self.consecutive_failures - 3)
            self.cooldown_until = time.time() + cooldown_delay
            logger.warning(f"Multiple failures detected, cooldown until {time.ctime(self.cooldown_until)}")
    
    @asynccontextmanager
    async def rate_limited_request(self, **request_kwargs):
        """Context manager for rate-limited requests"""
        request_id = self.request_tracker.generate_request_id(**request_kwargs)
        
        # Check for duplicate requests
        if self.request_tracker.is_duplicate(request_id):
            self.metrics.deduplicated_requests += 1
            logger.debug(f"Duplicate request blocked: {request_id[:8]}")
            raise ValueError("Duplicate request in progress")
        
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            self.metrics.circuit_breaker_blocks += 1
            logger.warning("Request blocked by circuit breaker")
            raise RuntimeError("Circuit breaker is OPEN")
        
        # Check cooldown
        should_wait_cooldown, cooldown_delay = self._should_wait_for_cooldown()
        if should_wait_cooldown:
            logger.info(f"In cooldown period, waiting {cooldown_delay:.1f}s")
            await self._wait_with_backoff(cooldown_delay)
        
        # Rate limiting
        should_wait_rate, rate_delay = self._should_wait_for_rate_limit()
        if should_wait_rate:
            self.metrics.rate_limited_requests += 1
            await self._wait_with_backoff(rate_delay)
        
        # Track request
        self.request_tracker.track_request(request_id)
        self._record_request_start()
        
        start_time = time.time()
        try:
            yield await self._get_client()
            
            # Record success
            response_time = time.time() - start_time
            self._record_request_success(response_time)
            
        except Exception as e:
            # Record failure
            self._record_request_failure(e)
            raise
        
        finally:
            # Complete request tracking
            self.request_tracker.complete_request(request_id)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": (
                self.metrics.successful_requests / max(1, self.metrics.total_requests) * 100
            ),
            "rate_limited_requests": self.metrics.rate_limited_requests,
            "circuit_breaker_blocks": self.metrics.circuit_breaker_blocks,
            "deduplicated_requests": self.metrics.deduplicated_requests,
            "average_response_time": self.metrics.average_response_time,
            "circuit_state": self.circuit_breaker.state.value,
            "consecutive_failures": self.consecutive_failures,
            "cooldown_active": time.time() < self.cooldown_until,
            "effective_rpm": self.effective_rpm,
            "current_request_count": len(self.request_times)
        }
    
    def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker (for emergency recovery)"""
        self.circuit_breaker.state = CircuitState.CLOSED
        self.circuit_breaker.failure_count = 0
        self.consecutive_failures = 0
        self.cooldown_until = 0.0
        logger.info("Circuit breaker manually reset")


# Predefined configurations for different Groq models
GROQ_DEV_CONFIGS = {
    "whisper-large-v3-turbo": RateLimitConfig(
        rpm=400,
        burst_size=15,
        safety_factor=0.8,
        max_retries=5,
        failure_threshold=3,
        recovery_timeout=60.0
    ),
    "whisper-large-v3": RateLimitConfig(
        rpm=300,
        burst_size=12,
        safety_factor=0.8,
        max_retries=5,
        failure_threshold=3,
        recovery_timeout=45.0
    ),
    "distil-whisper-large-v3-en": RateLimitConfig(
        rpm=100,
        burst_size=5,
        safety_factor=0.7,  # More conservative for lower limit
        max_retries=3,
        failure_threshold=2,
        recovery_timeout=30.0
    )
}


def create_rate_limiter(model: str) -> AdvancedRateLimiter:
    """Create rate limiter for specific Groq model"""
    config = GROQ_DEV_CONFIGS.get(model)
    if not config:
        logger.warning(f"Unknown model {model}, using default config")
        config = GROQ_DEV_CONFIGS["whisper-large-v3"]
    
    return AdvancedRateLimiter(config)


# Utility functions for backward compatibility
class SyncRateLimiter:
    """Synchronous wrapper for backward compatibility"""
    
    def __init__(self, model: str):
        self.model = model
        self.config = GROQ_DEV_CONFIGS.get(model, GROQ_DEV_CONFIGS["whisper-large-v3"])
        self.request_times: deque = deque()
        self.effective_rpm = int(self.config.rpm * self.config.safety_factor)
        self.consecutive_failures = 0
        self.cooldown_until = 0.0
        
    def wait_if_needed(self) -> None:
        """Synchronous rate limiting for backward compatibility"""
        current_time = time.time()
        
        # Check cooldown
        if current_time < self.cooldown_until:
            wait_time = self.cooldown_until - current_time
            logger.info(f"Cooldown wait: {wait_time:.1f}s")
            time.sleep(wait_time)
        
        # Remove old requests
        while (self.request_times and 
               current_time - self.request_times[0] >= 60.0):
            self.request_times.popleft()
        
        # Rate limiting
        if len(self.request_times) >= self.effective_rpm:
            oldest_request = self.request_times[0]
            wait_time = 60.0 - (current_time - oldest_request) + 0.1
            if wait_time > 0:
                logger.debug(f"Rate limit wait: {wait_time:.2f}s")
                time.sleep(wait_time)
        
        self.request_times.append(time.time())
    
    def record_failure(self) -> None:
        """Record failure for cooldown calculation"""
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            cooldown_delay = min(
                self.config.base_backoff * (2 ** (self.consecutive_failures - 3)),
                self.config.max_backoff
            )
            self.cooldown_until = time.time() + cooldown_delay
            logger.warning(f"Setting cooldown: {cooldown_delay:.1f}s")
    
    def record_success(self) -> None:
        """Record success to reset failure counter"""
        self.consecutive_failures = 0
        self.cooldown_until = 0.0