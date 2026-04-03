import asyncio
from sqlalchemy import text
from database.engine import engine

async def update_db():
    async with engine.begin() as conn:
        print("Checking/Adding 'banned_until' column to 'users' table...")
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_until TIMESTAMP WITHOUT TIME ZONE"))
            print("Successfully added 'banned_until' column (or it already exists).")
        except Exception as e:
            print(f"Error while adding column: {e}")
            
        print("Checking/Adding 'support_tickets' table...")
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    message TEXT NOT NULL,
                    is_replied BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("Successfully checked/created 'support_tickets' table.")
        except Exception as e:
            print(f"Error while creating table: {e}")

        print("Checking/Adding 'support_chats' table...")
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS support_chats (
                    id SERIAL PRIMARY KEY,
                    user_tid BIGINT NOT NULL,
                    admin_tid BIGINT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("Successfully checked/created 'support_chats' table.")
        except Exception as e:
            print(f"Error while creating chat table: {e}")

if __name__ == "__main__":
    asyncio.run(update_db())
