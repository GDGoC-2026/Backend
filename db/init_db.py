from Backend.db.session import engine
from Backend.db.base import Base

import asyncio

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init())