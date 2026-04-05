import asyncio
import logging
from database.engine import engine
from database.models import Base, Category
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_database():
    """Drops and recreates all tables, then seeds initial data."""
    async with engine.begin() as conn:
        logger.info("💥 Уничтожаем старые таблицы (Dropping all tables)...")
        await conn.run_sync(Base.metadata.drop_all)
        
        logger.info("🏗 Создаем чистую структуру (Creating all tables)...")
        await conn.run_sync(Base.metadata.create_all)

    # Initial seeding phase
    async_session = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    
    async with async_session() as session:
        logger.info("🌱 Наполняем базу стартовыми категориями...")
        initial_categories = [
            '🚰 Сантехник', 
            '⚡️ Электрик', 
            '🔨 Плотник/Мебель', 
            '🚛 Грузоперевозки',
            '🧹 Уборка/Клининг',
            '💻 Ремонт техники'
        ]
        
        for cat_name in initial_categories:
            session.add(Category(name=cat_name, is_active=True))
        
        # Initialize SystemSettings row
        from database.models import SystemSettings
        session.add(SystemSettings(id=1, crypto_enabled=False, bank_enabled=False))
        
        await session.commit()
        logger.info("✅ База данных успешно очищена и готова к работе!")

if __name__ == "__main__":
    try:
        asyncio.run(reset_database())
    except KeyboardInterrupt:
        logger.info("Очистка прервана пользователем.")
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке БД: {e}")
