from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload, joinedload
from database.engine import async_session_maker
from database.models import User, MasterProfile, MasterStatus, Category, Order, Bid, OrderStatus, Transaction, TransactionType, Review, District
from bot.keyboards.master import (
    get_master_main_menu, get_profile_menu, get_orders_menu, 
    get_balance_menu, get_settings_menu, build_districts_keyboard,
    get_edit_profile_inline_keyboard, get_photo_management_keyboard
)
from bot.states import EditProfileStates, ManagePhotoStates, SettingsStates, BidStates, ReviewStates
from bot.core.config import config

router = Router()

@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message):
    """Shows master profile and submenu."""
    async with async_session_maker() as session:
        stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.chat.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.master_profile:
            await message.answer("❌ Профиль мастера не найден. Попробуйте зарегистрироваться заново.")
            return

        profile = user.master_profile
        points = user.points
        
        status_emoji = "🎗️ Аккредитован" if profile.status == MasterStatus.APPROVED else "⏳ На модерации"
        
        text = (
            f"👤 <b>Ваш профиль</b>\n"
            f"Имя: {user.full_name}\n"
            f"Рейтинг: {profile.rating:.1f} ⭐\n"
            f"Статус: {status_emoji}\n"
            f"Баланс: {points} баллов\n\n"
            f"Описание: {profile.description or '—'}\n"
            f"Стаж: {profile.experience or '—'}"
        )
        
        await message.answer(text, parse_mode="HTML", reply_markup=get_profile_menu())

# --- EDIT PROFILE HANDLERS ---
@router.message(F.text == "✏️ Редактировать")
async def edit_profile_start(message: Message):
    await message.answer("🛠 Что вы хотите изменить?", reply_markup=get_edit_profile_inline_keyboard())

@router.callback_query(F.data == "edit_name")
async def edit_name_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfileStates.editing_name)
    await callback.message.edit_text("📝 Введите ваше новое имя:")
    await callback.answer()

@router.message(EditProfileStates.editing_name)
async def process_edit_name(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        stmt = update(User).where(User.telegram_id == message.chat.id).values(full_name=message.text)
        await session.execute(stmt)
        await session.commit()
    
    await state.clear()
    await message.answer(f"✅ Имя успешно изменено на: <b>{message.text}</b>", parse_mode="HTML")
    await show_profile(message)

@router.callback_query(F.data == "edit_categories")
async def edit_categories_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfileStates.selecting_categories)
    
    from bot.keyboards.registration import build_categories_keyboard
    async with async_session_maker() as session:
        stmt = select(User).options(selectinload(User.master_profile).selectinload(MasterProfile.categories)).where(User.telegram_id == callback.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        selected_ids = [c.id for c in user.master_profile.categories]
        res_cats = await session.execute(select(Category))
        all_cats = res_cats.scalars().all()
        cats_list = [{"id": c.id, "name": c.name} for c in all_cats]
        
        await state.update_data(all_categories=cats_list, selected_categories=selected_ids)
        keyboard = build_categories_keyboard(set(selected_ids), cats_list)
        await callback.message.edit_text("📁 Выберите категории услуг (можно несколько):", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(EditProfileStates.selecting_categories, F.data.startswith("cat_toggle:"))
async def edit_toggle_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("selected_categories", []))
    cats_list = data.get("all_categories", [])
    
    if cat_id in selected:
        selected.remove(cat_id)
    else:
        selected.add(cat_id)
        
    await state.update_data(selected_categories=list(selected))
    from bot.keyboards.registration import build_categories_keyboard
    await callback.message.edit_reply_markup(reply_markup=build_categories_keyboard(selected, cats_list))
    await callback.answer()

@router.callback_query(EditProfileStates.selecting_categories, F.data == "cat_save")
async def edit_save_categories(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_ids = data.get("selected_categories", [])
    
    if not selected_ids:
        await callback.answer("⚠️ Выберите хотя бы одну категорию!", show_alert=True)
        return

    async with async_session_maker() as session:
        stmt = select(MasterProfile).join(User).where(User.telegram_id == callback.from_user.id).options(selectinload(MasterProfile.categories))
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        cat_stmt = select(Category).where(Category.id.in_(selected_ids))
        new_cats = (await session.execute(cat_stmt)).scalars().all()
        profile.categories = list(new_cats)
        await session.commit()

    await state.clear()
    await callback.message.edit_text("✅ Категории успешно обновлены!")
    await show_profile(callback.message)
    await callback.answer()

@router.callback_query(F.data == "edit_description")
async def edit_description_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfileStates.editing_description)
    await callback.message.edit_text("📝 Опишите ваш опыт и услуги (несколько предложений):")
    await callback.answer()

@router.message(EditProfileStates.editing_description)
async def process_edit_description(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        res = await session.execute(select(MasterProfile).join(User).where(User.telegram_id == message.chat.id))
        profile = res.scalar_one_or_none()
        if profile:
            profile.description = message.text
            await session.commit()
    
    await state.clear()
    await message.answer("✅ Описание успешно обновлено!")
    await show_profile(message)

# --- PHOTO MANAGEMENT ---
@router.message(F.text == "📸 Фото")
@router.message(F.text == "📸 Фото")
async def manage_master_photos(message: Message):
    async with async_session_maker() as session:
        stmt = select(MasterProfile).join(User).where(User.telegram_id == message.chat.id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        
        photos = profile.work_photos or []
        count = len(photos)
        
        await message.answer(
            f"📸 <b>Ваше портфолио</b> ({count}/3 фото):\n\n"
            "Вы можете добавить новые фото или удалить существующие по одному.",
            reply_markup=get_photo_management_keyboard(count),
            parse_mode="HTML"
        )
        
        for idx, p_id in enumerate(photos):
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                 InlineKeyboardButton(text="🗑️ Удалить это фото", callback_data=f"del_photo:{idx}")
            ]])
            await message.bot.send_photo(message.chat.id, photo=p_id, reply_markup=kb)

