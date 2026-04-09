from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command
from bot.core.config import config
from database.engine import async_session_maker
from database.models import User, MasterProfile, MasterStatus, UserRole, Transaction, TransactionType, Order, OrderStatus, Category, District, SystemSettings, TopUpRequest
from sqlalchemy import select, func, update, delete, or_
from sqlalchemy.orm import selectinload
from bot.keyboards.master import get_master_main_menu
from bot.keyboards.admin import (
    get_admin_main_menu, 
    get_admin_back_inline, 
    get_list_management_keyboard, 
    get_payment_settings_keyboard,
    get_topup_review_keyboard
)
from bot.states import AdminStates, BroadcastStates, UserManagementStates, PaymentSettingsStates
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, timezone

router = Router()

@router.message(Command("admin"))
@router.message(F.text == "👨‍✈️ Админ-панель")
async def admin_start(message: Message):
    """Shows admin navigation menu."""
    if message.from_user.id not in config.ADMIN_IDS:
        return
        
    async with async_session_maker() as session:
        # Mini Stats
        total_u = (await session.execute(select(func.count(User.id)))).scalar() or 0
        pending_m = (await session.execute(select(func.count(MasterProfile.id)).where(MasterProfile.status == MasterStatus.PENDING))).scalar() or 0
        active_o = (await session.execute(select(func.count(Order.id)).where(Order.status == OrderStatus.ACTIVE))).scalar() or 0
        
    text = (
        f"👷 <b>Добро пожаловать в админ-панель!</b>\n\n"
        f"📊 <b>Текущие данные:</b>\n"
        f"👥 Пользователей: {total_u}\n"
        f"⏳ Заявок мастеров: {pending_m}\n"
        f"⚡️ Активных заказов: {active_o}\n\n"
        f"Выберите раздел ниже для управления."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_admin_main_menu())

