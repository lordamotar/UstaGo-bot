from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.states import ReviewStates
from database.engine import async_session_maker
from database.models import User, Order, Bid, OrderStatus, MasterProfile
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload

router = Router()

@router.message(F.text == "👤 Мой профиль")
async def show_client_profile(message: Message):
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
    if not user: return
    
    text = (
        f"👤 <b>Ваш профиль клиента</b>\n\n"
        f"Имя: {user.full_name}\n"
        f"Телефон: {user.phone_number or '—'}\n"
        f"Баланс: {user.points} баллов\n"
    )
    from bot.core.config import config
    is_admin = message.from_user.id in config.ADMIN_IDS
    from bot.keyboards.client import get_client_main_menu
    await message.answer(text, parse_mode="HTML", reply_markup=get_client_main_menu(is_admin=is_admin))

@router.message(F.text == "⏳ Мои заявки")
async def show_my_orders(message: Message):
    async with async_session_maker() as session:
        # Get User ID
        res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = res.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Пользователь не найден.")
            return

        # NEW Orders
        new_stmt = select(Order).options(selectinload(Order.category)).where(
            Order.client_id == user.id,
            Order.status == OrderStatus.NEW
        ).order_by(Order.created_at.desc())
        
        # ACTIVE Orders
        active_stmt = select(Order).options(selectinload(Order.category)).where(
            Order.client_id == user.id,
            Order.status == OrderStatus.ACTIVE
        ).order_by(Order.created_at.desc())
        
        orders_new = (await session.execute(new_stmt)).scalars().all()
        orders_active = (await session.execute(active_stmt)).scalars().all()
        
    if not orders_new and not orders_active:
        await message.answer("⏳ У вас пока нет заявок.")
        return
        
    if orders_active:
        text = "⚡️ <b>Активные заказы (в работе):</b>\n"
        keyboard = []
        for o in orders_active:
            text += f"\n📦 <b>{o.category.name}</b>\n📝 {o.description[:50]}...\n"
            keyboard.append([InlineKeyboardButton(text=f"✅ Завершить заказ №{o.id}", callback_data=f"client_complete_order:{o.id}")])
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

    if orders_new:
        text = "🆕 <b>Новые заявки (сбор откликов):</b>\n"
        keyboard = []
        for o in orders_new:
            text += f"\n📦 <b>{o.category.name}</b>\n📝 {o.description[:50]}...\n"
            keyboard.append([InlineKeyboardButton(text=f"🔍 Детали заявки №{o.id}", callback_data=f"client_view_order:{o.id}")])
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("client_view_order:"))
async def client_view_order_callback(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await process_view_order(callback.message, order_id)
    await callback.answer()

@router.message(F.text.startswith("/view_order_"))
async def view_order_bids_msg(message: Message):
    try:
        order_id = int(message.text.split("_")[-1])
        await process_view_order(message, order_id)
    except: pass

async def process_view_order(message: Message, order_id: int):
    async with async_session_maker() as session:
        stmt = select(Order).options(
            selectinload(Order.bids).joinedload(Bid.master).joinedload(MasterProfile.user)
        ).where(Order.id == order_id)
        
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        
    if not order:
        await message.answer("❌ Заявка не найдена.")
        return
        
    text = f"📋 <b>Заявка №{order.id}</b>\n"
    text += f"📝 Описание: {order.description}\n"
    text += f"💰 Бюджет: {order.budget or 'Договорная'}\n\n"
    
    if not order.bids:
        text += "⏳ Откликов пока нет."
        await message.answer(text, parse_mode="HTML")
    else:
        text += f"🔔 <b>Отклики ({len(order.bids)}):</b>\n\n"
        await message.answer(text, parse_mode="HTML")
        
        for bid in order.bids:
            m_user = bid.master.user
            b_text = (
                f"👷 <b>Мастер:</b> {m_user.full_name} ({bid.master.rating}⭐)\n"
                f"🏷️ Цена: {bid.suggested_price or 'Договорная'}\n"
                f"📩 Сообщение: {bid.message or '—'}"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Принять этого мастера", callback_data=f"client_accept_bid:{bid.id}")
            ]])
            await message.answer(b_text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("client_accept_bid:"))
async def client_accept_bid_callback(callback: CallbackQuery):
    bid_id = int(callback.data.split(":")[1])
    await process_accept_bid(callback.message, bid_id)
    await callback.answer()

@router.message(F.text.startswith("/accept_bid_"))
async def accept_master_bid_msg(message: Message):
    try:
        bid_id = int(message.text.split("_")[-1])
        await process_accept_bid(message, bid_id)
    except: pass

