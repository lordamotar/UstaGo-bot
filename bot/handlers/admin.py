from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from bot.core.config import config
from database.engine import async_session_maker
from database.models import User, MasterProfile, MasterStatus, UserRole
from sqlalchemy import select, update

router = Router()

@router.message(Command("admin"))
async def admin_menu(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return

    async with async_session_maker() as session:
        stmt = select(MasterProfile).where(MasterProfile.status == MasterStatus.PENDING)
        result = await session.execute(stmt)
        pending_masters = result.scalars().all()
        
    count = len(pending_masters)
    text = f"👨‍✈️ Админ-панель\n\nЗаявок на проверку: {count}"
    
    if count > 0:
        # For simplicity, showing the first one or just a list
        # In a real app we'd have pagination.
        await message.answer(text)
    else:
        await message.answer(text)

@router.callback_query(F.data.startswith("admin_approve:"))
async def approve_master(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("У вас нет прав.")
        return
        
    master_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        # Update Master Status
        q = update(MasterProfile).where(MasterProfile.id == master_id).values(status=MasterStatus.APPROVED)
        await session.execute(q)
        
        # Get Master's Telegram ID to notify them
        stmt = select(User.telegram_id).join(MasterProfile).where(MasterProfile.id == master_id)
        res = await session.execute(stmt)
        tg_id = res.scalar()
        
        await session.commit()
        
    await callback.message.edit_text(f"✅ Мастер #{master_id} одобрен!")
    
    try:
        await callback.bot.send_message(
            tg_id, 
            "🎉 Поздравляем! Ваш профиль мастера одобрен.\n"
            "Теперь вы будете получать уведомления о новых заказах в ваших категориях."
        )
    except Exception:
        pass
    
    await callback.answer()

@router.callback_query(F.data.startswith("admin_reject:"))
async def reject_master(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
        
    master_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        q = update(MasterProfile).where(MasterProfile.id == master_id).values(status=MasterStatus.REJECTED)
        await session.execute(q)
        await session.commit()
        
    await callback.message.edit_text(f"❌ Мастер #{master_id} отклонен.")
    await callback.answer()
