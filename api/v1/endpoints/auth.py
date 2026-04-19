from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.api.deps import get_current_user
from Backend.core.config import settings
from Backend.core.security import create_access_token
from Backend.crud.user import authenticate_user, create_user, get_user_by_email
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.schemas.user import Token, UserCreate, UserLogin, UserProfile
from Backend.services.oauth import oauth


router = APIRouter()


def _resolve_oauth_redirect_uri(request: Request, provider: str):
    configured_redirect_uri = (
        settings.google_redirect_uri if provider == "google" else settings.github_redirect_uri
    )
    requested_redirect_uri = request.query_params.get("redirect_uri")

    if requested_redirect_uri:
        return requested_redirect_uri

    if configured_redirect_uri:
        return configured_redirect_uri

    return str(request.url_for(f"{provider}_callback"))


@router.post("/register", response_model=UserProfile, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await create_user(db, payload.email, payload.password, payload.full_name)
    return user


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, payload.email)
    if not user or not authenticate_user(user, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(
        subject=user.email,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return Token(access_token=token)


@router.get("/me", response_model=UserProfile)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/google/login")
async def google_login(request: Request):
    if "google" not in oauth.create_client.__self__._clients:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")
    redirect_uri = _resolve_oauth_redirect_uri(request, "google")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", response_model=Token)
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    if "google" not in oauth.create_client.__self__._clients:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await oauth.google.parse_id_token(request, token)

    email = userinfo.get("email")
    full_name = userinfo.get("name")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    user = await get_user_by_email(db, email)
    if not user:
        user = await create_user(db, email=email, password="oauth-user-placeholder", full_name=full_name, is_oauth_user=True)

    access_token = create_access_token(subject=user.email)
    return Token(access_token=access_token)


@router.get("/github/login")
async def github_login(request: Request):
    if "github" not in oauth.create_client.__self__._clients:
        raise HTTPException(status_code=400, detail="GitHub OAuth is not configured")
    redirect_uri = _resolve_oauth_redirect_uri(request, "github")
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback", response_model=Token)
async def github_callback(request: Request, db: AsyncSession = Depends(get_db)):
    if "github" not in oauth.create_client.__self__._clients:
        raise HTTPException(status_code=400, detail="GitHub OAuth is not configured")
    token = await oauth.github.authorize_access_token(request)
    resp = await oauth.github.get("user", token=token)
    profile = resp.json()

    email = profile.get("email")
    if not email:
        emails_resp = await oauth.github.get("user/emails", token=token)
        emails = emails_resp.json()
        primary_email = next((e["email"] for e in emails if e.get("primary")), None)
        email = primary_email

    if not email:
        raise HTTPException(status_code=400, detail="GitHub account has no accessible email")

    full_name = profile.get("name") or profile.get("login")
    user = await get_user_by_email(db, email)
    if not user:
        user = await create_user(db, email=email, password="oauth-user-placeholder", full_name=full_name, is_oauth_user=True)

    access_token = create_access_token(subject=user.email)
    return Token(access_token=access_token)
