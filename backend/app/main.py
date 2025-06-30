"""
Main FastAPI application for ytFetch backend.
Production-ready YouTube transcription service.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import settings, ensure_temp_dir
from .core.supabase import SupabaseClient, SupabaseError
from .api.endpoints import router
from .api.bulk_endpoints import router as bulk_router
from .api.stripe_endpoints import router as stripe_router
from .api.token_endpoints import router as token_router


# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting ytFetch backend...")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Temp directory: {settings.temp_dir}")
    
    # Ensure temp directory exists
    ensure_temp_dir()
    
    # Verify API keys
    if not settings.groq_api_key:
        logger.warning("Groq API key not configured")
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured")
    
    # Initialize Supabase if configured
    try:
        if SupabaseClient.is_configured():
            SupabaseClient.initialize()
            health = SupabaseClient.health_check()
            if health["anon_client"]:
                logger.info("Supabase anonymous client initialized successfully")
            if health["service_client"]:
                logger.info("Supabase service role client initialized successfully")
            elif settings.supabase_service_role_key:
                logger.warning("Supabase service role key provided but client failed to initialize")
        else:
            logger.info("Supabase not configured, skipping initialization")
    except SupabaseError as e:
        logger.error(f"Supabase initialization failed: {e}")
        # Continue startup - Supabase is optional
    
    logger.info("Backend startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ytFetch backend...")


# Create FastAPI application
app = FastAPI(
    title="ytFetch Backend",
    description="Production-ready YouTube transcription service with enhanced download strategies",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(router)
app.include_router(bulk_router)
app.include_router(stripe_router)
app.include_router(token_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ytFetch Backend",
        "version": "0.1.0",
        "status": "healthy",
        "docs": "/docs" if settings.debug else "disabled",
        "endpoints": {
            "health": "/health",
            "transcribe": "/api/v1/transcribe",
            "video_info": "/api/v1/video-info/{video_id}",
            "supabase_health": "/api/v1/supabase/health",
            "bulk_analyze": "/api/v1/bulk/analyze",
            "bulk_create": "/api/v1/bulk/create",
            "bulk_jobs": "/api/v1/bulk/jobs",
            "bulk_job_status": "/api/v1/bulk/jobs/{job_id}",
            "bulk_start": "/api/v1/bulk/jobs/{job_id}/start",
            "bulk_cancel": "/api/v1/bulk/jobs/{job_id}/cancel",
            "bulk_download": "/api/v1/bulk/jobs/{job_id}/download",
            "bulk_delete": "/api/v1/bulk/jobs/{job_id}",
            "stripe_checkout": "/api/v1/stripe/checkout-session",
            "stripe_portal": "/api/v1/stripe/portal-session",
            "stripe_prices": "/api/v1/stripe/prices",
            "stripe_subscription_info": "/api/v1/stripe/subscription-info"
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "details": {"error": str(exc)} if settings.debug else {}
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )