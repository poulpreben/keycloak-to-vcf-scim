import logging
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.core.config import get_settings
from src.api.routes import router
from src.api.debug_routes import debug_router
from src.services.scheduler import SyncScheduler
from src.core.sync_state import sync_state

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global scheduler
    settings = get_settings()
    
    # Startup
    logger.info("Starting SCIM Client application...")
    logger.info(f"Environment: {settings.environment}")
    
    # Initialize and start scheduler
    scheduler = SyncScheduler(settings)
    scheduler.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down SCIM Client application...")
    if scheduler:
        scheduler.stop()


# Create FastAPI app
app = FastAPI(
    title="SCIM Client for vCenter",
    description="Automates user provisioning from Keycloak to vCenter Server via SCIM",
    version="1.0.0",
    lifespan=lifespan
)

# Get settings
settings = get_settings()

# Include routers
app.include_router(router, prefix=settings.api_prefix)

# Include debug routes only in DEV environment
if settings.environment == "DEV":
    app.include_router(debug_router, prefix=settings.api_prefix)
    logger.info("Debug endpoints enabled (DEV environment)")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "SCIM Client for vCenter",
        "environment": settings.environment,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with last sync information"""
    sync_info = sync_state.get_sync_info()
    
    # Determine overall health status
    status = "healthy"
    if sync_info.get("last_sync_result"):
        result = sync_info["last_sync_result"]
        if result.get("errors") and len(result["errors"]) > 0:
            status = "degraded"
    
    return {
        "status": status,
        "sync": sync_info
    }


if __name__ == "__main__":
    settings = get_settings()
    
    # Set log level
    logging.getLogger().setLevel(settings.log_level)
    
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "DEV",
        log_level=settings.log_level.lower()
    )