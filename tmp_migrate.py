import asyncio
from sqlalchemy import text
from database.engine import engine

async def update_db():
    async with engine.begin() as conn:
        print("Updating 'categories' table...")
        try:
            await conn.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
            await conn.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP"))
            print("Successfully updated 'categories'.")
            
            # Seed
            await conn.execute(text("""
                INSERT INTO categories (name) VALUES 
                ('🚰 Сантехник'), 
                ('⚡️ Электрик'), 
                ('🔨 Плотник/Мебель'), 
                ('🚛 Грузоперевозки'),
                ('🧹 Уборка/Клининг'),
                ('💻 Ремонт техники')
                ON CONFLICT (name) DO NOTHING
            """))
            print("Categories seeded correctly in 'categories' table.")
        except Exception as e:
            print(f"Error while updating categories: {e}")

if __name__ == "__main__":
    asyncio.run(update_db())
