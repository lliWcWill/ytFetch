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
from .api.endpoints import router


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

# Include API router
app.include_router(router)


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
            "video_info": "/api/v1/video-info/{video_id}"
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