@router.callback_query(F.data.startswith("del_photo:"))
async def delete_photo_callback(callback: CallbackQuery):
    idx = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        stmt = select(MasterProfile).join(User).where(User.telegram_id == callback.from_user.id)
        profile = (await session.execute(stmt)).scalar_one_or_none()
        
        if profile and profile.work_photos:
            photos = list(profile.work_photos)
            if 0 <= idx < len(photos):
                photos.pop(idx)
                profile.work_photos = photos
                await session.commit()
                await callback.message.delete()
                await callback.answer("✅ Фото удалено!")
            else:
                await callback.answer("❌ Ошибка: фото не найдено.")
        else:
            await callback.answer("❌ Профиль не найден.")

@router.callback_query(F.data == "add_photos")
async def add_photos_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ManagePhotoStates.adding_photos)
    await callback.message.edit_text("📤 Отправьте до 3 фото ваших работ одно за другим:")
    await callback.answer()

@router.message(ManagePhotoStates.adding_photos, F.photo)
async def process_adding_photos(message: Message, state: FSMContext):
    # Safety check: if state is already being cleared, ignore
    current_state = await state.get_state()
    if current_state != ManagePhotoStates.adding_photos:
        return

    data = await state.get_data()
    temp_photos = data.get("temp_photos", [])
    
    # Don't add more than 3
    if len(temp_photos) >= 3:
        return

    temp_photos.append(message.photo[-1].file_id)
    await state.update_data(temp_photos=temp_photos)
    
    if len(temp_photos) >= 3:
        # Clear state immediately to prevent concurrent calls
        await state.set_state(None)
        await finish_adding_photos(message, state, override_photos=temp_photos)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="finish_add_photos")]])
        await message.answer(f"✅ Фото получено! ({len(temp_photos)}/3). Скиньте еще или нажмите Готово.", reply_markup=kb)

