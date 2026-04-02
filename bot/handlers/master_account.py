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
async def manage_master_photos(message: Message):
    async with async_session_maker() as session:
        stmt = select(MasterProfile).join(User).where(User.telegram_id == message.chat.id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        
        photos = profile.work_photos or []
        count = len(photos)
        
        await message.answer(f"📸 У вас загружено {count} фото работ (макс. 3).", reply_markup=get_photo_management_keyboard(count))
        if photos:
            media = [InputMediaPhoto(media=p) for p in photos]
            await message.answer_media_group(media=media)

@router.callback_query(F.data == "add_photos")
async def add_photos_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ManagePhotoStates.adding_photos)
    await callback.message.edit_text("📤 Отправьте до 3 фото ваших работ одно за другим:")
    await callback.answer()

@router.message(ManagePhotoStates.adding_photos, F.photo)
async def process_adding_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    temp_photos = data.get("temp_photos", [])
    temp_photos.append(message.photo[-1].file_id)
    await state.update_data(temp_photos=temp_photos)
    
    if len(temp_photos) >= 3:
        await finish_adding_photos(message, state)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="finish_add_photos")]])
        await message.answer(f"✅ Фото получено! ({len(temp_photos)}/3). Скиньте еще или нажмите Готово.", reply_markup=kb)

@router.callback_query(F.data == "finish_add_photos")
async def finish_adding_photos_callback(callback: CallbackQuery, state: FSMContext):
    await finish_adding_photos(callback.message, state)
    await callback.answer()

async def finish_adding_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    new_photos = data.get("temp_photos", [])
    async with async_session_maker() as session:
        res = await session.execute(select(MasterProfile).join(User).where(User.telegram_id == message.chat.id))
        profile = res.scalar_one_or_none()
        if profile:
            profile.work_photos = new_photos[:3]
            await session.commit()
    await state.clear()
    await message.answer("✅ Фото успешно обновлены!")
    await show_profile(message)

@router.callback_query(F.data == "delete_photos")
async def delete_photos_callback(callback: CallbackQuery):
    async with async_session_maker() as session:
        res = await session.execute(select(MasterProfile).join(User).where(User.telegram_id == callback.from_user.id))
        profile = res.scalar_one_or_none()
        if profile:
            profile.work_photos = []
            await session.commit()
    await callback.message.edit_text("🗑️ Все фото удалены.")
    await callback.answer()

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
        text += f"\n📦 <b>{o.category.name}</b>\n👤 Клиент: {o.client.full_name}\n📱 Телефон: <code>{o.client.phone_number}</code>\n"
        keyboard.append([InlineKeyboardButton(text=f"✅ Завершить заказ №{o.id}", callback_data=f"client_complete_order:{o.id}")])
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

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
    text = f"📦 <b>Заказ №{order.id}: {order.category.name}</b>\n\n📝 {order.description}\n💰 Бюджет: {order.budget or 'Договорная'}\n📍 Район: {order.district.name if order.district else '—'}\n\n🏷️ <b>Стоимость отклика: 50 баллов.</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Откликнуться", callback_data=f"start_bid:{order.id}")]])
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
        user = (await session.execute(select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.chat.id))).scalar_one()
        user.points -= 50
        session.add(Transaction(user_id=user.id, amount=-50, type=TransactionType.CONTACT_FEE, description=f"Отклик на заказ №{order_id}"))
        import re
        price_val = int("".join(re.findall(r'\d+', price_str))) if re.findall(r'\d+', price_str) else 0
        bid = Bid(order_id=order_id, master_id=user.master_profile.id, suggested_price=price_val, message=message.text)
        session.add(bid)
        await session.flush()
        order = (await session.execute(select(Order).options(selectinload(Order.client)).where(Order.id == order_id))).scalar_one()
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
        res = await session.execute(select(MasterProfile.id).join(User).where(User.telegram_id == message.chat.id))
        master_id = res.scalar()
        completed = (await session.execute(select(func.count(Order.id)).join(Bid).where(Bid.master_id == master_id, Bid.status == 'accepted', Order.status == OrderStatus.COMPLETED))).scalar() or 0
        active = (await session.execute(select(func.count(Order.id)).join(Bid).where(Bid.master_id == master_id, Bid.status == 'accepted', Order.status == OrderStatus.ACTIVE))).scalar() or 0
    await message.answer(f"📊 <b>Статистика:</b>\n✅ Выполнено: {completed}\n⚡️ В работе: {active}", parse_mode="HTML")

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
    await message.answer(f"💰 Ваш баланс: {p} баллов\n\nСтоимость отклика: 50 баллов.", reply_markup=get_balance_menu())

@router.message(F.text == "⚙️ Настройки")
async def show_settings_handler(message: Message):
    await message.answer("⚙️ Настройки профиля:", reply_markup=get_settings_menu())

@router.message(F.text == "🏠 Выход в главное меню")
async def exit_to_main(message: Message):
    from bot.handlers.start import get_role_keyboard
    await message.answer("🏠 Вы вернулись в главное меню.", reply_markup=get_role_keyboard())

@router.message(F.text == "🔙 Назад в меню")
async def back_to_main(message: Message):
    await message.answer("📋 Главное меню", reply_markup=get_master_main_menu())

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
