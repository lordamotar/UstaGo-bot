from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from bot.states import ReviewStates
from database.engine import async_session_maker
from database.models import User, Order, Bid, OrderStatus, MasterProfile, Review
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
        # f"Баланс: {user.points} баллов\n"
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
        for o in orders_active:
            text += f"\n📦 <b>{o.category.name}</b>\n📝 {o.description[:50]}...\n"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"✅ Завершить заказ №{o.id}", callback_data=f"client_complete_order:{o.id}")],
                [InlineKeyboardButton(text=f"❌ Отменить заказ №{o.id}", callback_data=f"client_cancel_order:{o.id}")]
            ])
            await message.answer(text, parse_mode="HTML", reply_markup=kb)

    if orders_new:
        text = "🆕 <b>Новые заявки (сбор откликов):</b>\n"
        for o in orders_new:
            text += f"\n📦 <b>{o.category.name}</b>\n📝 {o.description[:50]}...\n"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🔍 Детали заявки №{o.id}", callback_data=f"client_view_order:{o.id}")],
                [InlineKeyboardButton(text=f"❌ Отменить заявку №{o.id}", callback_data=f"client_cancel_order:{o.id}")]
            ])
            await message.answer(text, parse_mode="HTML", reply_markup=kb)

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
        
    status_icon = "🟢" if order.status == OrderStatus.ACTIVE else "⚪️" if order.status == OrderStatus.NEW else "✅" if order.status == OrderStatus.COMPLETED else "❌"
    text = f"{status_icon} <b>Заявка №{order.id}</b>\n"
    text += f"📝 Описание: {order.description}\n"
    text += f"💰 Бюджет: {order.budget or 'Договорная'}\n\n"
    
    if order.status == OrderStatus.ACTIVE:
        accepted_bid = next((b for b in order.bids if b.status == "accepted"), None)
        if accepted_bid:
            m_user = accepted_bid.master.user
            text += (
                f"✅ <b>Мастер выбран:</b> {m_user.full_name}\n"
                f"📱 Телефон: <code>{m_user.phone_number}</code>\n"
                f"Telegram: @{m_user.username if m_user.username else '—'}\n\n"
                "Выполняется работа над заказом."
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Завершить работу", callback_data=f"client_complete_order:{order.id}")],
                [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"client_cancel_order:{order.id}")]
            ])
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            return

    if not order.bids:
        text += "⏳ Откликов пока нет."
        await message.answer(text, parse_mode="HTML")
    else:
        text += f"🔔 <b>Отклики ({len(order.bids)}):</b>\n\n"
        await message.answer(text, parse_mode="HTML")
        
        for bid in order.bids:
            if order.status == OrderStatus.NEW and bid.status != "rejected":
                m_user = bid.master.user
                acc_badge = "🏅 " if bid.master.is_accredited else ""
                b_text = (
                    f"👷 <b>Мастер:</b> {acc_badge}{m_user.full_name} ({bid.master.rating}⭐)\n"
                    f"🏷️ Цена: {bid.suggested_price or 'Договорная'}\n"
                    f"📩 Сообщение: {bid.message or '—'}"
                )
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👷 Профиль мастера", callback_data=f"client_view_master:{bid.master_id}:{order_id}")],
                    [
                        InlineKeyboardButton(text="✅ Принять", callback_data=f"client_accept_bid:{bid.id}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"client_reject_bid:{bid.id}")
                    ]
                ])
                await message.answer(b_text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("client_reject_bid:"))
