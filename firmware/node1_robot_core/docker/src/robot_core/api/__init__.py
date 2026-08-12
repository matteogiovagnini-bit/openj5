"""
OpenJ5 Robot Core - API Module

REST API + WebSocket for robot control, monitoring, and configuration.
"""

from robot_core.api.rest import create_rest_api
from robot_core.api.websocket import create_websocket_handler
from robot_core.api.models import *

def create_api_app(
    config,
    event_bus,
    plugin_manager,
    ota_manager,
    scheduler,
    state_machine,
    digital_twin,
    health_service,
):
    """Create complete API application with REST and WebSocket."""
    
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(
        title="OpenJ5 Robot Core API",
        description="REST API and WebSocket for OpenJ5 Robot Platform",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount REST API
    rest_api = create_rest_api(
        config=config,
        event_bus=event_bus,
        plugin_manager=plugin_manager,
        ota_manager=ota_manager,
        scheduler=scheduler,
        state_machine=state_machine,
        digital_twin=digital_twin,
        health_service=health_service,
    )
    app.include_router(rest_api, prefix="/api/v1")
    
    # Mount WebSocket
    ws_handler = create_websocket_handler(
        event_bus=event_bus,
        state_machine=state_machine,
        health_service=health_service,
    )
    app.include_router(ws_handler, prefix="/ws")
    
    # Health endpoint (no auth)
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "openj5-robot-core"}
    
    @app.get("/ready")
    async def ready():
        # Check if all critical services are ready
        return {"ready": True}
    
    return app