@router.message(F.text == "⏳ Заявки мастеров")
async def list_pending_masters(message: Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    async with async_session_maker() as session:
        stmt = select(MasterProfile).options(selectinload(MasterProfile.user)).where(MasterProfile.status == MasterStatus.PENDING)
        masters = (await session.execute(stmt)).scalars().all()
    
    if not masters:
        await message.answer("✅ Пока нет новых заявок на модерации.")
        return
        
    text = "⏳ <b>Заявки на проверку:</b>"
    kb = []
    for m in masters:
        kb.append([InlineKeyboardButton(text=f"🔍 {m.user.full_name} (#{m.id})", callback_data=f"admin_view_master:{m.id}")])
    
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.message(F.text == "📋 Все заказы")
async def list_all_orders(message: Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    async with async_session_maker() as session:
        stmt = select(Order).options(selectinload(Order.category), selectinload(Order.district)).where(Order.status.in_([OrderStatus.NEW, OrderStatus.ACTIVE])).order_by(Order.created_at.desc()).limit(10)
        orders = (await session.execute(stmt)).scalars().all()
        
    if not orders:
        await message.answer("📦 Активных заказов нет.")
        return
        
    text = "📋 <b>Последние заказы:</b>\n"
    for o in orders:
        st = "🆕" if o.status == OrderStatus.NEW else "⏳"
        text += f"\n{st} #{o.id} - {o.category.name}\n📍 {o.district.name if o.district else '—'} | 💰 {o.budget or 'Нет'}"
    
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "👥 Пользователи")
async def show_users_stats(message: Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    async with async_session_maker() as session:
        stats = (await session.execute(select(User.role, func.count(User.id)).group_by(User.role))).all()
        
    text = "👥 <b>Статистика пользователей:</b>\n\n"
    for role, count in stats:
        text += f"▪️ {role.value}: {count}\n"
    
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "💰 Пополнение баллов")
async def show_refill_info(message: Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    text = (
        "💰 <b>Управление балансом</b>\n\n"
        "Чтобы пополнить баланс мастера, используйте команду:\n"
        "<code>/refill [telegram_id] [сумма]</code>\n\n"
        "Пример: <code>/refill 1234567 1000</code>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🔙 Выход из админки")
async def exit_admin(message: Message):
    from bot.keyboards.registration import get_role_keyboard
    is_admin = message.from_user.id in config.ADMIN_IDS
    await message.answer("🏠 Вы вернулись в главное меню.", reply_markup=get_role_keyboard(is_admin=is_admin))

# --- VIEW MASTER DETAILS (reuse callbacks) ---
@router.callback_query(F.data.startswith("admin_view_master:"))
async def view_master_details(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS: return
    m_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        stmt = select(MasterProfile).options(selectinload(MasterProfile.user), selectinload(MasterProfile.categories)).where(MasterProfile.id == m_id)
        profile = (await session.execute(stmt)).scalar_one_or_none()
    if not profile:
        await callback.answer("Master not found.")
        return
    text = (
        f"👷 <b>Мастер #{profile.id}</b>\n\n"
        f"👤 Имя: {profile.user.full_name}\n"
        f"📅 Стаж: {profile.experience or '—'}\n"
        f"🗂 Категории: {', '.join([c.name for c in profile.categories])}\n"
        f"💬 О себе: {profile.description or '—'}\n"
        f"TG: @{profile.user.username or 'no_user'} (<code>{profile.user.telegram_id}</code>)"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve:{profile.id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject:{profile.id}")]
    ])
    if profile.work_photos:
        media = [InputMediaPhoto(media=p) for p in profile.work_photos]
        await callback.message.answer_media_group(media=media)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_approve:"))
async def approve_master(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS: return
    master_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        stmt = select(User).join(MasterProfile).where(MasterProfile.id == master_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user: return
        profile = (await session.execute(select(MasterProfile).where(MasterProfile.id == master_id))).scalar_one()
        profile.status = MasterStatus.APPROVED
        
        # 🎁 WELCOME BONUS for the MASTER
        user.points += 2000
        session.add(Transaction(
            user_id=user.id,
            amount=2000,
            type=TransactionType.REFERRAL_BONUS,
            description="Приветственный бонус при регистрации"
        ))

        # 🎁 REFERRAL reward for the inviter
        if user.referred_by:
            inviter = await session.get(User, user.referred_by)
            if inviter:
                inviter.points += 1000
                session.add(Transaction(
                    user_id=inviter.id,
                    amount=1000,
                    type=TransactionType.REFERRAL_BONUS,
                    description=f"Бонус за регистрацию мастера {user.full_name}"
                ))
                try:
                    await callback.bot.send_message(
                        inviter.telegram_id,
                        f"🎁 <b>Бонус за реферала!</b>\n\n"
                        f"Приглашенный вами мастер <b>{user.full_name}</b> успешно прошел проверку.\n"
                        f"Вам начислено <b>1000 баллов</b>!",
                        parse_mode="HTML"
                    )
                except Exception: pass
                
        tg_id = user.telegram_id
        is_target_admin = tg_id in config.ADMIN_IDS
        await session.commit()
    await callback.message.edit_text(f"✅ Мастер #{master_id} одобрен!")
    try:
        await callback.bot.send_message(
            tg_id, 
            f"🎉 <b>Ваш профиль мастера одобрен!</b>\n\n"
            f"🎁 Вам начислено <b>2000 приветственных баллов</b>.\n"
            f"Теперь вы можете откликаться на заказы.", 
            reply_markup=get_master_main_menu(is_admin=is_target_admin),
            parse_mode="HTML"
        )
    except Exception: pass
    await callback.answer()

@router.callback_query(F.data.startswith("admin_reject:"))
async def reject_master(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS: return
    master_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        await session.execute(update(MasterProfile).where(MasterProfile.id == master_id).values(status=MasterStatus.REJECTED))
        await session.commit()
    await callback.message.edit_text(f"❌ Мастер #{master_id} отклонен.")
    await callback.answer()

@router.message(Command("refill"))
async def admin_refill_points(message: Message):
    """Manual refill command: /refill [telegram_id] [amount]"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("⚠️ Ошибка формата. Используйте: <code>/refill [ID] [сумма]</code>", parse_mode="HTML")
        return
        
    try:
        # Clean input from brackets or other symbols
        raw_id = parts[1].strip("[]")
        raw_amount = parts[2].strip("[]")
        
        target_id = int(raw_id)
        amount = int(raw_amount)
    except ValueError:
        await message.answer("❌ Ошибка: ID и сумма должны быть числами.")
        return
    
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == target_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user:
            await message.answer(f"❌ Пользователь с ID <code>{target_id}</code> не найден в базе.", parse_mode="HTML")
            return
            
        user.points += amount
        session.add(Transaction(
            user_id=user.id, 
            amount=amount, 
            type=TransactionType.ADMIN_ADJUSTMENT, 
            description="Ручное пополнение администратором"
        ))
        await session.commit()
        
    await message.answer(f"✅ Баланс пользователя <b>{user.full_name}</b> пополнен на <b>{amount}</b> баллов.", parse_mode="HTML")
    try:
        await message.bot.send_message(target_id, f"💰 Ваш баланс пополнен администратором на <b>{amount}</b> баллов!", parse_mode="HTML")
    except Exception:
        pass

# --- CATEGORY MANAGEMENT ---
@router.message(F.text == "🗂️ Категории")
async def admin_manage_categories(message: Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category))).scalars().all()
    await message.answer("🗂️ <b>Управление категориями</b>\nНажмите Trash для удаления или кнопку ниже для добавления:", parse_mode="HTML", reply_markup=get_list_management_keyboard(cats, "cat"))

@router.callback_query(F.data == "cat_add")
async def admin_add_cat_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.adding_category)
    await callback.message.answer("⌨️ Введите название новой категории:")
    await callback.answer()

@router.message(AdminStates.adding_category)
async def admin_add_cat_finish(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        session.add(Category(name=message.text))
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Категория «{message.text}» успешно добавлена!")
    await admin_manage_categories(message)

@router.callback_query(F.data.startswith("cat_del:"))
async def admin_del_cat(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        # Check usage in orders and master subscriptions
        orders_c = (await session.execute(select(func.count(Order.id)).where(Order.category_id == cat_id))).scalar()
        masters_c = (await session.execute(
            select(func.count(MasterProfile.id))
            .join(MasterProfile.categories)
            .where(Category.id == cat_id)
        )).scalar()
        
        if orders_c:
            await callback.answer(f"❌ Нельзя удалить: {orders_c} заказа(ов) в категории!", show_alert=True)
            return
            
        cat = await session.get(Category, cat_id)
        await session.delete(cat)
        await session.commit()
    await callback.answer(f"✅ Категория удалена (затронуто мастеров: {masters_c})")
    await admin_manage_categories(callback.message)

# --- DISTRICT MANAGEMENT ---
@router.message(F.text == "📍 Районы")
async def admin_manage_districts(message: Message):
    if message.from_user.id not in config.ADMIN_IDS: return
    async with async_session_maker() as session:
        dists = (await session.execute(select(District))).scalars().all()
    await message.answer("📍 <b>Управление районами</b>\nНажмите Trash для удаления или кнопку ниже для добавления:", parse_mode="HTML", reply_markup=get_list_management_keyboard(dists, "dist"))

@router.callback_query(F.data == "dist_add")
async def admin_add_dist_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.adding_district)
    await callback.message.answer("⌨️ Введите название нового района:")
    await callback.answer()

@router.message(AdminStates.adding_district)
async def admin_add_dist_finish(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        session.add(District(name=message.text))
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Район «{message.text}» успешно добавлен!")
    await admin_manage_districts(message)

@router.callback_query(F.data.startswith("dist_del:"))
async def admin_del_dist(callback: CallbackQuery):
    dist_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        orders_c = (await session.execute(select(func.count(Order.id)).where(Order.district_id == dist_id))).scalar()
        masters_c = (await session.execute(
            select(func.count(MasterProfile.id))
            .join(MasterProfile.districts)
            .where(District.id == dist_id)
        )).scalar()
        
        if orders_c:
            await callback.answer(f"❌ Нельзя удалить: {orders_c} заказа(ов) в этом районе!", show_alert=True)
            return
            
        dist = await session.get(District, dist_id)
        await session.delete(dist)
        await session.commit()
    await callback.answer(f"✅ Район удален (затронуто мастеров: {masters_c})")
    await admin_manage_districts(callback.message)

@router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS: return
    await state.set_state(BroadcastStates.entering_text)
    await message.answer(
        "📢 <b>Режим рассылки</b>\n\n"
        "Напишите текст сообщения в поле ввода ниже и отправьте его (можно использовать HTML-разметку):",
        parse_mode="HTML"
    )

@router.message(BroadcastStates.entering_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(BroadcastStates.uploading_photo)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏩ Без фото", callback_data="skip_photo")]])
    await message.answer(
        "📸 Теперь отправьте <b>фото</b> для рассылки (через 📎 <b>скрепку</b>) или нажмите кнопку ниже:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "skip_photo", BroadcastStates.uploading_photo)
async def skip_broadcast_photo(callback: CallbackQuery, state: FSMContext):
    await state.update_data(photo=None)
    await show_broadcast_preview(callback.message, state)
    await callback.answer()

@router.message(BroadcastStates.uploading_photo, F.photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await show_broadcast_preview(message, state)

async def show_broadcast_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    text, photo = data['text'], data['photo']
    await state.set_state(BroadcastStates.confirming)
    
    preview_text = f"📝 <b>Предпросмотр рассылки:</b>\n\n{text}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить рассылку", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    
    if photo:
        await message.answer_photo(photo, caption=preview_text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(preview_text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(BroadcastStates.confirming, F.data == "confirm_broadcast")
async def execute_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text, photo = data['text'], data['photo']
    if callback.message.photo:
        await callback.message.edit_caption(caption="⏳ Рассылка запущена... Это может занять некоторое время.")
    else:
        await callback.message.edit_text("⏳ Рассылка запущена... Это может занять некоторое время.")
    
    async with async_session_maker() as session:
        users = (await session.execute(select(User.telegram_id))).scalars().all()
    
    count = 0
    for uid in users:
        try:
            if photo:
                await callback.bot.send_photo(uid, photo, caption=text, parse_mode="HTML")
            else:
                await callback.bot.send_message(uid, text, parse_mode="HTML")
            count += 1
        except Exception: pass
            
    await callback.message.answer(f"✅ Рассылка завершена! Доставлено {count} пользователям.")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Рассылка отменена.")

# --- BAN MANAGEMENT ---
@router.message(F.text == "🚫 Баны")
async def start_ban_management(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS: return
    await state.set_state(UserManagementStates.searching_user)
    await message.answer("🔍 Введите ID пользователя (внутренний в базе) для управления баном:")

@router.message(UserManagementStates.searching_user)
async def process_user_ban_search(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("⚠️ Введите числовой идентификатор.")
        return
        
    async with async_session_maker() as session:
        from sqlalchemy import or_
        # Safety check: PostgreSQL INTEGER (int32) max value is 2,147,483,647
        if user_id > 2147483647:
            stmt = select(User).where(User.telegram_id == user_id)
        else:
            stmt = select(User).where(or_(User.id == user_id, User.telegram_id == user_id))
            
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            await message.answer(f"❌ Пользователь #{user_id} не найден.")
            return
            
    await state.update_data(target_user_id=user.id)
    await state.set_state(UserManagementStates.selecting_ban_period)
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    status = "✅ Активен"
    if user.banned_until and user.banned_until > now:
        status = f"🚫 Забанен до {user.banned_until.strftime('%d.%m.%Y %H:%M')}"
        
    text = (
        f"👤 <b>Управление пользователем:</b> {user.full_name}\n"
        f"🆔 ID записи: {user.id}\n"
        f"📱 TG ID: <code>{user.telegram_id}</code>\n"
        f"📊 Статус: {status}\n\n"
        f"Выберите период для бана (или снимите бан):"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Разбанить", callback_data="ban_set:0")],
        [InlineKeyboardButton(text="24 часа", callback_data="ban_set:1"), InlineKeyboardButton(text="7 дней", callback_data="ban_set:7")],
        [InlineKeyboardButton(text="1 месяц", callback_data="ban_set:30"), InlineKeyboardButton(text="6 месяцев", callback_data="ban_set:180")],
        [InlineKeyboardButton(text="1 год", callback_data="ban_set:365"), InlineKeyboardButton(text="🔥 Пожизненно", callback_data="ban_set:99999")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(UserManagementStates.selecting_ban_period, F.data.startswith("ban_set:"))
async def process_ban_execution(callback: CallbackQuery, state: FSMContext):
    days = int(callback.data.split(":")[1])
    data = await state.get_data()
    uid = data['target_user_id']
    
    async with async_session_maker() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one()
        old_tid = user.telegram_id
        
        if days == 0:
            user.banned_until = None
            msg = "⚡️ Ограничения с вашего аккаунта сняты. Пожалуйста, больше не нарушайте правила!"
            admin_msg = f"✅ Пользователь #{uid} разбанен."
        else:
            ban_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)
            user.banned_until = ban_date
            msg = f"🚫 Ваш аккаунт заблокирован до {ban_date.strftime('%d.%m.%Y %H:%M')} за нарушение правил."
            admin_msg = f"🚫 Пользователь #{uid} забанен на {days} дн."

        await session.commit()
    
    try:
        await callback.bot.send_message(old_tid, msg)
    except Exception: pass
    
    await callback.message.edit_text(admin_msg)
    await state.clear()
    await callback.answer()

# --- PAYMENT SETTINGS MANAGEMENT ---
@router.message(F.text == "⚙️ Настройки оплаты")
async def cmd_payment_settings(message: Message):
    """Entry point for payment configuration."""
    if message.from_user.id not in config.ADMIN_IDS: return
    
    async with async_session_maker() as session:
        settings = await session.get(SystemSettings, 1)
        if not settings:
            settings = SystemSettings(id=1, crypto_enabled=False, bank_enabled=False)
            session.add(settings)
            await session.commit()
            
    text = (
        "⚙️ <b>Настройки платежной системы</b>\n\n"
        f"🔗 <b>Криптовалюта:</b> {'✅ ВКЛ' if settings.crypto_enabled else '❌ ВЫКЛ'}\n"
        f"👛 Адрес: <code>{settings.crypto_address or 'Не установлен'}</code>\n\n"
        f"🏛 <b>Банковский перевод:</b> {'✅ ВКЛ' if settings.bank_enabled else '❌ ВЫКЛ'}\n"
        f"📝 Реквизиты: <code>{settings.bank_details or 'Не установлены'}</code>\n\n"
        "Выберите действие ниже:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_payment_settings_keyboard(settings.crypto_enabled, settings.bank_enabled))

@router.callback_query(F.data.startswith("pay_toggle:"))
async def process_pay_toggle(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS: return
    method = callback.data.split(":")[1]
    
    async with async_session_maker() as session:
        # Get using ID=1 as it's a single-row settings table
        settings = await session.get(SystemSettings, 1)
        if not settings: 
            settings = SystemSettings(id=1)
            session.add(settings)
            
        if method == "crypto":
            settings.crypto_enabled = not settings.crypto_enabled
        else:
            settings.bank_enabled = not settings.bank_enabled
        await session.commit()
        
    await callback.answer("✅ Настройки обновлены")
    # Refresh the menu
    await cmd_payment_settings(callback.message)
    await callback.message.delete()

@router.callback_query(F.data.startswith("pay_edit:"))
async def process_pay_edit(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMIN_IDS: return
    method = callback.data.split(":")[1]
    
    if method == "crypto":
        await state.set_state(PaymentSettingsStates.entering_crypto_address)
        await callback.message.answer("⌨️ Введите <b>новый адрес</b> для оплаты криптовалютой:")
    else:
        await state.set_state(PaymentSettingsStates.entering_bank_details)
        await callback.message.answer("⌨️ Введите <b>реквизиты</b> для банковского перевода (номер карты, ссылку или текст):")
    
    await callback.answer()

@router.message(PaymentSettingsStates.entering_crypto_address)
async def process_crypto_address(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        settings = await session.get(SystemSettings, 1)
        settings.crypto_address = message.text
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Адрес криптовалюты обновлен на: <code>{message.text}</code>", parse_mode="HTML")
    await cmd_payment_settings(message)

@router.message(PaymentSettingsStates.entering_bank_details)
async def process_bank_details(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        settings = await session.get(SystemSettings, 1)
        settings.bank_details = message.text
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Банковские реквизиты обновлены.", parse_mode="HTML")
    await cmd_payment_settings(message)

@router.callback_query(F.data == "pay_requests")
async def list_topup_requests(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS: return
    
    async with async_session_maker() as session:
        stmt = (
            select(TopUpRequest)
            .options(selectinload(TopUpRequest.user))
            .where(TopUpRequest.status == "PENDING")
            .order_by(TopUpRequest.created_at.desc())
        )
        requests = (await session.execute(stmt)).scalars().all()
    
    if not requests:
        await callback.answer("✅ Ожидающих заявок нет.", show_alert=True)
        return
        
    await callback.message.answer(f"📦 <b>Всего ожидающих заявок: {len(requests)}</b>", parse_mode="HTML")
    
    for req in requests:
        text = (
            f"💰 <b>Заявка на пополнение #{req.id}</b>\n\n"
            f"👤 От: {req.user.full_name} (<code>{req.user.telegram_id}</code>)\n"
            f"💵 Сумма: <b>{req.amount}</b> баллов\n"
            f"🔹 Метод: {req.method}\n"
            f"📅 Дата: {req.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        if req.receipt_photo:
            await callback.bot.send_photo(callback.from_user.id, req.receipt_photo, caption=text, reply_markup=get_topup_review_keyboard(req.id), parse_mode="HTML")
        else:
            await callback.message.answer(text, reply_markup=get_topup_review_keyboard(req.id), parse_mode="HTML")

@router.callback_query(F.data.startswith("tr_"))
async def process_topup_review(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS: return
    action, request_id = callback.data.split(":")
    request_id = int(request_id)
    
    async with async_session_maker() as session:
        req = await session.get(TopUpRequest, request_id)
        if not req or req.status != "PENDING":
            await callback.answer("⚠️ Заявка уже обработана или не найдена.")
            return
            
        user = await session.get(User, req.user_id)
        
        if action == "tr_approve":
            req.status = "APPROVED"
            user.points += req.amount
            session.add(Transaction(
                user_id=user.id,
                amount=req.amount,
                type=TransactionType.REFILL,
                description=f"Пополнение баланса через {req.method}"
            ))
            msg = f"✅ <b>Ваша заявка на пополнение одобрена!</b>\nНачислено <b>{req.amount}</b> баллов."
            admin_msg = f"✅ Заявка #{request_id} одобрена. Баллы начислены."
        else:
            req.status = "REJECTED"
            msg = f"❌ <b>Ваша заявка на пополнение отклонена.</b>\nЕсли вы считаете это ошибкой, свяжитесь с поддержкой."
            admin_msg = f"❌ Заявка #{request_id} отклонена."
            
        await session.commit()
        
    try:
        await callback.bot.send_message(user.telegram_id, msg, parse_mode="HTML")
    except Exception: pass
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(admin_msg)
    await callback.message.answer(admin_msg)