async def client_reject_bid_callback(callback: CallbackQuery):
    bid_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        stmt = select(Bid).options(joinedload(Bid.master).joinedload(MasterProfile.user)).where(Bid.id == bid_id)
        bid = (await session.execute(stmt)).scalar_one_or_none()
        if bid:
            bid.status = "rejected"
            master_tid = bid.master.user.telegram_id
            order_id = bid.order_id
            await session.commit()
            
            # Notify Master
            try:
                await callback.bot.send_message(
                    master_tid,
                    f"🔻 <b>Ваш отклик на заказ №{order_id} отклонен.</b>\n"
                    "Не расстраивайтесь, в списке есть еще много заказов!",
                    parse_mode="HTML"
                )
            except Exception: pass
            
            await callback.message.delete()
            await callback.answer("❌ Отклик отклонен.")
        else:
            await callback.answer("❌ Ошибка: отклик не найден.")

@router.callback_query(F.data.startswith("client_view_master:"))
async def client_view_master_details(callback: CallbackQuery):
    """Shows full master profile to a client who received a bid."""
    parts = callback.data.split(":")
    master_id = int(parts[1])
    order_id = int(parts[2])
    
    async with async_session_maker() as session:
        # 1. Load Master's info
        stmt = select(MasterProfile).options(
            selectinload(MasterProfile.user)
        ).where(MasterProfile.id == master_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        
        if not profile:
            await callback.answer("Master profile not found.")
            return
            
        # 2. Get Reviews
        rev_stmt = select(Review).where(Review.to_user_id == profile.user_id).order_by(Review.created_at.desc()).limit(5)
        reviews = (await session.execute(rev_stmt)).scalars().all()
        
    acc_badge = "🏅 " if profile.is_accredited else ""
    text = (
        f"👷 <b>Профиль мастера: {acc_badge}{profile.user.full_name}</b>\n\n"
        f"⭐ Рейтинг: {profile.rating:.1f} / 5.0\n"
        f"⏳ Стаж: {profile.experience or '—'}\n\n"
        f"📝 <b>О себе:</b>\n{profile.description or '—'}\n\n"
    )
    
    if reviews:
        text += "💬 <b>Последние отзывы:</b>\n"
        for r in reviews:
            stars = "⭐" * r.rating
            text += f"\n{stars}\n«{r.comment}»\n"
    else:
        text += "\n💬 Отзывов пока нет.\n"
        
    # Photos
    if profile.work_photos:
        media = [InputMediaPhoto(media=p) for p in profile.work_photos]
        await callback.message.answer_media_group(media=media)
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 Назад к списку откликов", callback_data=f"client_view_order:{order_id}")
    ]])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

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
        # Load Bid with ALL necessary relations
        stmt = select(Bid).options(
            joinedload(Bid.master).joinedload(MasterProfile.user),
            joinedload(Bid.order).options(
                joinedload(Order.client),
                joinedload(Order.category),
                joinedload(Order.district)
            )
        ).where(Bid.id == bid_id)
        
        res = await session.execute(stmt)
        bid = res.scalar_one_or_none()
        
        if not bid:
            await message.answer("❌ Отклик не найден.")
            return

        order = bid.order
        if order.status != OrderStatus.NEW:
            status_text = "в работе" if order.status == OrderStatus.ACTIVE else "уже завершен" if order.status == OrderStatus.COMPLETED else "отменен"
            await message.answer(f"⚠️ Вы не можете принять мастера: заказ уже {status_text}.")
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить работу", callback_data=f"client_complete_order:{order.id}")],
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"client_cancel_order:{order.id}")]
    ])
    await message.answer(client_text, parse_mode="HTML", reply_markup=kb)
    
    # Notify Master with FULL order details
    master_text = (
        f"🎉 <b>Клиент принял ваш отклик на заказ №{order.id}!</b>\n\n"
        f"📦 <b>Заказ №{order.id}: {order.category.name}</b>\n\n"
        f"📝 {order.description}\n"
        f"💰 Бюджет: {order.budget or 'Договорная'}\n"
        f"📍 Район: {order.district.name if order.district else '—'}\n"
        f"👤 Клиент: {client_user.full_name}\n"
        f"📱 Телефон: <code>{client_user.phone_number}</code>\n"
        f"Telegram: @{client_user.username if client_user.username else '—'}\n\n"
        "🟢 <b>Свяжитесь с клиентом прямо сейчас!</b>"
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

@router.callback_query(F.data.startswith("client_cancel_order:"))
async def client_cancel_order_callback(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Да, отменить", callback_data=f"client_confirm_cancel:{order_id}")],
        [InlineKeyboardButton(text="🔙 Не отменять", callback_data=f"client_view_order:{order_id}")]
    ])
    await callback.message.edit_text(f"❓ Вы уверены, что хотите отменить <b>заказ №{order_id}</b>?", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("client_confirm_cancel:"))
async def client_confirm_cancel_order_callback(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        # Load order with relations
        stmt = select(Order).options(
            selectinload(Order.bids).joinedload(Bid.master).joinedload(MasterProfile.user)
        ).where(Order.id == order_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        
        if not order:
            await callback.answer("❌ Заказ не найден.")
            return
            
        if order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
            await callback.answer("⚠️ Вы не можете отменить этот заказ.")
            return
            
        old_status = order.status
        order.status = OrderStatus.CANCELLED
        
        # Notify all masters who bid on this order
        bidders = [(b.master.user.telegram_id, b.status) for b in order.bids]
        
        await session.commit()
        
    await callback.message.edit_text(f"🗑️ Заказ №{order_id} успешно отменен.")
    
    # Notify Master(s) and Refund Points
    from database.models import Transaction, TransactionType
    for tid, status in bidders:
        try:
            # Return points (50 per bid)
            async with async_session_maker() as session:
                master_user = (await session.execute(select(User).where(User.telegram_id == tid))).scalar_one_or_none()
                if master_user:
                    master_user.points += 50
                    session.add(Transaction(
                        user_id=master_user.id, 
                        amount=50, 
                        type=TransactionType.REFUND,
                        description=f"Возврат баллов: заказ №{order_id} отменен клиентом"
                    ))
                    await session.commit()

            status_desc = "был в работе" if status == "accepted" else "был предложен"
            await callback.bot.send_message(
                tid,
                f"🗑️ <b>Заявка №{order_id} была удалена клиентом.</b>\n"
                f"Ваш отклик {status_desc}.\n"
                "💰 <b>50 баллов возвращены на ваш баланс.</b>\n\n"
                "Вы по-прежнему можете откликаться на другие заказы!",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error notifying/refunding master {tid}: {e}")
        
    await callback.answer("Заказ отменен. Баллы мастерам возвращены.")

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
    from sqlalchemy import func
    async with async_session_maker() as session:
        # Find the master and his profile
        stmt = select(Bid).options(
            joinedload(Bid.master).joinedload(MasterProfile.user)
        ).where(Bid.order_id == order_id, Bid.status == 'accepted')
        res = await session.execute(stmt)
        bid = res.scalar_one_or_none()
        
        if bid:
            # Need real user id of client
            user_stmt = select(User).where(User.telegram_id == message.from_user.id)
            user = (await session.execute(user_stmt)).scalar_one()
            
            # Save new review
            new_review = Review(
                order_id=order_id,
                from_user_id=user.id,
                to_user_id=bid.master.user_id,
                rating=rating,
                comment=comment
            )
            session.add(new_review)
            await session.flush()
            
            # RECALCULATE average rating
            avg_stmt = select(func.avg(Review.rating)).where(Review.to_user_id == bid.master.user_id)
            new_avg_rating = (await session.execute(avg_stmt)).scalar() or 0
            
            # Update MasterProfile rating
            profile = bid.master
            profile.rating = float(new_avg_rating)
            
            await session.commit()

    await message.answer("🙏 Спасибо за ваш отзыв! Это помогает мастерам становиться лучше.")
    await state.clear()
    
    from bot.core.config import config
    is_admin = message.from_user.id in config.ADMIN_IDS
    from bot.keyboards.client import get_client_main_menu
    await message.answer("Вы в главном меню.", reply_markup=get_client_main_menu(is_admin=is_admin))