@router.callback_query(F.data == "finish_add_photos")
async def finish_adding_photos_callback(callback: CallbackQuery, state: FSMContext):
    # Double check state
    if await state.get_state() == ManagePhotoStates.adding_photos:
        await state.set_state(None)
        await finish_adding_photos(callback.message, state)
    await callback.answer()

async def finish_adding_photos(message: Message, state: FSMContext, override_photos: list = None):
    data = await state.get_data()
    new_photos = override_photos if override_photos else data.get("temp_photos", [])
    async with async_session_maker() as session:
        res = await session.execute(select(MasterProfile).join(User).where(User.telegram_id == message.chat.id))
        profile = res.scalar_one_or_none()
        if profile:
            profile.work_photos = new_photos[:3]
            await session.commit()
    await state.clear()
    await message.answer("✅ Фото успешно обновлены!")
    await show_profile(message)

# (Removed old delete_photos bulk handler)

@router.callback_query(F.data == "profile_back")
async def profile_back_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()

# --- ORDERS MANAGEMENT ---
@router.message(F.text == "📋 Мои заказы")
async def show_orders_menu(message: Message):
    await message.answer("📋 Выберите категорию заказов:", reply_markup=get_orders_menu())

@router.message(F.text == "🔄 Доступные заказы")
async def show_available_orders(message: Message):
    async with async_session_maker() as session:
        stmt = select(User).options(selectinload(User.master_profile).selectinload(MasterProfile.categories)).where(User.telegram_id == message.chat.id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user or not user.master_profile: return
        cat_ids = [c.id for c in user.master_profile.categories]
        order_stmt = select(Order).options(selectinload(Order.category), selectinload(Order.district)).where(
            Order.category_id.in_(cat_ids), Order.status == OrderStatus.NEW
        ).order_by(Order.created_at.desc())
        orders = (await session.execute(order_stmt)).scalars().all()
    if not orders:
        await message.answer("🔄 Пока нет новых заказов в ваших категориях.", reply_markup=get_orders_menu())
        return
    text = f"🔄 <b>Доступные заказы ({len(orders)}):</b>\n\n"
    keyboard = []
    for o in orders:
        text += f"📦 <b>{o.category.name}</b>\n💰 Бюджет: {o.budget or 'Договорная'}\n📍 {o.district.name if o.district else '—'}\n\n"
        keyboard.append([InlineKeyboardButton(text=f"📥 Заказ №{o.id}", callback_data=f"master_view_order:{o.id}")])
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.message(F.text == "⏳ Мои активные заказы")
async def show_active_orders(message: Message):
    async with async_session_maker() as session:
        stmt = select(MasterProfile).join(User).where(User.telegram_id == message.chat.id)
        master = (await session.execute(stmt)).scalar_one_or_none()
        if not master: return
        stmt = select(Order).join(Bid).where(Bid.master_id == master.id, Bid.status == 'accepted', Order.status == OrderStatus.ACTIVE).options(selectinload(Order.category), selectinload(Order.client)).order_by(Order.created_at.desc())
        orders = (await session.execute(stmt)).scalars().all()
    if not orders:
        await message.answer("⏳ У вас пока нет активных заказов.", reply_markup=get_orders_menu())
        return
    text = "⚡️ <b>Заказы в работе:</b>\n"
    keyboard = []
    for o in orders:
        link = f" (@{o.client.username})" if o.client.username else ""
        text += (
            f"\n🏷 <b>{o.category.name}</b>\n"
            f"👤 Клиент: {o.client.full_name}{link}\n"
            f"📱 Телефон: <code>{o.client.phone_number}</code>\n"
        )
        keyboard.append([InlineKeyboardButton(text=f"✅ Завершить заказ №{o.id}", callback_data=f"master_request_complete:{o.id}")])
    
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("master_request_complete:"))
async def master_request_complete_callback(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        stmt = select(Order).options(selectinload(Order.client)).where(Order.id == order_id)
        order = (await session.execute(stmt)).scalar_one_or_none()
        if not order: return
        client_tg_id = order.client.telegram_id

    # Notify Client
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⭐ Подтвердить и оценить", callback_data=f"client_complete_order:{order_id}")
    ]])
    
    try:
        await callback.bot.send_message(
            client_tg_id,
            f"👷 Мастер объявил о завершении <b>заказа №{order_id}</b>.\n\n"
            f"Если работа выполнена, пожалуйста, подтвердите это и оставьте отзыв мастеу.",
            parse_mode="HTML",
            reply_markup=kb
        )
        await callback.answer("✅ Запрос отправлен клиенту!", show_alert=True)
        await callback.message.edit_text("⏳ Запрос на завершение отправлен клиенту. Ждем его подтверждения.")
    except Exception:
        await callback.answer("❌ Ошибка при уведомлении клиента.")

