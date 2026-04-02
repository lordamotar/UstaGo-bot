from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from database.engine import async_session_maker
from database.models import User, MasterProfile, MasterStatus, Category, Order, Bid, OrderStatus, Transaction, TransactionType
from bot.keyboards.master import (
    get_master_main_menu, get_profile_menu, get_orders_menu, 
    get_balance_menu, get_settings_menu, build_districts_keyboard
)
from bot.states import EditProfileStates, ManagePhotoStates, SettingsStates, BidStates
from aiogram.fsm.context import FSMContext

router = Router()

@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message):
    """
    Shows master profile and submenu.
    """
    from sqlalchemy.orm import selectinload
    async with async_session_maker() as session:
        stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.master_profile:
            await message.answer("❌ Профиль мастера не найден. Попробуйте зарегистрироваться заново.")
            return

        if not user:
            return

        profile = user.master_profile
        points = user.points
        
        status_emoji = "🎗️ Аккредитован" if profile.status == MasterStatus.APPROVED else "⏳ На модерации"
        
        # Format profile message
        text = (
            f"👤 *Ваш профиль*\n"
            f"Имя: {user.full_name}\n"
            f"Рейтинг: {profile.rating} ⭐\n"
            f"Статус: {status_emoji}\n"
            f"Баланс: {points} баллов\n\n"
            f"Описание: {profile.description or '—'}\n"
            f"Стаж: {profile.experience or '—'}"
        )
        
        await message.answer(text, parse_mode="Markdown", reply_markup=get_profile_menu())

@router.message(F.text == "📋 Мои заказы")
async def show_orders_menu(message: Message):
    await message.answer("📋 Выберите категорию заказов:", reply_markup=get_orders_menu())

@router.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    async with async_session_maker() as session:
        stmt = select(User.points).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        points = res.scalar() or 0
        
    text = (
        f"💰 Ваш баланс: {points} баллов\n\n"
        "Лицензия на один контакт: 50 баллов.\n"
        "Берется только в случае, если клиент выбрал вас."
    )
    await message.answer(text, reply_markup=get_balance_menu())

@router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message):
    await message.answer("⚙️ Настройки профиля и уведомлений:", reply_markup=get_settings_menu())

@router.message(F.text == "🔙 Назад в меню")
async def return_to_main_master_menu(message: Message):
    await message.answer("📋 Главное меню мастера", reply_markup=get_master_main_menu())

@router.message(F.text == "🏠 Выход в главное меню")
async def exit_to_client_mode(message: Message):
    from bot.handlers.start import get_role_keyboard
    await message.answer("🔄 Вы переключились в режим клиента.", reply_markup=get_role_keyboard())

# --- PROFILE SUBMENU ---
@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    # Mock stats for now
    text = (
        "📊 *Статистика*\n\n"
        "Выполнено заказов: 0\n"
        "Отзывов получено: 0\n"
        "Средний чек: —\n"
        "Доход за месяц: 0 баллов"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🎗️ Мой статус")
async def show_accreditation(message: Message):
    text = (
        "🎗️ *Аккредитация мастера*\n\n"
        "Ваш профиль проходит проверку модератором.\n"
        "Проверенные мастера получают:\n"
        "1. Приоритет в списке (выше других).\n"
        "2. Метка «Проверено» в профиле.\n"
        "3. Больше доверия от заказчиков."
    )
    await message.answer(text, parse_mode="Markdown")

from bot.states import EditProfileStates, ManagePhotoStates
from bot.keyboards.master import get_edit_profile_inline_keyboard, get_photo_management_keyboard
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

# --- MANAGE PROFILE ---
@router.message(F.text == "✏️ Редактировать")
async def edit_profile_menu(message: Message, state: FSMContext):
    await state.set_state(EditProfileStates.choosing_field)
    await message.answer(
        "✏️ *Редактирование анкеты*\n\nВыберите, что хотите изменить:",
        parse_mode="Markdown",
        reply_markup=get_edit_profile_inline_keyboard()
    )

@router.callback_query(EditProfileStates.choosing_field, F.data == "edit_name")
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfileStates.editing_name)
    await callback.message.edit_text("Введите новое имя (как оно будет отображаться клиентам):")
    await callback.answer()

@router.message(EditProfileStates.editing_name)
async def process_new_name(message: Message, state: FSMContext):
    new_name = message.text
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if user:
            user.full_name = new_name
            await session.commit()
    
    await state.set_state(EditProfileStates.choosing_field)
    await message.answer(f"✅ Имя успешно изменено на *{new_name}*", parse_mode="Markdown", reply_markup=get_edit_profile_inline_keyboard())

