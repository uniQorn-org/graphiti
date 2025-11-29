"""
FastAPI main application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
from .config import get_settings, init_services, shutdown_services

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    logger.info("Initializing services...")
    await init_services()
    logger.info("Service initialization completed")
    yield
    # Shutdown
    logger.info("Shutting down services...")
    await shutdown_services()
    logger.info("Service shutdown completed")


# Create FastAPI application
app = FastAPI(
    title="Graphiti Search Bot API",
    description="Internal search bot using LangChain + Graphiti",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
settings = get_settings()
origins = settings.cors_origins.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register router
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Graphiti Search Bot API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.backend_port,
        reload=True,
        log_level="info",
    )
