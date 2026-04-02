import asyncio
from sqlalchemy import select
from database.engine import async_session_maker
from database.models import Category, District
from bot.core.constants import LIST_OF_DISTRICTS

MOCK_CATEGORIES = [
    "Электрик", "Сантехник", "Сборка мебели", "Вскрытие замков", 
    "Уборка квартир", "Мойка окон", "Мастер на час"
]

async def seed():
    async with async_session_maker() as session:
        # Seed Categories
        for cat_name in MOCK_CATEGORIES:
            stmt = select(Category).where(Category.name == cat_name)
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                session.add(Category(name=cat_name))
        
        # Seed Districts
        for dist_name in LIST_OF_DISTRICTS:
            stmt = select(District).where(District.name == dist_name)
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                session.add(District(name=dist_name))
                
        await session.commit()
    print("Database seeded with categories and districts.")

if __name__ == "__main__":
    asyncio.run(seed())