@router.callback_query(EditProfileStates.choosing_field, F.data == "edit_description")
async def edit_desc_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfileStates.editing_description)
    await callback.message.edit_text("Введите новое описание (до 500 символов):")
    await callback.answer()

@router.message(EditProfileStates.editing_description)
async def process_new_desc(message: Message, state: FSMContext):
    new_desc = message.text
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id).options(selectinload(User.master_profile))
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if user and user.master_profile:
            user.master_profile.description = new_desc
            await session.commit()
    
    await state.set_state(EditProfileStates.choosing_field)
    await message.answer("✅ Описание сохранено.", reply_markup=get_edit_profile_inline_keyboard())

@router.callback_query(EditProfileStates.choosing_field, F.data == "profile_back")
@router.callback_query(ManagePhotoStates.main, F.data == "profile_back")
async def back_to_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await show_profile(callback.message)
    await callback.answer()

# --- MANAGE PHOTOS ---
@router.message(F.text == "📸 Фото")
async def manage_photos(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
    count = len(user.master_profile.work_photos) if user and user.master_profile and user.master_profile.work_photos else 0
    await state.set_state(ManagePhotoStates.main)
    await message.answer(
        f"📸 *Ваши фото работ*\n\nУ вас {count} фото.",
        parse_mode="Markdown",
        reply_markup=get_photo_management_keyboard(count)
    )

@router.callback_query(ManagePhotoStates.main, F.data == "add_photos")
async def add_photos_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ManagePhotoStates.adding_photos)
    await callback.message.edit_text(
        "📸 *Добавление фото*\n\nОтправьте мне одно или несколько фото. Когда закончите, нажмите кнопку «Готово».",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="photo_done")]])
    )
    await callback.answer()

@router.message(ManagePhotoStates.adding_photos, F.photo)
async def process_new_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    async with async_session_maker() as session:
        stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if user and user.master_profile:
            current_photos = list(user.master_profile.work_photos or [])
            current_photos.append(file_id)
            user.master_profile.work_photos = current_photos
            await session.commit()
    
    await message.answer(f"✅ Фото добавлено. Вы можете отправить еще или нажать «Готово» выше.")

@router.callback_query(ManagePhotoStates.adding_photos, F.data == "photo_done")
async def finish_uploading(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await manage_photos(callback.message, state)
    await callback.answer()

@router.callback_query(ManagePhotoStates.main, F.data == "delete_photos")
async def delete_photos_start(callback: CallbackQuery, state: FSMContext):
    async with async_session_maker() as session:
        stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == callback.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
    
    photos = user.master_profile.work_photos if user and user.master_profile else []
    if not photos:
        await callback.answer("У вас нет фото для удаления.", show_alert=True)
        return

    await state.set_state(ManagePhotoStates.deleting_photos)
    # Just show the first one or simple logic for now
    await callback.message.edit_text("🗑️ Введите номер фото для удаления (1, 2, 3...) или 'отмена'.")
    await callback.answer()

# --- ORDERS SUBMENU ---
@router.message(F.text == "🔄 Доступные заказы")
async def show_available_orders(message: Message):
    async with async_session_maker() as session:
        from database.models import Order, OrderStatus
        # Get Master's categories
        stmt = select(User).options(selectinload(User.master_profile).selectinload(MasterProfile.categories)).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user or not user.master_profile:
            return

        cat_ids = [c.id for c in user.master_profile.categories]
        
        # Fetch active orders in these categories
        order_stmt = select(Order).options(selectinload(Order.category)).where(
            Order.category_id.in_(cat_ids),
            Order.status == OrderStatus.NEW
        ).order_by(Order.created_at.desc())
        
        o_res = await session.execute(order_stmt)
        orders = o_res.scalars().all()
        
    if not orders:
        await message.answer("🔄 В данный момент новых заказов по вашим категориям нет. Мы уведомим вас, когда они появятся!")
        return
        
    text = f"🔄 *Доступные заказы ({len(orders)}):*\n\n"
    keyboard = []
    for o in orders:
        text += f"📦 *{o.category.name}*\n💰 Бюджет: {o.budget or 'Договорная'}\n📍 {o.district.name if o.district else '—'}\n\n"
        keyboard.append([InlineKeyboardButton(text=f"📥 Заказ №{o.id}", callback_data=f"master_view_order:{o.id}")])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("master_view_order:"))
