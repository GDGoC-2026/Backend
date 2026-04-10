from fastapi import APIRouter
from Backend.api.v1.endpoints import auth, users, notifications, editor, notes

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
# Note & Knowledge Management
api_router.include_router(notes.router, prefix="/notes", tags=["notes", "knowledge"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(editor.router, prefix="/editor", tags=["editor"])
