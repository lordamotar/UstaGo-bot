from aiogram import Router, F, types
from bot.utils.faq_manager import faq_manager
from bot.keyboards.faq import get_faq_keyboard, get_back_to_faq_keyboard
from database.engine import async_session_maker
from database.models import User, UserRole
from sqlalchemy import select

router = Router()

async def get_user_role_key(telegram_id: int) -> str:
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return "client"
        if user.role == UserRole.MASTER:
            return "master"
        return "client"

@router.message(F.text.in_({"❓ FAQ", "Помощь", "Справка"}))
async def show_faq_main(message: types.Message):
    role_key = await get_user_role_key(message.from_user.id)
    questions = faq_manager.get_questions(role_key)
    
    if not questions:
        return await message.answer("ℹ️ Раздел FAQ временно пуст.")
        
    kb = get_faq_keyboard(questions, page=0, section=role_key)
    await message.answer(
        "❓ <b>Часто задаваемые вопросы</b>\n\nВыберите интересующий вас вопрос из списка ниже:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("faq_p:"))
async def faq_pagination(callback: types.CallbackQuery):
    try:
        _, section, page = callback.data.split(":")
        page = int(page)
    except ValueError:
        return await callback.answer()

    questions = faq_manager.get_questions(section)
    kb = get_faq_keyboard(questions, page=page, section=section)
    
    await callback.message.edit_text(
        "❓ <b>Часто задаваемые вопросы</b>\n\nВыберите интересующий вас вопрос из списка ниже:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("faq_q:"))
async def faq_question_detail(callback: types.CallbackQuery):
    try:
        _, section, q_idx = callback.data.split(":")
        q_idx = int(q_idx)
    except ValueError:
        return await callback.answer()

    questions = faq_manager.get_questions(section)
    
    if 0 <= q_idx < len(questions):
        q = questions[q_idx]
        text = f"❓ <b>{q['question']}</b>\n\n{q['answer']}"
        page = q_idx // 5 # Page size is 5
        kb = get_back_to_faq_keyboard(section, page)
        
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            # Fallback if edit fails (e.g. content too long or same)
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
            await callback.message.delete()
            
    await callback.answer()

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()