@router.message(F.text == "✅ Выполненные заказы")
async def show_completed_orders(message: Message):
    async with async_session_maker() as session:
        stmt = select(MasterProfile).join(User).where(User.telegram_id == message.chat.id)
        master = (await session.execute(stmt)).scalar_one_or_none()
        if not master: return
        stmt = select(Order).join(Bid).where(Bid.master_id == master.id, Bid.status == 'accepted', Order.status == OrderStatus.COMPLETED).options(selectinload(Order.category)).order_by(Order.created_at.desc())
        orders = (await session.execute(stmt)).scalars().all()
    if not orders:
        await message.answer("✅ У вас пока нет выполненных заказов.")
        return
    text = "✅ <b>История завершенных заказов:</b>\n"
    for o in orders:
        text += f"\n📦 <b>{o.category.name}</b>\n📅 {o.created_at.strftime('%d.%m.%Y')}\n"
    await message.answer(text, parse_mode="HTML")

# --- ORDER DETAILS ---
@router.callback_query(F.data.startswith("master_view_order:"))
async def master_view_order_callback(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        stmt = select(Order).options(selectinload(Order.category), selectinload(Order.district)).where(Order.id == order_id)
        order = (await session.execute(stmt)).scalar_one_or_none()
        
    if not order:
        await callback.answer("Заказ не найден.")
        return
        
    # Show photos if exist
    if order.photo_ids:
        try:
            media = [InputMediaPhoto(media=p) for p in order.photo_ids]
            await callback.message.answer_media_group(media=media)
        except Exception:
            pass
            
    text = (
        f"📦 <b>Заказ №{order.id}: {order.category.name}</b>\n\n"
        f"📝 {order.description}\n"
        f"💰 Бюджет: {order.budget or 'Договорная'}\n"
        f"📍 Район: {order.district.name if order.district else '—'}\n\n"
        f"🏷️ <b>Стоимость отклика: 50 баллов.</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Откликнуться", callback_data=f"start_bid:{order.id}")
    ]])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

