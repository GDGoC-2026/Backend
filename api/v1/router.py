from fastapi import APIRouter
from Backend.api.v1.endpoints import auth, users, notifications, editor, notes, learning, gamification, judge

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(editor.router, prefix="/editor", tags=["editor"])
# Note & Knowledge Management
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
api_router.include_router(gamification.router, prefix="/gamification", tags=["gamification"])
api_router.include_router(judge.router, prefix="/judge", tags=["judge"])
