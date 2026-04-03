from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from bot.states import SupportStates
from database.engine import async_session_maker
from database.models import User, SupportTicket, SupportChat, UserRole
from bot.keyboards.client import get_client_main_menu
from bot.keyboards.master import get_master_main_menu
from bot.keyboards.admin import get_admin_main_menu
from bot.core.config import config
from sqlalchemy import select, and_, update
from datetime import datetime

router = Router()

def get_finish_chat_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Завершить диалог")]],
        resize_keyboard=True
    )

@router.message(F.text == "📩 Обратная связь")
async def start_support(message: Message, state: FSMContext):
    # Check if user is in active chat
    async with async_session_maker() as session:
        active_chat = (await session.execute(
            select(SupportChat).where(and_(SupportChat.user_tid == message.from_user.id, SupportChat.is_active == True))
        )).scalar_one_or_none()
        
        if active_chat:
            await state.set_state(SupportStates.active_chat)
            await message.answer(
                "⚠️ У вас уже есть активный диалог с администрацией. Можете продолжать писать сообщения здесь.",
                reply_markup=get_finish_chat_kb()
            )
            return

    await state.set_state(SupportStates.entering_message)
    await message.answer(
        "👋 <b>Служба поддержки УстаGo</b>\n\n"
        "Напишите ваше сообщение администрации. Мы ответим вам в ближайшее время.\n"
        "Ваше обращение будет передано анонимно.",
        parse_mode="HTML"
    )

@router.message(F.text == "❌ Завершить диалог")
async def finish_chat_handler(message: Message, state: FSMContext):
    user_tid = message.from_user.id
    
    async with async_session_maker() as session:
        # Find active chat
        chat = (await session.execute(
            select(SupportChat).where(
                and_(
                    SupportChat.is_active == True,
                    (SupportChat.user_tid == user_tid) | (SupportChat.admin_tid == user_tid)
                )
            )
        )).scalar_one_or_none()
        
        if chat:
            chat.is_active = False
            await session.commit()
            
            other_tid = chat.admin_tid if user_tid == chat.user_tid else chat.user_tid
            
            # Helper to get menu for any user tid
            async def send_menu_back(tid, msg_text, current_bot):
                async with async_session_maker() as sub_session:
                    u = (await sub_session.execute(select(User).where(User.telegram_id == tid))).scalar_one_or_none()
                    if u:
                        if u.role == UserRole.ADMIN: kb = get_admin_main_menu()
                        elif u.role == UserRole.MASTER: kb = get_master_main_menu()
                        else: kb = get_client_main_menu()
                        
                        try:
                            await current_bot.send_message(tid, msg_text, parse_mode="HTML", reply_markup=kb)
                        except: pass

            # Finish for sender
            await send_menu_back(user_tid, "🏁 <b>Диалог завершен.</b>", message.bot)
            # Finish for other side
            await send_menu_back(other_tid, "🏁 <b>Собеседник завершил диалог.</b>", message.bot)
            
    await state.clear()

@router.message(SupportStates.active_chat)
async def handle_active_chat(message: Message, state: FSMContext):
    if message.text == "❌ Завершить диалог":
        return # Handled by finish_chat_handler
        
    user_tid = message.from_user.id
    async with async_session_maker() as session:
        chat = (await session.execute(
            select(SupportChat).where(
                and_(
                    SupportChat.is_active == True,
                    (SupportChat.user_tid == user_tid) | (SupportChat.admin_tid == user_tid)
                )
            )
        )).scalar_one_or_none()
        
        if not chat:
            await state.clear()
            await message.answer("❌ Активный диалог не найден.")
            return
            
        target_tid = chat.admin_tid if user_tid == chat.user_tid else chat.user_tid
        
        prefix = "👤 <b>Пользователь:</b>\n" if user_tid == chat.user_tid else "👨‍✈️ <b>Админ:</b>\n"
        
        try:
            await message.bot.send_message(target_tid, f"{prefix}{message.text}", parse_mode="HTML")
        except Exception as e:
            await message.answer(f"⚠️ Сообщение не доставлено: собеседник недоступен.")