# --- BIDDING FLOW ---
@router.callback_query(F.data.startswith("start_bid:"))
async def start_bid_flow(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        user = (await session.execute(select(User).where(User.telegram_id == callback.from_user.id))).scalar_one_or_none()
        if not user or user.points < 50:
            await callback.answer("❌ Недостаточно баллов (нужно 50).", show_alert=True)
            return
    await state.update_data(bid_order_id=order_id)
    await state.set_state(BidStates.entering_price)
    await callback.message.answer("💰 <b>Введите вашу цену (в тенге):</b>", parse_mode="HTML")
    await callback.answer()

@router.message(BidStates.entering_price)
async def process_bid_price(message: Message, state: FSMContext):
    await state.update_data(bid_price=message.text)
    await state.set_state(BidStates.entering_message)
    await message.answer("📩 <b>Напишите сообщение для клиента:</b>", parse_mode="HTML")

@router.message(BidStates.entering_message)
async def process_bid_message(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id, price_str = data['bid_order_id'], data['bid_price']
    async with async_session_maker() as session:
        user = (await session.execute(select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.chat.id))).scalar()
        user.points -= 50
        session.add(Transaction(user_id=user.id, amount=-50, type=TransactionType.CONTACT_FEE, description=f"Отклик на заказ №{order_id}"))
        import re
        price_val = int("".join(re.findall(r'\d+', price_str))) if re.findall(r'\d+', price_str) else 0
        bid = Bid(order_id=order_id, master_id=user.master_profile.id, suggested_price=price_val, message=message.text)
        session.add(bid)
        await session.flush()
        order = (await session.execute(select(Order).options(selectinload(Order.client)).where(Order.id == order_id))).scalar()
        client_tg_id = order.client.telegram_id
        await session.commit()
    await message.answer("✅ Отклик отправлен!")
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Детали и Принять", callback_data=f"client_view_order:{order_id}")]])
    await message.bot.send_message(client_tg_id, f"🔔 <b>Новый отклик!</b>\n💰 Цена: {price_str}\n👷 Мастер: {user.full_name}\n📩: {message.text[:100]}...", parse_mode="HTML", reply_markup=kb)

# --- OTHER HANDLERS ---
@router.message(F.text == "📊 Статистика")
async def show_stats_handler(message: Message):
    async with async_session_maker() as session:
        # Get user and master profile
        stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.chat.id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user or not user.master_profile: return
        
        master_id = user.master_profile.id
        
        # 1. Count completed orders
        completed = (await session.execute(
            select(func.count(Order.id))
            .join(Bid)
            .where(Bid.master_id == master_id, Bid.status == 'accepted', Order.status == OrderStatus.COMPLETED)
        )).scalar() or 0
        
        # 2. Count active orders
        active = (await session.execute(
            select(func.count(Order.id))
            .join(Bid)
            .where(Bid.master_id == master_id, Bid.status == 'accepted', Order.status == OrderStatus.ACTIVE)
        )).scalar() or 0
        
        # 3. Calculate total lifetime points (non-negative transactions)
        total_earned = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(Transaction.user_id == user.id, Transaction.amount > 0)
        )).scalar() or 0
        
        # 4. Average Rating
        avg_rating = (await session.execute(
            select(func.avg(Review.rating))
            .join(User, Review.to_user_id == User.id)
            .where(User.telegram_id == message.chat.id)
        )).scalar() or 0
        
    reg_date = user.created_at.strftime("%d.%m.%Y")
    
    text = (
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"✅ Выполнено заказов: <b>{completed}</b>\n"
        f"⚡️ Сейчас в работе: <b>{active}</b>\n"
        f"💰 Заработано баллов (всего): <b>{total_earned}</b>\n"
        f"⭐ Средний рейтинг: <b>{avg_rating:.1f}</b>\n\n"
        f"🗓 В сервисе с: <b>{reg_date}</b>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🎗️ Мой статус")
async def show_status_handler(message: Message):
    async with async_session_maker() as session:
        status = (await session.execute(select(MasterProfile.status).join(User).where(User.telegram_id == message.chat.id))).scalar()
    txt = "🎗️ <b>Аккредитован</b>" if status == MasterStatus.APPROVED else "⏳ <b>На модерации</b>" if status == MasterStatus.PENDING else "❌ <b>Отклонен</b>"
    await message.answer(txt, parse_mode="HTML")

@router.message(F.text == "⭐ Рейтинг и отзывы")
async def show_rating_handler(message: Message):
    async with async_session_maker() as session:
        reviews = (await session.execute(select(Review).join(User, Review.to_user_id == User.id).where(User.telegram_id == message.chat.id).order_by(Review.created_at.desc()))).scalars().all()
        avg = (await session.execute(select(func.avg(Review.rating)).join(User, Review.to_user_id == User.id).where(User.telegram_id == message.chat.id))).scalar() or 0
    if not reviews:
        await message.answer("⭐ Еще нет отзывов.")
        return
    text = f"⭐ <b>Рейтинг: {avg:.1f}/5.0</b>\n\n💬 <b>Последние отзывы:</b>\n"
    for r in reviews[:10]: text += f"\n{'⭐'*r.rating} ({r.created_at.strftime('%d.%m.%Y')})\n<i>«{r.comment}»</i>\n"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "💰 Баланс")
