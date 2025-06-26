"""
HTTP Connection Pool Manager

Optimized connection pooling for Groq API calls with persistent connections,
intelligent retry logic, and connection health monitoring.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolConfig:
    """Configuration for connection pooling"""
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0
    pool_timeout: float = 5.0
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    write_timeout: float = 10.0
    max_redirects: int = 3
    http2: bool = True
    verify_ssl: bool = True
    
    # Health monitoring
    health_check_interval: float = 60.0
    max_idle_time: float = 300.0
    connection_reuse_threshold: int = 100


class ConnectionHealthMonitor:
    """Monitor connection pool health and performance"""
    
    def __init__(self):
        self.connection_stats: Dict[str, Dict[str, Any]] = {}
        self.pool_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "idle_connections": 0,
            "failed_connections": 0,
            "connection_reuses": 0,
            "average_connection_time": 0.0,
            "last_health_check": 0.0
        }
    
    def record_connection_attempt(self, host: str) -> None:
        """Record connection attempt"""
        if host not in self.connection_stats:
            self.connection_stats[host] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "total_time": 0.0,
                "last_used": 0.0,
                "reuse_count": 0
            }
        
        self.connection_stats[host]["attempts"] += 1
        self.connection_stats[host]["last_used"] = time.time()
    
    def record_connection_success(self, host: str, connection_time: float) -> None:
        """Record successful connection"""
        if host in self.connection_stats:
            stats = self.connection_stats[host]
            stats["successes"] += 1
            stats["total_time"] += connection_time
            stats["reuse_count"] += 1
            
            # Update pool stats
            self.pool_stats["connection_reuses"] += 1
            self._update_average_connection_time(connection_time)
    
    def record_connection_failure(self, host: str) -> None:
        """Record connection failure"""
        if host in self.connection_stats:
            self.connection_stats[host]["failures"] += 1
        
        self.pool_stats["failed_connections"] += 1
    
    def _update_average_connection_time(self, connection_time: float) -> None:
        """Update rolling average connection time"""
        current_avg = self.pool_stats["average_connection_time"]
        if current_avg == 0.0:
            self.pool_stats["average_connection_time"] = connection_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.pool_stats["average_connection_time"] = (
                alpha * connection_time + (1 - alpha) * current_avg
            )
    
    def get_host_stats(self, host: str) -> Dict[str, Any]:
        """Get statistics for specific host"""
        if host not in self.connection_stats:
            return {}
        
        stats = self.connection_stats[host].copy()
        
        # Calculate derived metrics
        if stats["attempts"] > 0:
            stats["success_rate"] = stats["successes"] / stats["attempts"] * 100
        else:
            stats["success_rate"] = 0.0
        
        if stats["successes"] > 0:
            stats["average_connection_time"] = stats["total_time"] / stats["successes"]
        else:
            stats["average_connection_time"] = 0.0
        
        stats["idle_time"] = time.time() - stats["last_used"]
        
        return stats
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get overall pool statistics"""
        return self.pool_stats.copy()
    
    def should_recycle_connection(self, host: str, config: ConnectionPoolConfig) -> bool:
        """Determine if connection should be recycled"""
        stats = self.get_host_stats(host)
        
        if not stats:
            return False
        
        # Recycle if too many reuses
        if stats["reuse_count"] >= config.connection_reuse_threshold:
            return True
        
        # Recycle if idle too long
        if stats["idle_time"] > config.max_idle_time:
            return True
        
        # Recycle if poor success rate
        if stats["attempts"] > 10 and stats["success_rate"] < 80:
            return True
        
        return False


