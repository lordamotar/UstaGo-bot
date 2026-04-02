from bot.keyboards.master import get_master_main_menu
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

from database.models import User, MasterProfile, MasterStatus, UserRole, Transaction, TransactionType

router = Router()

@router.callback_query(F.data.startswith("admin_approve:"))
async def approve_master(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("У вас нет прав.")
        return
        
    master_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        # Get Master's User object to check referral
        stmt = select(User).join(MasterProfile).where(MasterProfile.id == master_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user:
            await callback.answer("User not found.")
            return

        # Update Master Status
        profile_stmt = select(MasterProfile).where(MasterProfile.id == master_id)
        profile_res = await session.execute(profile_stmt)
        profile = profile_res.scalar_one_or_none()
        profile.status = MasterStatus.APPROVED
        
        # Referral Bonus Logic
        if user.referred_by:
            # Inviter Bonus
            inviter_stmt = select(User).where(User.id == user.referred_by)
            inviter_res = await session.execute(inviter_stmt)
            inviter = inviter_res.scalar_one_or_none()
            if inviter:
                bonus_amount = 1000
                inviter.points += bonus_amount
                session.add(Transaction(
                    user_id=inviter.id,
                    amount=bonus_amount,
                    type=TransactionType.REFERRAL_BONUS,
                    description=f"Бонус за приглашенного мастера {user.full_name}"
                ))
                # Master Bonus
                user.points += bonus_amount
                session.add(Transaction(
                    user_id=user.id,
                    amount=bonus_amount,
                    type=TransactionType.REFERRAL_BONUS,
                    description="Бонус за регистрацию по реферальной ссылке"
                ))
                
                # Notify Inviter
                try:
                    await callback.bot.send_message(
                        inviter.telegram_id,
                        f"🎁 Ваш приглашенный мастер {user.full_name} прошел модерацию!\n"
                        f"Вам начислено {bonus_amount} баллов!"
                    )
                except Exception:
                    pass
        
        tg_id = user.telegram_id
        await session.commit()
        
    await callback.message.edit_text(f"✅ Мастер #{master_id} одобрен!")
    
    try:
        await callback.bot.send_message(
            tg_id, 
            "🎉 Поздравляем! Ваш профиль мастера одобрен.\n"
            "Теперь вы будете получать уведомления о новых заказах в ваших категориях.",
            reply_markup=get_master_main_menu()
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