async def master_view_order_callback(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await show_order_details(callback.message, order_id)
    await callback.answer()

@router.message(F.text.regexp(r"^/order_?(\d+)$"))
async def view_order_details(message: Message):
    # Matches /order_6 or /order6
    import re
    match = re.match(r"^/order_?(\d+)$", message.text)
    order_id = int(match.group(1))
    await show_order_details(message, order_id)

async def show_order_details(message: Message, order_id: int):
    async with async_session_maker() as session:
        stmt = select(Order).options(selectinload(Order.category), selectinload(Order.district)).where(Order.id == order_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
    
    if not order:
        await message.answer("❌ Заказ не найден.")
        return
    
    text = (
        f"📦 *Заказ №{order.id}: {order.category.name}*\n\n"
        f"📝 Описание: {order.description}\n"
        f"💰 Бюджет: {order.budget or 'Договорная'}\n"
        f"📍 Район: {order.district.name if order.district else '—'}\n"
        f"📅 Создан: {order.created_at.strftime('%d.%m %H:%M')}\n\n"
        f"🏷️ *Стоимость отклика: 50 баллов.*"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Откликнуться", callback_data=f"start_bid:{order.id}")
    ]])
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data.startswith("start_bid:"))
async def start_bid_flow(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == callback.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user or user.points < 50:
            await callback.answer("❌ У вас недостаточно баллов для отклика (нужно 50).", show_alert=True)
            return

    await state.update_data(bid_order_id=order_id)
    await state.set_state(BidStates.entering_price)
    await callback.message.answer("💰 *Введите вашу цену за работу (в тенге):*")
    await callback.answer()

@router.message(BidStates.entering_price)
async def process_bid_price(message: Message, state: FSMContext):
    await state.update_data(bid_price=message.text)
    await state.set_state(BidStates.entering_message)
    await message.answer("📩 *Напишите мастерское сообщение для клиента:*")

@router.message(BidStates.entering_message)
async def process_bid_message(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['bid_order_id']
    price_str = data['bid_price']
    msg = message.text
    
    async with async_session_maker() as session:
        m_stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.from_user.id)
        user = (await session.execute(m_stmt)).scalar_one()
        
        # Deduct
        user.points -= 50
        session.add(Transaction(user_id=user.id, amount=-50, type=TransactionType.CONTACT_FEE, description=f"Отклик на заказ №{order_id}"))
        
        import re
        price_val = None
        digits = re.findall(r'\d+', price_str)
        if digits: price_val = int("".join(digits))
        
        bid = Bid(order_id=order_id, master_id=user.master_profile.id, suggested_price=price_val, message=msg)
        session.add(bid)
        await session.flush() # Get bid.id
        
        # Notify
        o_stmt = select(Order).options(selectinload(Order.client)).where(Order.id == order_id)
        order = (await session.execute(o_stmt)).scalar_one()
        client_tg_id = order.client.telegram_id
        
        await session.commit()
    
    await message.answer("✅ Отклик успешно отправлен!")
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Посмотреть отклик и детали", callback_data=f"client_view_order:{order_id}")],
        [InlineKeyboardButton(text="✅ Принять отклик", callback_data=f"client_accept_bid:{bid.id}")]
    ])
    
    await message.bot.send_message(
        client_tg_id, 
        f"🔔 <b>Новый отклик на заказ №{order_id}!</b>\n💰 Предложенная цена: {price_str}\n\n"
        f"👷 Мастер: {user.full_name}\n"
        f"📩 Сообщение: {msg[:100]}...", 
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.message(F.text == "⏳ Мои активные заказы")
async def show_active_orders(message: Message):
    await message.answer("⏳ У вас пока нет активных заказов. Откликнитесь на заявку в списке доступных!")

@router.message(F.text == "✅ Выполненные заказы")
async def show_completed_orders(message: Message):
    await message.answer("✅ В вашей истории пока нет завершенных заказов.")

# --- BALANCE SUBMENU ---
@router.message(F.text == "📜 История операций")
async def show_balance_history(message: Message):
    async with async_session_maker() as session:
        from database.models import Transaction
        stmt = select(Transaction).join(User).where(User.telegram_id == message.from_user.id).order_by(Transaction.created_at.desc()).limit(10)
        res = await session.execute(stmt)
        txs = res.scalars().all()
        
    if not txs:
        await message.answer("📜 Ваша история операций пока пуста.")
        return
        
    text = "📜 *История операций:*\n\n"
    for tx in txs:
        sign = "+" if tx.amount > 0 else "-"
        date = tx.created_at.strftime("%d.%m %H:%M")
        text += f"📅 {date} | *{sign}{abs(tx.amount)}* — {tx.description}\n"
    
    await message.answer(text, parse_mode="Markdown")

# --- SETTINGS SUBMENU ---
@router.message(F.text == "🔔 Уведомления")
async def toggle_notifications(message: Message):
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        current = user.notifications_enabled
        user.notifications_enabled = not current
        await session.commit()
        new_state = "ВКЛЮЧЕНЫ" if not current else "ВЫКЛЮЧЕНЫ"
        
    await message.answer(f"🔔 Уведомления о новых заказах: *{new_state}*", parse_mode="Markdown")

@router.message(F.text == "🚫 Режим «Не беспокоить»")
async def toggle_dnd(message: Message):
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        current = user.do_not_disturb
        user.do_not_disturb = not current
        await session.commit()
        new_state = "АКТИВИРОВАН" if not current else "ВЫКЛЮЧЕН"
        
    await message.answer(f"🚫 Режим «Не беспокоить»: *{new_state}*", parse_mode="Markdown")

@router.message(F.text == "🔑 Сменить статус видимости")
async def toggle_visibility(message: Message):
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        current = user.visible_for_new_orders
        user.visible_for_new_orders = not current
        await session.commit()
        new_state = "ВИДИМ" if not current else "СКРЫТ"
        
    await message.answer(f"🔑 Ваш профиль для новых заказов: *{new_state}*", parse_mode="Markdown")

@router.message(F.text == "📍 Районы работы")
async def manage_districts(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        from database.models import District
        stmt = select(User).options(selectinload(User.master_profile).selectinload(MasterProfile.districts)).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        dist_res = await session.execute(select(District))
        all_districts = dist_res.scalars().all()
        all_dist_names = [d.name for d in all_districts]
        selected_names = [d.name for d in user.master_profile.districts]
        
    await state.set_state(SettingsStates.choosing_districts)
    await state.update_data(selected_districts=selected_names, all_dist_names=all_dist_names)
    
    await message.answer(
        "📍 *Выбор районов работы*\n\nОтметьте районы, в которых вы готовы принимать заказы:",
        parse_mode="Markdown",
        reply_markup=build_districts_keyboard(selected_names, all_dist_names)
    )

@router.callback_query(SettingsStates.choosing_districts, F.data.startswith("dist_toggle:"))
async def toggle_district(callback: CallbackQuery, state: FSMContext):
    dist_name = callback.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("selected_districts", []))
    all_names = data.get("all_dist_names", [])
    
    if dist_name in selected:
        selected.remove(dist_name)
    else:
        selected.add(dist_name)
        
    await state.update_data(selected_districts=list(selected))
    await callback.message.edit_reply_markup(reply_markup=build_districts_keyboard(list(selected), all_names))
    await callback.answer()

@router.callback_query(SettingsStates.choosing_districts, F.data == "dist_save")
async def save_districts(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_names = data.get("selected_districts", [])
    
    async with async_session_maker() as session:
        from database.models import District
        stmt = select(User).options(selectinload(User.master_profile).selectinload(MasterProfile.districts)).where(User.telegram_id == callback.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        # Sync districts
        dist_stmt = select(District).where(District.name.in_(selected_names))
        dist_res = await session.execute(dist_stmt)
        new_districts = dist_res.scalars().all()
        
        user.master_profile.districts = list(new_districts)
        await session.commit()
    
    await state.clear()
    # Simple message after save
    await callback.message.edit_text("✅ Районы успешно сохранены.")
    await callback.answer()

@router.message(F.text == "🆘 Помощь")
async def show_help(message: Message):
    text = (
        "🆘 *Центр помощи*\n\n"
        "1. Как получить аккредитацию? Загрузите реальные фото и дождитесь проверки.\n"
        "2. Как работают баллы? Вы платите за контакт с клиентом.\n"
        "3. Почему нет заказов? Проверьте настройки видимости в Профиле.\n\n"
        "Нужен человек? Свяжитесь с @admin"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🔗 Рефералы")
async def show_referrals(message: Message):
    async with async_session_maker() as session:
        from database.models import Transaction, TransactionType
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        # Count referred users who are approved masters
        ref_stmt = select(User).where(User.referred_by == user.id)
        ref_res = await session.execute(ref_stmt)
        refs = ref_res.scalars().all()
        
        # Total earned from referrals
        bonus_stmt = select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user.id,
            Transaction.type == TransactionType.REFERRAL_BONUS
        )
        bonus_res = await session.execute(bonus_stmt)
        total_earned = bonus_res.scalar() or 0

    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"
    
    text = (
        "🔗 *Реферальная система*\n\n"
        "Приглашайте коллег и получайте по *1000 баллов* за каждого мастера, который пройдет модерацию!\n\n"
        f"👥 Принято приглашений: {len(refs)}\n"
        f"💰 Заработано: {total_earned} баллов\n\n"
        f"📍 Ваша ссылка:\n`{ref_link}`"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "⭐ Рейтинг и отзывы")
async def show_rating(message: Message):
    await message.answer("⭐ Ваша статистика отзывов:\nПока нет отзывов (раздел в разработке).")
