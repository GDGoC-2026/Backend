from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from Backend.api.v1.router import api_router
from Backend.core.config import settings
from Backend.services.oauth import register_oauth_providers
from Backend.db.vector import init_milvus, disconnect_milvus, create_default_collections
from Backend.db.graph import neo4j_db
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Connecting to Milvus...")
        init_milvus()
        create_default_collections()
        logger.info("Milvus ready")
    except Exception as e:
        logger.warning(f"Milvus init failed: {e}")

    yield

    try:
        disconnect_milvus()
        await neo4j_db.close()
    except Exception as e:
        logger.warning(f"Shutdown error: {e}")

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

@app.get("/health")
async def health_check():
    return {"status": "ok"}
