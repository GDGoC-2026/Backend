from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from Backend.db.session import get_db
from Backend.core.config import settings
from Backend.crud.user import get_user_by_email
from Backend.schemas.user import UserProfile
from Backend.models.user import User
from Backend.core.security import ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = await get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user