async def show_balance_handler(message: Message):
    async with async_session_maker() as session:
        p = (await session.execute(select(User.points).where(User.telegram_id == message.chat.id))).scalar() or 0
    
    text = (
        f"💰 <b>Ваш баланс: {p} баллов</b>\n\n"
        f"🏷️ Стоимость одного отклика: 50 баллов.\n\n"
        f"💳 <b>Как пополнить баланс?</b>\n"
        f"Переведите необходимую сумму на Kaspi (по номеру +7775...) и отправьте скриншот в поддержку @admin. "
        f"1 тенге = 1 балл."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_balance_menu())

@router.message(F.text == "📜 История операций")
async def show_transactions_handler(message: Message):
    async with async_session_maker() as session:
        stmt = select(Transaction).join(User).where(User.telegram_id == message.chat.id).order_by(Transaction.created_at.desc()).limit(10)
        txs = (await session.execute(stmt)).scalars().all()
    
    if not txs:
        await message.answer("📜 У вас пока нет операций по счету.")
        return
        
    text = "📜 <b>Последние 10 операций:</b>\n"
    for t in txs:
        sign = "+" if t.amount > 0 else ""
        date = t.created_at.strftime("%d.%m %H:%M")
        text += f"\n📅 {date} | <b>{sign}{t.amount}</b>\n└ {t.description or '—'}"
        
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "⚙️ Настройки")
async def show_settings_handler(message: Message):
    await message.answer("⚙️ Настройки профиля:", reply_markup=get_settings_menu())

@router.message(F.text == "🏠 Выход в главное меню")
async def exit_to_main(message: Message):
    from bot.handlers.start import get_role_keyboard
    is_admin = message.chat.id in config.ADMIN_IDS
    await message.answer("🏠 Вы вернулись в главное меню.", reply_markup=get_role_keyboard(is_admin=is_admin))

@router.message(F.text == "🔙 Назад в меню")
async def back_to_master_main(message: Message):
    is_admin = message.chat.id in config.ADMIN_IDS
    await message.answer("Главное меню мастера:", reply_markup=get_master_main_menu(is_admin=is_admin))

@router.message(F.text == "🆘 Помощь")
async def show_help(message: Message):
    await message.answer("🆘 Нужна помощь? Свяжитесь с @admin", parse_mode="HTML")

@router.message(F.text == "🔗 Рефералы")
async def show_refs(message: Message):
    bot = await message.bot.get_me()
    link = f"https://t.me/{bot.username}?start=ref_{message.chat.id}"
    await message.answer(f"🔗 Ваша ссылка:\n`{link}`\n\nПолучайте бонусы за приглашение коллег!", parse_mode="Markdown")

# --- SETTINGS TOGGLES ---
@router.message(F.text == "🔔 Уведомления")
async def toggle_notif(m: Message):
    async with async_session_maker() as session:
        u = (await session.execute(select(User).where(User.telegram_id == m.chat.id))).scalar()
        u.notifications_enabled = not u.notifications_enabled
        await session.commit()
    await m.answer(f"🔔 Уведомления: {'ВКЛ' if u.notifications_enabled else 'ВЫКЛ'}")

@router.message(F.text == "🚫 Режим «Не беспокоить»")
async def start_dnd_setup(m: Message, state: FSMContext):
    async with async_session_maker() as session:
        u = (await session.execute(select(User).where(User.telegram_id == m.chat.id))).scalar()
    
    current = f"{u.dnd_start or '—'} - {u.dnd_end or '—'}"
    await m.answer(
        f"🌙 <b>Режим «Тишины» (DND)</b>\n"
        f"Текущее нерабочее время: <code>{current}</code>\n\n"
        f"Введите время <b>начала</b> тишины (например, 18:00) или напишите «выкл» для сброса:",
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.entering_dnd_start)

