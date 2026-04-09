from fastapi import APIRouter
from Backend.api.v1.endpoints import auth, users, knowledge, notifications

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
# Knowledge Graph endpoints
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])