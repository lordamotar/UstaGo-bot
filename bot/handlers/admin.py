from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command
from bot.core.config import config
from database.engine import async_session_maker
from database.models import User, MasterProfile, MasterStatus, UserRole, Transaction, TransactionType, Order, OrderStatus, Category, District
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from bot.keyboards.master import get_master_main_menu
from bot.keyboards.admin import get_admin_main_menu, get_admin_back_inline, get_list_management_keyboard
from bot.states import AdminStates
from aiogram.fsm.context import FSMContext

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
        
        # Referral reward for the inviter
        if user.referred_by:
            inviter = await session.get(User, user.referred_by)
            if inviter:
                inviter.points += 100
                session.add(Transaction(
                    user_id=inviter.id,
                    amount=100,
                    type=TransactionType.REFERRAL_BONUS,
                    description=f"Бонус за регистрацию мастера {user.full_name}"
                ))
                try:
                    await callback.bot.send_message(
                        inviter.telegram_id,
                        f"🎁 <b>Бонус за реферала!</b>\n\n"
                        f"Приглашенный вами мастер <b>{user.full_name}</b> успешно прошел проверку.\n"
                        f"Вам начислено <b>100 баллов</b>!",
                        parse_mode="HTML"
                    )
                except Exception: pass
                
        tg_id = user.telegram_id
        is_target_admin = tg_id in config.ADMIN_IDS
        await session.commit()
    await callback.message.edit_text(f"✅ Мастер #{master_id} одобрен!")
    try:
        await callback.bot.send_message(tg_id, "🎉 Ваш профиль мастера одобрен!", reply_markup=get_master_main_menu(is_admin=is_target_admin))
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
