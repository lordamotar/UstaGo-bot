import asyncio
from sqlalchemy import text
from database.engine import engine

async def fix():
    async with engine.begin() as conn:
        print("Очистка конфликтующих ENUM типов...")
        await conn.execute(text("DROP TYPE IF EXISTS userrole CASCADE;"))
        await conn.execute(text("DROP TYPE IF EXISTS masterstatus CASCADE;"))
        await conn.execute(text("DROP TYPE IF EXISTS orderstatus CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
        
    await engine.dispose()
    print("Успешно очищено. Теперь можно повторить upgrade head.")

if __name__ == "__main__":
    asyncio.run(fix())
