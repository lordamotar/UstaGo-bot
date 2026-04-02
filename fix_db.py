import asyncio
from sqlalchemy import text
from database.engine import engine

async def fix():
    async with engine.begin() as conn:
        print("Очистка базы данных...")
        # Drop tables with CASCADE
        tables = [
            "transactions", "reviews", "bids", "orders", 
            "master_district_areas", "master_category_subscriptions",
            "districts", "master_profiles", "categories", "users", "alembic_version"
        ]
        for table in tables:
            print(f"Dropping table {table}...")
            await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
            
        # Drop types
        types = ["userrole", "masterstatus", "orderstatus", "transactiontype"]
        for t in types:
            print(f"Dropping type {t}...")
            await conn.execute(text(f"DROP TYPE IF EXISTS {t} CASCADE;"))
        
    await engine.dispose()
    print("Успешно очищено. Теперь можно повторить alembic upgrade head.")

if __name__ == "__main__":
    asyncio.run(fix())
