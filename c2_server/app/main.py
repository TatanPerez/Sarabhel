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
from .application.use_cases.register_agent import RegisterAgent
from .application.use_cases.store_result import StoreResult
from .application.use_cases.update_heartbeat import UpdateHeartbeat
from .infrastructure.Base import SessionLocal, init_db
from .infrastructure.repositories import AgentRepository, CommandRepository, ResultRepository

# ----------------------------------------------------------------------
# Logging configuration
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)


def configure_mqtt_callbacks() -> None:
    async def handle_register(payload: dict) -> None:
        db = SessionLocal()
        try:
            await RegisterAgent(AgentRepository(db)).execute(payload)
        finally:
            db.close()

    async def handle_heartbeat(agent_id: str, payload: dict) -> None:
        db = SessionLocal()
        try:
            await UpdateHeartbeat(AgentRepository(db)).execute(agent_id, payload)
        finally:
            db.close()

    async def handle_result(agent_id: str, payload: dict) -> None:
        db = SessionLocal()
        try:
            await StoreResult(ResultRepository(db), CommandRepository(db)).execute(agent_id, payload)
        finally:
            db.close()

    mqtt_service.on_register(handle_register)
    mqtt_service.on_heartbeat(handle_heartbeat)
    mqtt_service.on_result(handle_result)

# ----------------------------------------------------------------------
# FastAPI lifespan handler
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("🚀 Starting C2 Server...")
    init_db()  # ensure tables exist
    configure_mqtt_callbacks()
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


@app.get("/health", include_in_schema=False)
async def root_health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