class OptimizedConnectionPool:
    """Optimized HTTP connection pool for Groq API"""
    
    def __init__(self, config: ConnectionPoolConfig):
        self.config = config
        self.monitor = ConnectionHealthMonitor()
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._closed = False
    
    async def _create_client(self) -> httpx.AsyncClient:
        """Create HTTP client with optimized settings"""
        limits = httpx.Limits(
            max_connections=self.config.max_connections,
            max_keepalive_connections=self.config.max_keepalive_connections,
            keepalive_expiry=self.config.keepalive_expiry
        )
        
        timeout = httpx.Timeout(
            connect=self.config.connect_timeout,
            read=self.config.read_timeout,
            write=self.config.write_timeout,
            pool=self.config.pool_timeout
        )
        
        # Optimized transport configuration
        transport = httpx.AsyncHTTPTransport(
            limits=limits,
            http2=self.config.http2,
            verify=self.config.verify_ssl,
            retries=0,  # We handle retries at higher level
        )
        
        client = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            max_redirects=self.config.max_redirects,
            follow_redirects=True
        )
        
        logger.info(f"Created HTTP client with {self.config.max_connections} max connections")
        return client
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client thread-safely"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        async with self._client_lock:
            if self._client is None:
                self._client = await self._create_client()
                
                # Start health monitoring
                if self._health_check_task is None:
                    self._health_check_task = asyncio.create_task(
                        self._health_check_loop()
                    )
        
        return self._client
    
    async def _health_check_loop(self) -> None:
        """Background health monitoring loop"""
        while not self._closed:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Health check error: {e}")
    
    async def _perform_health_check(self) -> None:
        """Perform connection pool health check"""
        if self._client is None:
            return
        
        # Update pool statistics
        pool_info = self._client._transport._pool._pool_for_request
        if hasattr(pool_info, '_connections'):
            self.monitor.pool_stats["active_connections"] = len(
                [c for c in pool_info._connections if c.is_connection_dropped()]
            )
        
        self.monitor.pool_stats["last_health_check"] = time.time()
        
        # Check for connections that should be recycled
        for host in list(self.monitor.connection_stats.keys()):
            if self.monitor.should_recycle_connection(host, self.config):
                logger.debug(f"Recycling connection pool for {host}")
                # Force connection recycling by closing and recreating client
                await self._recycle_connections()
                break
    
    async def _recycle_connections(self) -> None:
        """Recycle connection pool"""
        async with self._client_lock:
            if self._client:
                await self._client.aclose()
                self._client = None
                logger.info("Connection pool recycled")
    
    @asynccontextmanager
    async def request(self, method: str, url: str, **kwargs) -> AsyncIterator[httpx.Response]:
        """Make HTTP request with connection pooling and monitoring"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        client = await self._get_client()
        host = httpx.URL(url).host
        
        # Record connection attempt
        self.monitor.record_connection_attempt(host)
        
        start_time = time.time()
        try:
            async with client.stream(method, url, **kwargs) as response:
                connection_time = time.time() - start_time
                self.monitor.record_connection_success(host, connection_time)
                yield response
                
        except Exception as e:
            self.monitor.record_connection_failure(host)
            raise
    
    async def post_multipart(self, url: str, files: Dict[str, Any], 
                           data: Optional[Dict[str, Any]] = None,
                           headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """Optimized multipart POST for file uploads"""
        async with self.request("POST", url, files=files, data=data, headers=headers) as response:
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=await response.aread(),
                request=response.request
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            "pool_stats": self.monitor.get_pool_stats(),
            "host_stats": {
                host: self.monitor.get_host_stats(host)
                for host in self.monitor.connection_stats.keys()
            },
            "config": {
                "max_connections": self.config.max_connections,
                "max_keepalive": self.config.max_keepalive_connections,
                "http2_enabled": self.config.http2,
                "keepalive_expiry": self.config.keepalive_expiry
            }
        }
    
    async def close(self) -> None:
        """Close connection pool"""
        self._closed = True
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close HTTP client
        async with self._client_lock:
            if self._client:
                await self._client.aclose()
                self._client = None
        
        logger.info("Connection pool closed")


# Global connection pool instance
_global_pool: Optional[OptimizedConnectionPool] = None
_pool_lock = asyncio.Lock()


async def get_global_pool(config: Optional[ConnectionPoolConfig] = None) -> OptimizedConnectionPool:
    """Get or create global connection pool"""
    global _global_pool
    
    if config is None:
        config = ConnectionPoolConfig()
    
    async with _pool_lock:
        if _global_pool is None or _global_pool._closed:
            _global_pool = OptimizedConnectionPool(config)
    
    return _global_pool


async def close_global_pool() -> None:
    """Close global connection pool"""
    global _global_pool
    
    async with _pool_lock:
        if _global_pool:
            await _global_pool.close()
            _global_pool = None


# Convenience functions for common use cases
@asynccontextmanager
async def optimized_request(method: str, url: str, **kwargs) -> AsyncIterator[httpx.Response]:
    """Make optimized HTTP request using global pool"""
    pool = await get_global_pool()
    async with pool.request(method, url, **kwargs) as response:
        yield response


async def optimized_post_multipart(url: str, files: Dict[str, Any], 
                                 data: Optional[Dict[str, Any]] = None,
                                 headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    """Optimized multipart POST using global pool"""
    pool = await get_global_pool()
    return await pool.post_multipart(url, files, data, headers)


def get_pool_stats() -> Dict[str, Any]:
    """Get global pool statistics"""
    if _global_pool:
        return _global_pool.get_stats()
    return {"error": "No active connection pool"}


# Configuration presets for different use cases
GROQ_OPTIMIZED_CONFIG = ConnectionPoolConfig(
    max_connections=50,          # Conservative for API limits
    max_keepalive_connections=10, # Keep connections alive for reuse
    keepalive_expiry=30.0,       # 30 second keepalive
    connect_timeout=15.0,        # Generous connection timeout
    read_timeout=300.0,          # 5 minutes for large transcriptions
    write_timeout=60.0,          # 1 minute for uploads
    http2=True,                  # Enable HTTP/2 for multiplexing
    health_check_interval=30.0,  # Check health every 30s
    max_idle_time=180.0,         # Recycle after 3 minutes idle
    connection_reuse_threshold=50 # Recycle after 50 reuses
)

HIGH_THROUGHPUT_CONFIG = ConnectionPoolConfig(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=60.0,
    connect_timeout=10.0,
    read_timeout=120.0,
    write_timeout=30.0,
    http2=True,
    health_check_interval=60.0,
    max_idle_time=300.0,
    connection_reuse_threshold=100
)

CONSERVATIVE_CONFIG = ConnectionPoolConfig(
    max_connections=20,
    max_keepalive_connections=5,
    keepalive_expiry=15.0,
    connect_timeout=30.0,
    read_timeout=600.0,
    write_timeout=120.0,
    http2=False,  # Disable HTTP/2 for maximum compatibility
    health_check_interval=120.0,
    max_idle_time=120.0,
    connection_reuse_threshold=25
)