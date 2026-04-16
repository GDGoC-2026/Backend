from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from Backend.api.v1.router import api_router
from Backend.core.config import settings
from Backend.services.oauth import register_oauth_providers
from Backend.db.vector import init_milvus, disconnect_milvus, connect_milvus, create_default_collections
from Backend.db.graph import neo4j_db
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_milvus()
    yield
    # Shutdown
    disconnect_milvus()
    await neo4j_db.close()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_oauth_providers()
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize Milvus and create default collections on startup"""
    try:
        logger.info("Connecting to Milvus...")
        connect_milvus()
        logger.info("Successfully connected to Milvus")
        
        logger.info("Creating default Milvus collections...")
        create_default_collections()
        logger.info("Milvus collections initialized")
    except Exception as e:
        logger.warning(f"Milvus initialization warning: {e}")
        logger.info("Continuing without Milvus - some features may be limited")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up Milvus connection on shutdown"""
    try:
        logger.info("Disconnecting from Milvus...")
        disconnect_milvus()
        logger.info("Milvus connection closed")
    except Exception as e:
        logger.warning(f"Error during Milvus shutdown: {e}")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