@router.message(SupportStates.entering_message)
async def process_support_msg(message: Message, state: FSMContext):
    msg_text = message.text
    if not msg_text or msg_text == "📩 Обратная связь":
        return

    async with async_session_maker() as session:
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one()
        new_ticket = SupportTicket(user_id=user.id, message=msg_text)
        session.add(new_ticket)
        await session.flush()
        ticket_id = new_ticket.id
        await session.commit()

    # Notify Admins
    admin_text = (
        f"📩 <b>Новое обращение #{ticket_id}</b>\n"
        f"👤 От пользователя: <code>#{user.id}</code>\n\n"
        f"💬 Текст: {msg_text}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Ответить (разово)", callback_data=f"admin_reply:{ticket_id}")],
        [InlineKeyboardButton(text="💎 Начать диалог", callback_data=f"start_chat:{message.from_user.id}")]
    ])

    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, admin_text, parse_mode="HTML", reply_markup=kb)
        except Exception: pass

    await state.clear()
    await message.answer("✅ Ваше сообщение отправлено администрации. Ожидайте ответа!")

# --- ADMIN CHAT LOGIC ---
@router.callback_query(F.data.startswith("start_chat:"))
async def admin_start_chat(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMIN_IDS: return
    user_tid = int(callback.data.split(":")[1])
    admin_tid = callback.from_user.id
    
    async with async_session_maker() as session:
        # Close any previous active chats for this user/admin (just in case)
        await session.execute(
            update(SupportChat).where(
                and_(SupportChat.is_active == True, (SupportChat.user_tid == user_tid) | (SupportChat.admin_tid == admin_tid))
            ).values(is_active=False)
        )
        
        new_chat = SupportChat(user_tid=user_tid, admin_tid=admin_tid, is_active=True)
        session.add(new_chat)
        await session.commit()
    
    # Set states for both? 
    # AIOGram FSM is per user. We can't easily set user's state from here without dispatcher.
    # But we can handle it globally in middleware or here by checking DB in every message.
    # For now, let's just notify the user. When user sends message, we check DB.
    
    await state.set_state(SupportStates.active_chat)
    await callback.message.answer(
        "💎 <b>Диалог начат.</b>\nТеперь ваши сообщения будут пересылаться пользователю напрямую.",
        parse_mode="HTML",
        reply_markup=get_finish_chat_kb()
    )
    
    try:
        await callback.bot.send_message(
            user_tid,
            "💎 <b>Администратор начал с вами диалог.</b>\nТеперь вы можете общаться в реальном времени.",
            parse_mode="HTML",
            reply_markup=get_finish_chat_kb()
        )
    except: pass
    
    await callback.answer()

# --- ONE-OFF REPLY ---
@router.callback_query(F.data.startswith("admin_reply:"))
async def start_admin_reply(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMIN_IDS: return
    ticket_id = int(callback.data.split(":")[1])
    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state(SupportStates.admin_replying)
    await callback.message.answer(f"⌨️ Введите ответ на обращение #{ticket_id}:")
    await callback.answer()

@router.message(SupportStates.admin_replying)
async def process_admin_reply(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS: return
    data = await state.get_data()
    ticket_id = data['reply_ticket_id']
    
    async with async_session_maker() as session:
        ticket = (await session.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))).scalar_one_or_none()
        if not ticket:
            await message.answer("❌ Обращение не найдено.")
            await state.clear()
            return
            
        user_stmt = select(User).where(User.id == ticket.user_id)
        user = (await session.execute(user_stmt)).scalar_one()
        user_tid = user.telegram_id
        
        ticket.is_replied = True
        await session.commit()

    try:
        await message.bot.send_message(user_tid, f"📨 <b>Ответ от администрации:</b>\n\n{message.text}", parse_mode="HTML")
        await message.answer(f"✅ Ответ на обращение #{ticket_id} успешно доставлен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

    await state.clear()
