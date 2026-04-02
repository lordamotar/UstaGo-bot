import asyncio
import sys
import os
sys.path.append(os.getcwd())
from sqlalchemy import text
from database.engine import engine

async def fix_database():
    print("🚀 Adding dnd columns to users table...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN dnd_start VARCHAR(5);"))
            print("✅ Column dnd_start added.")
        except Exception as e:
            print(f"⚠️ dnd_start maybe exists: {e}")
            
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN dnd_end VARCHAR(5);"))
            print("✅ Column dnd_end added.")
        except Exception as e:
            print(f"⚠️ dnd_end maybe exists: {e}")

        try:
            # We also renamed/removed do_not_disturb, but it's safer to just leave it or drop
            await conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS do_not_disturb;"))
            print("✅ Column do_not_disturb removed.")
        except Exception: pass

    print("🏁 Migration finished!")

if __name__ == "__main__":
    asyncio.run(fix_database())
