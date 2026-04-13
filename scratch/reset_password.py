import asyncio
from passlib.context import CryptContext
from sqlalchemy import select, update
from database.engine import async_session_maker
from database.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

async def reset_password(username, new_password):
    async with async_session_maker() as session:
        # Проверяем, существует ли пользователь
        stmt = select(User).where(User.username == username)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user:
            print(f"❌ Пользователь с логином '{username}' не найден.")
            return

        # Обновляем пароль
        hashed_password = get_password_hash(new_password)
        await session.execute(
            update(User).where(User.username == username).values(hashed_password=hashed_password)
        )
        await session.commit()
        print(f"✅ Пароль для пользователя '{username}' успешно изменен на '{new_password}'")

if __name__ == "__main__":
    # Укажите здесь ваш логин и новый пароль
    USERNAME_TO_RESET = "admin" 
    NEW_PASS = "admin12345"
    
    asyncio.run(reset_password(USERNAME_TO_RESET, NEW_PASS))