@router.message(SettingsStates.entering_dnd_start)
async def process_dnd_start(m: Message, state: FSMContext):
    if m.text.lower() == "выкл":
        async with async_session_maker() as session:
            await session.execute(update(User).where(User.telegram_id == m.chat.id).values(dnd_start=None, dnd_end=None))
            await session.commit()
        await m.answer("✅ Режим тишины полностью отключен.")
        await state.clear()
        return
        
    # Check format HH:MM
    import re
    if not re.match(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", m.text):
        await m.answer("⚠️ Ошибка формата. Введите время в формате ЧЧ:ММ (например, 18:00):")
        return
        
    await state.update_data(dnd_start=m.text)
    await m.answer(f"⏳ Начало тишины: {m.text}. Теперь введите время <b>окончания</b> (например, 08:00):")
    await state.set_state(SettingsStates.entering_dnd_end)

@router.message(SettingsStates.entering_dnd_end)
async def process_dnd_end(m: Message, state: FSMContext):
    # Check format HH:MM
    import re
    if not re.match(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", m.text):
        await m.answer("⚠️ Ошибка формата. Введите время в формате ЧЧ:ММ (например, 08:00):")
        return
        
    data = await state.get_data()
    start = data['dnd_start']
    end = m.text
    
    async with async_session_maker() as session:
        await session.execute(update(User).where(User.telegram_id == m.chat.id).values(dnd_start=start, dnd_end=end))
        await session.commit()
        
    await m.answer(f"✅ Режим тишины установлен: с <b>{start}</b> до <b>{end}</b>.", parse_mode="HTML")
    await state.clear()
    await back_to_master_main(m)

@router.message(F.text == "🔑 Сменить статус видимости")
async def toggle_visibility(m: Message):
    async with async_session_maker() as session:
        u = (await session.execute(select(User).where(User.telegram_id == m.chat.id))).scalar()
        u.visible_for_new_orders = not u.visible_for_new_orders
        status = "ВИДИМ" if u.visible_for_new_orders else "СКРЫТ (вы не получаете уведомлений)"
        await session.commit()
    await m.answer(f"🕵️ Ваш статус: {status}")

@router.message(F.text == "📍 Районы работы")
async def manage_districts(m: Message, state: FSMContext):
    async with async_session_maker() as s:
        u = (await s.execute(select(User).options(selectinload(User.master_profile).selectinload(MasterProfile.districts)).where(User.telegram_id == m.chat.id))).scalar()
        ds = (await s.execute(select(District))).scalars().all()
        all_ds = [d.name for d in ds]
        sel_ds = [d.name for d in u.master_profile.districts]
    await state.set_state(SettingsStates.choosing_districts)
    await state.update_data(selected_districts=sel_ds, all_dist_names=all_ds)
    await m.answer("📍 Выберите районы:", reply_markup=build_districts_keyboard(sel_ds, all_ds))

@router.callback_query(SettingsStates.choosing_districts, F.data.startswith("dist_toggle:"))
async def toggle_dist(c: CallbackQuery, state: FSMContext):
    d_name = c.data.split(":")[1]
    data = await state.get_data()
    sel = set(data.get("selected_districts", []))
    if d_name in sel: sel.remove(d_name)
    else: sel.add(d_name)
    await state.update_data(selected_districts=list(sel))
    await c.message.edit_reply_markup(reply_markup=build_districts_keyboard(list(sel), data['all_dist_names']))
    await c.answer()

@router.callback_query(SettingsStates.choosing_districts, F.data == "dist_save")
async def save_dist(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    sel = data.get("selected_districts", [])
    async with async_session_maker() as s:
        u = (await s.execute(select(User).options(selectinload(User.master_profile).selectinload(MasterProfile.districts)).where(User.telegram_id == c.from_user.id))).scalar()
        ds = (await s.execute(select(District).where(District.name.in_(sel)))).scalars().all()
        u.master_profile.districts = list(ds)
        await s.commit()
    await state.clear()
    await c.message.edit_text("✅ Районы сохранены.")
    await c.answer()
