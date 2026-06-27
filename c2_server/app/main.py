"""
C2 Server – FastAPI application entry point.

This module wires together the FastAPI application, configures routes,
and initialises the background MQTT client on startup.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .transport.api.routers import router
from .infrastructure.mqtt_client import mqtt_service
from .infrastructure.Base import init_db
from .settings import settings

# ----------------------------------------------------------------------
# Logging configuration
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# FastAPI lifespan handler
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("🚀 Starting C2 Server...")
    init_db()  # ensure tables exist
    await mqtt_service.connect()
    log.info("✅ C2 Server is ready")
    yield
    # Shutdown
    log.info("🧹 Shutting down...")
    await mqtt_service.close()

# ----------------------------------------------------------------------
# FastAPI application factory
# ----------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="C2 Lab Server",
        description="Command & Control server for the authorized hackathon lab.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(router, prefix="/api/v1")

    # CORS – allow any origin for simplicity in the lab
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app

# ----------------------------------------------------------------------
# Uvicorn entry point
# ----------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)