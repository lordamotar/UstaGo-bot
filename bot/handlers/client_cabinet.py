from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.engine import async_session_maker
from database.models import User, Order, Bid, OrderStatus, MasterProfile
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload

router = Router()

@router.message(F.text == "⏳ Мои заявки")
async def show_my_orders(message: Message):
    async with async_session_maker() as session:
        # Get User ID
        res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = res.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Пользователь не найден.")
            return

        stmt = select(Order).options(selectinload(Order.category)).where(
            Order.client_id == user.id,
            Order.status != OrderStatus.CANCELLED
        ).order_by(Order.created_at.desc())
        
        o_res = await session.execute(stmt)
        orders = o_res.scalars().all()
        
    if not orders:
        await message.answer("⏳ У вас пока нет активных заявок.")
        return
        
    text = "📋 <b>Ваши заявки:</b>\n"
    keyboard = []
    
    for o in orders:
        status_text = "🆕 Новая" if o.status == OrderStatus.NEW else "✅ Активна"
        text += f"\n📦 <b>{o.category.name}</b> ({status_text})\n📝 {o.description[:50]}...\n"
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
