from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Backend.models.user import User
from Backend.core.security import hash_password, verify_password

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, email: str, password: str, full_name: str | None = None, is_oauth_user: bool = False) -> User:
    user = User(
        email=email,
        hashed_password=None if is_oauth_user else hash_password(password),
        full_name=full_name,
        is_oauth_user=is_oauth_user,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

def authenticate_user(user: User | None, password: str) -> bool:
    if not user or not user.hashed_password:
        return False
    return verify_password(password, user.hashed_password)
