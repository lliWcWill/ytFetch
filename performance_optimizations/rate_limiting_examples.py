"""
Advanced Rate Limiting Examples and Usage Patterns

This module demonstrates how to use the advanced rate limiting system
for optimal Groq dev tier performance with loop prevention.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any

from .advanced_rate_limiter import (
    AdvancedRateLimiter,
    SyncRateLimiter,
    RateLimitConfig,
    GROQ_DEV_CONFIGS,
    create_rate_limiter
)
from .connection_pool_manager import (
    OptimizedConnectionPool,
    GROQ_OPTIMIZED_CONFIG,
    get_global_pool,
    optimized_post_multipart
)
from .enhanced_audio_transcriber import (
    EnhancedAudioTranscriber,
    transcribe_audio_from_file
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RateLimitingDemo:
    """Demonstration of advanced rate limiting patterns"""
    
    def __init__(self):
        self.demo_results = {}
    
    def demo_circuit_breaker_pattern(self) -> Dict[str, Any]:
        """Demonstrate circuit breaker pattern for 503 error handling"""
        logger.info("🔌 Circuit Breaker Pattern Demo")
        
        # Create rate limiter with aggressive settings for demo
        config = RateLimitConfig(
            rpm=100,
            failure_threshold=3,  # Open after 3 failures
            recovery_timeout=30.0,  # 30 second recovery
            success_threshold=2   # Close after 2 successes
        )
        
        rate_limiter = AdvancedRateLimiter(config)
        
        # Simulate failures to trigger circuit breaker
        for i in range(5):
            try:
                # Simulate API call that fails
                rate_limiter.circuit_breaker.record_failure(
                    Exception("503 Service Unavailable")
                )
                logger.info(f"Recorded failure {i+1}")
                
                # Check if circuit is open
                if not rate_limiter.circuit_breaker.can_execute():
                    logger.warning("🚨 Circuit breaker is OPEN - requests blocked")
                    break
                    
            except Exception as e:
                logger.error(f"Error in circuit breaker demo: {e}")
        
        # Show current state
        metrics = rate_limiter.get_metrics()
        logger.info(f"Circuit state: {metrics['circuit_state']}")
        
        return {
            "circuit_state": metrics["circuit_state"],
            "failure_count": rate_limiter.circuit_breaker.failure_count,
            "demo_completed": True
        }
    
    def demo_exponential_backoff(self) -> Dict[str, Any]:
        """Demonstrate exponential backoff with jitter"""
        logger.info("📈 Exponential Backoff Demo")
        
        rate_limiter = SyncRateLimiter("whisper-large-v3-turbo")
        
        backoff_times = []
        
        # Simulate multiple failures
        for attempt in range(5):
            rate_limiter.record_failure()
            
            # Calculate backoff time
            base_delay = 2.0
            backoff_time = min(base_delay * (2 ** attempt), 60.0)
            backoff_times.append(backoff_time)
            
            logger.info(f"Attempt {attempt + 1}: Backoff time = {backoff_time:.2f}s")
            
            # Don't actually sleep in demo
            time.sleep(0.1)
        
        return {
            "backoff_times": backoff_times,
            "max_backoff": max(backoff_times),
            "total_backoff": sum(backoff_times)
        }
    
    def demo_request_deduplication(self) -> Dict[str, Any]:
        """Demonstrate request deduplication"""
        logger.info("🔄 Request Deduplication Demo")
        
        rate_limiter = create_rate_limiter("whisper-large-v3")
        
        # Simulate duplicate requests
        request_params = {
            "file_path": "/tmp/test_audio.wav",
            "model": "whisper-large-v3",
            "language": "en"
        }
        
        request_id = rate_limiter.request_tracker.generate_request_id(**request_params)
        
        # First request
        is_duplicate_1 = rate_limiter.request_tracker.is_duplicate(request_id)
        rate_limiter.request_tracker.track_request(request_id)
        
        # Second request (should be duplicate)
        is_duplicate_2 = rate_limiter.request_tracker.is_duplicate(request_id)
        
        # Complete first request
        rate_limiter.request_tracker.complete_request(request_id)
        
        # Third request (should not be duplicate)
        is_duplicate_3 = rate_limiter.request_tracker.is_duplicate(request_id)
        
        logger.info(f"Request ID: {request_id[:8]}...")
        logger.info(f"First request duplicate: {is_duplicate_1}")
        logger.info(f"Second request duplicate: {is_duplicate_2}")
        logger.info(f"Third request duplicate: {is_duplicate_3}")
        
        return {
            "request_id": request_id[:8],
            "first_duplicate": is_duplicate_1,
            "second_duplicate": is_duplicate_2,
            "third_duplicate": is_duplicate_3
        }
    
    async def demo_connection_pooling(self) -> Dict[str, Any]:
        """Demonstrate HTTP connection pooling"""
        logger.info("🌐 Connection Pooling Demo")
        
        pool = await get_global_pool(GROQ_OPTIMIZED_CONFIG)
        
        # Simulate multiple requests to show connection reuse
        start_time = time.time()
        
        tasks = []
        for i in range(5):
            # Simulate HTTP requests (we'll use httpbin for demo)
            task = asyncio.create_task(
                self._simulate_http_request(pool, f"request_{i}")
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # Get pool statistics
        stats = pool.get_stats()
        
        logger.info(f"Completed {len(results)} requests in {elapsed:.2f}s")
        logger.info(f"Pool stats: {stats['pool_stats']}")
        
        return {
            "requests_completed": len(results),
            "total_time": elapsed,
            "pool_stats": stats["pool_stats"],
            "successful_requests": sum(1 for r in results if not isinstance(r, Exception))
        }
    
    async def _simulate_http_request(self, pool: OptimizedConnectionPool, 
                                   request_id: str) -> str:
        """Simulate HTTP request for connection pool demo"""
        try:
            # Use httpbin for demo (replace with actual Groq API in real usage)
            async with pool.request("GET", "https://httpbin.org/delay/1") as response:
                if response.status_code == 200:
                    logger.info(f"✅ {request_id} completed successfully")
                    return f"{request_id}_success"
                else:
                    logger.warning(f"⚠️ {request_id} failed with status {response.status_code}")
                    return f"{request_id}_failed"
        except Exception as e:
            logger.error(f"❌ {request_id} error: {e}")
            return f"{request_id}_error"
    
    def demo_adaptive_rate_limiting(self) -> Dict[str, Any]:
        """Demonstrate adaptive rate limiting based on file size"""
        logger.info("🎯 Adaptive Rate Limiting Demo")
        
        # Different file scenarios
        scenarios = [
            {"duration": 300, "description": "5-minute video"},
            {"duration": 1800, "description": "30-minute video"},
            {"duration": 7200, "description": "2-hour video"},
            {"duration": 14400, "description": "4-hour video"},
            {"duration": 28800, "description": "8-hour video"}
        ]
        
        results = []
        
        for scenario in scenarios:
            transcriber = EnhancedAudioTranscriber("auto")
            
            # Calculate optimal settings
            optimal_model = transcriber.select_optimal_model(
                scenario["duration"], "en"
            )
            chunk_duration = transcriber.calculate_optimal_chunk_duration(
                scenario["duration"]
            )
            workers = transcriber.calculate_workers_for_duration(
                scenario["duration"]
            )
            
            result = {
                "description": scenario["description"],
                "duration": scenario["duration"],
                "optimal_model": optimal_model,
                "chunk_duration": chunk_duration,
                "workers": workers,
                "estimated_chunks": scenario["duration"] // chunk_duration
            }
            
            results.append(result)
            
            logger.info(f"{scenario['description']}: {optimal_model}, "
                       f"{chunk_duration}s chunks, {workers} workers")
        
        return {"scenarios": results}
    
    async def run_all_demos(self) -> Dict[str, Any]:
        """Run all demonstration scenarios"""
        logger.info("🚀 Starting Advanced Rate Limiting Demos")
        
        results = {}
        
        # Circuit breaker demo
        results["circuit_breaker"] = self.demo_circuit_breaker_pattern()
        
        # Exponential backoff demo
        results["exponential_backoff"] = self.demo_exponential_backoff()
        
        # Request deduplication demo
        results["request_deduplication"] = self.demo_request_deduplication()
        
        # Connection pooling demo
        results["connection_pooling"] = await self.demo_connection_pooling()
        
        # Adaptive rate limiting demo
        results["adaptive_rate_limiting"] = self.demo_adaptive_rate_limiting()
        
        logger.info("✅ All demos completed successfully")
        
        return results


def example_basic_usage():
    """Basic usage example"""
    logger.info("📚 Basic Usage Example")
    
    # Create rate limiter for specific model
    rate_limiter = SyncRateLimiter("whisper-large-v3-turbo")
    
    # Use in transcription loop
    for i in range(5):
        # Wait if rate limit reached
        rate_limiter.wait_if_needed()
        
        try:
            # Simulate API call
            logger.info(f"Making API call {i+1}")
            time.sleep(0.1)  # Simulate processing time
            
            # Record success
            rate_limiter.record_success()
            
        except Exception as e:
            # Record failure
            rate_limiter.record_failure()
            logger.error(f"API call failed: {e}")


async def example_async_usage():
    """Async usage example with connection pooling"""
    logger.info("🔄 Async Usage Example")
    
    # Create advanced rate limiter
    rate_limiter = create_rate_limiter("whisper-large-v3-turbo")
    
    try:
        # Use rate limiter in async context
        async with rate_limiter.rate_limited_request(
            file_path="/tmp/test.wav",
            model="whisper-large-v3-turbo"
        ) as client:
            logger.info("Making rate-limited request")
            
            # Simulate file upload
            files = {"file": ("test.wav", b"fake_audio_data", "audio/wav")}
            
            # This would be actual Groq API call
            # response = await client.post(
            #     "https://api.groq.com/openai/v1/audio/transcriptions",
            #     files=files
            # )
            
            logger.info("Request completed successfully")
            
    except Exception as e:
        logger.error(f"Rate-limited request failed: {e}")
    
    finally:
        await rate_limiter.close()


def example_production_usage():
    """Production-ready usage example"""
    logger.info("🏭 Production Usage Example")
    
    # Enhanced transcriber with all optimizations
    transcriber = EnhancedAudioTranscriber("whisper-large-v3-turbo")
    
    try:
        # This would be actual audio file
        audio_file = "/path/to/large_audio_file.mp3"
        
        # Transcribe with full optimization
        result = transcriber.transcribe_audio_enhanced(audio_file, language="en")
        
        if result:
            logger.info(f"Transcription successful: {len(result.split())} words")
            
            # Get performance metrics
            metrics = transcriber.get_session_metrics()
            logger.info(f"Performance: {metrics['speed_factor']:.1f}x realtime")
            logger.info(f"Success rate: {metrics['success_rate']:.1f}%")
            
        else:
            logger.error("Transcription failed")
            
    except Exception as e:
        logger.error(f"Production transcription error: {e}")


async def main():
    """Main demonstration function"""
    logger.info("🎬 Advanced Rate Limiting Demonstration")
    
    # Run basic example
    example_basic_usage()
    
    # Run async example
    await example_async_usage()
    
    # Run production example (commented out - requires actual audio file)
    # example_production_usage()
    
    # Run comprehensive demos
    demo = RateLimitingDemo()
    results = await demo.run_all_demos()
    
    # Print summary
    logger.info("📊 Demo Results Summary:")
    for demo_name, result in results.items():
        logger.info(f"  {demo_name}: ✅ Completed")
    
    logger.info("🎉 All demonstrations completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())