async def process_accept_bid(message: Message, bid_id: int):
    async with async_session_maker() as session:
        # Load Bid with relations
        stmt = select(Bid).options(
            joinedload(Bid.master).joinedload(MasterProfile.user),
            joinedload(Bid.order).joinedload(Order.client)
        ).where(Bid.id == bid_id)
        
        res = await session.execute(stmt)
        bid = res.scalar_one_or_none()
        
        if not bid:
            await message.answer("❌ Отклик не найден.")
            return

        order = bid.order
        if order.status == OrderStatus.ACTIVE:
            await message.answer("⚠️ Этот заказ уже в работе.")
            return

        master_user = bid.master.user
        client_user = order.client
        
        # Update statuses
        order.status = OrderStatus.ACTIVE
        bid.status = "accepted"
        
        await session.commit()
    
    # Notify Client
    client_text = (
        f"✅ <b>Вы приняли отклик мастера {master_user.full_name}!</b>\n\n"
        f"📱 Контакты мастера:\n"
        f"Телефон: <code>{master_user.phone_number}</code>\n"
        f"Telegram: @{master_user.username if master_user.username else '—'}\n\n"
        "Свяжитесь с мастером для уточнения деталей."
    )
    await message.answer(client_text, parse_mode="HTML")
    
    # Notify Master
    master_text = (
        f"🎉 <b>Клиент принял ваш отклик на заказ №{order.id}!</b>\n\n"
        f"👤 Клиент: {client_user.full_name}\n"
        f"📱 Телефон: <code>{client_user.phone_number}</code>\n"
        f"Telegram: @{client_user.username if client_user.username else '—'}\n\n"
        "Свяжитесь с клиентом прямо сейчас!"
    )
    await message.bot.send_message(master_user.telegram_id, master_text, parse_mode="HTML")

@router.callback_query(F.data.startswith("client_complete_order:"))
async def complete_order_handler(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        # Find order and accepted bid
        stmt = select(Order).options(
            selectinload(Order.bids).joinedload(Bid.master).joinedload(MasterProfile.user),
            selectinload(Order.client)
        ).where(Order.id == order_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        
        if not order or order.status != OrderStatus.ACTIVE:
            await callback.answer("❌ Заказ не найден или уже завершен.")
            return

        # Mark order as completed
        order.status = OrderStatus.COMPLETED
        
        # Find accepted master
        accepted_bid = next((b for b in order.bids if b.status == "accepted"), None)
        master_user = accepted_bid.master.user if accepted_bid else None
        client_user = order.client
        
        await session.commit()
    
    # Notify BOTH parties
    # Check who clicked
    is_master = (callback.from_user.id == master_user.telegram_id) if master_user else False
    
    if is_master:
        # Master finished. Notify master he is done and notify client to rate.
        await callback.message.answer("✅ Вы завершили работу над заказом! Ожидайте отзыв от клиента.")
        if client_user:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"start_review:{order_id}")
            ]])
            await callback.bot.send_message(
                client_user.telegram_id, 
                f"👷 Мастер завершил работу над вашим заказом №{order_id}. "
                "Пожалуйста, оцените качество услуги:", 
                reply_markup=kb
            )
    else:
        # Client finished. Start review flow immediately.
        await callback.message.answer("✅ Заказ завершен! Теперь вы можете оставить отзыв.")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate:{order_id}:{i}") for i in range(1, 6)
        ]])
        await callback.message.answer("Выберите оценку:", reply_markup=kb)
        
    await callback.answer()

@router.callback_query(F.data.startswith("start_review:"))
async def start_review_callback(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate:{order_id}:{i}") for i in range(1, 6)
    ]])
    await callback.message.edit_text("Выберите оценку работы мастера:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("rate:"))
async def handle_rating(callback: CallbackQuery, state: FSMContext):
    tokens = callback.data.split(":")
    order_id = int(tokens[1])
    rating = int(tokens[2])
    await state.update_data(review_order_id=order_id, rating=rating)
    
    await callback.message.edit_text(f"Оценка {rating}⭐ принята. Напишите краткий отзыв о работе:")
    await state.set_state(ReviewStates.comment)
    await callback.answer()

@router.message(ReviewStates.comment)
async def handle_review_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['review_order_id']
    rating = data['rating']
    comment = message.text
    
    from database.models import Review
    async with async_session_maker() as session:
        # Find the master
        from database.models import Bid # just in case
        stmt = select(Bid).options(joinedload(Bid.master)).where(Bid.order_id == order_id, Bid.status == 'accepted')
        res = await session.execute(stmt)
        bid = res.scalar_one_or_none()
        
        if bid:
            # Need real user id of client
            user_stmt = select(User).where(User.telegram_id == message.from_user.id)
            user = (await session.execute(user_stmt)).scalar_one()
            
            new_review = Review(
                order_id=order_id,
                from_user_id=user.id,
                to_user_id=bid.master.user_id,
                rating=rating,
                comment=comment
            )
            session.add(new_review)
            await session.commit()

    await message.answer("🙏 Спасибо за ваш отзыв! Это помогает мастерам становиться лучше.")
    await state.clear()
    
    from bot.core.config import config
    is_admin = message.from_user.id in config.ADMIN_IDS
    from bot.keyboards.client import get_client_main_menu
    await message.answer("Вы в главном меню.", reply_markup=get_client_main_menu(is_admin=is_admin))
