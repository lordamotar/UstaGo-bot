from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from bot.core.config import config

engine = create_async_engine(config.DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with async_session_maker() as session:
        yield session
