from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.states import OrderCreationStates
from database.engine import async_session_maker
from database.models import User, Order, Category, District, OrderStatus, MasterProfile, UserRole
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from bot.keyboards.client import get_inline_categories, get_inline_districts, get_order_confirmation_keyboard
from bot.core.config import config
from bot.utils.text import esc

router = Router()

@router.message(F.text == "➕ Создать заявку")
async def start_order_creation(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        user_stmt = select(User).where(User.telegram_id == message.from_user.id)
        user = (await session.execute(user_stmt)).scalar_one_or_none()
        
    if not user or not user.phone_number:
        await state.set_state(OrderCreationStates.requiring_phone)
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        await message.answer(
            "📱 Для создания заявки нам необходим ваш <b>номер телефона</b>.\n\n"
            "Нажмите внизу кнопку <b>«📱 Поделиться контактом»</b> или прикрепите номер через 📎 (скрепку).",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    await state.set_state(OrderCreationStates.selecting_category)
    async with async_session_maker() as session:
        res = await session.execute(select(Category).where(Category.is_active == True))
        categories = res.scalars().all()
    
    await message.answer(
        "🏷️ <b>Выберите категорию услуги:</b>",
        parse_mode="HTML",
        reply_markup=get_inline_categories(categories)
    )

@router.message(OrderCreationStates.requiring_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    async with async_session_maker() as session:
        await session.execute(update(User).where(User.telegram_id == message.from_user.id).values(phone_number=phone))
        await session.commit()
    
    await message.answer(f"✅ Номер {phone} привязан к вашему профилю.")
    await state.set_state(OrderCreationStates.selecting_category)
    async with async_session_maker() as session:
        res = await session.execute(select(Category).where(Category.is_active == True))
        categories = res.scalars().all()
    
    from bot.keyboards.client import get_client_main_menu
    is_admin = message.from_user.id in config.ADMIN_IDS
    await message.answer("🏷️ <b>Выберите категорию услуги:</b>", parse_mode="HTML", reply_markup=get_inline_categories(categories))
    await message.answer("🛠 Используйте кнопки снизу для навигации.", reply_markup=get_client_main_menu(is_admin=is_admin))

@router.callback_query(OrderCreationStates.selecting_category, F.data.startswith("sel_cat:"))
async def process_cat_selection(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(OrderCreationStates.entering_description)
    await callback.message.edit_text(
        "📝 <b>Опишите, что нужно сделать:</b>\n\n"
        "Напишите сообщение в поле ввода ниже и отправьте его.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(OrderCreationStates.entering_description)
async def process_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(OrderCreationStates.entering_budget)
    await message.answer("💰 <b>Укажите ваш бюджет (в тенге):</b>\nОтправьте число или напишите «договорная».", parse_mode="HTML")

@router.message(OrderCreationStates.entering_budget)
async def process_budget(message: Message, state: FSMContext):
    from bot.utils.parsing import parse_amount
    budget_text = message.text or ""
    budget = parse_amount(budget_text)
    
    await state.update_data(budget=budget, budget_text=budget_text)
    await state.set_state(OrderCreationStates.selecting_district)
    
    async with async_session_maker() as session:
        res = await session.execute(select(District))
        districts = res.scalars().all()
    
    await message.answer("📍 <b>В каком районе нужно выполнить работу?</b>", parse_mode="HTML", reply_markup=get_inline_districts(districts))

@router.callback_query(OrderCreationStates.selecting_district, F.data.startswith("sel_dist:"))
async def process_dist_selection(callback: CallbackQuery, state: FSMContext):
    dist_id = int(callback.data.split(":")[1])
    await state.update_data(district_id=dist_id)
    await state.set_state(OrderCreationStates.uploading_photos)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📸 Пропустить", callback_data="order_skip_photos")
    ]])
    await callback.message.edit_text(
        "🖼 <b>Добавьте фото (необязательно)</b>\n\n"
        "Вы можете отправить до 3 фотографий (нажмите 📎 <b>скрепку</b> и выберите файл).\n"
        "Или нажмите кнопку ниже <b>«📸 Пропустить»</b>, если фото не требуются.",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()

@router.message(OrderCreationStates.uploading_photos, F.photo)
async def process_order_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("order_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(order_photos=photos)
    
    if len(photos) >= 3:
        await finish_order_photos(message, state)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Готово", callback_data="order_finish_photos")
        ]])
        await message.answer(f"✅ Фото получено ({len(photos)}/3). Можно скинуть еще или нажать «Готово».", reply_markup=kb)

@router.callback_query(F.data.in_(["order_skip_photos", "order_finish_photos"]))
async def finish_order_photos_callback(callback: CallbackQuery, state: FSMContext):
    await finish_order_photos(callback.message, state)
    await callback.answer()

async def finish_order_photos(message: Message, state: FSMContext):
    await state.set_state(OrderCreationStates.confirming)
    data = await state.get_data()
    async with async_session_maker() as session:
        cat = await session.get(Category, data['category_id'])
        dist = await session.get(District, data['district_id'])
    
    photos_count = len(data.get("order_photos", []))
    text = (
        "📊 <b>Проверьте вашу заявку:</b>\n\n"
        f"🏷️ Категория: {esc(cat.name)}\n"
        f"📝 Описание: {esc(data['description'])}\n"
        f"💰 Бюджет: {data['budget_text']}\n"
        f"📍 Район: {esc(dist.name)}\n"
        f"🖼 Фото: {photos_count if photos_count > 0 else 'Нет'}\n\n"
        "<b>Опубликовать?</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_order_confirmation_keyboard())

@router.callback_query(OrderCreationStates.confirming, F.data == "order_confirm")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    async with async_session_maker() as session:
        user_stmt = select(User).where(User.telegram_id == callback.from_user.id)
        user = (await session.execute(user_stmt)).scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=callback.from_user.id,
                full_name=callback.from_user.full_name,
                username=callback.from_user.username
            )
            session.add(user)
            await session.flush()
        
        user_id = user.id
        
        new_order = Order(
            client_id=user_id,
            category_id=data['category_id'],
            district_id=data['district_id'],
            description=data['description'],
            budget=data['budget'],
            photo_ids=data.get("order_photos", []),
            status=OrderStatus.NEW
        )
        session.add(new_order)
        await session.flush()
        order_id = new_order.id
        
        cat = await session.get(Category, data['category_id'])
        dist = await session.get(District, data['district_id'])
        
        # Notify Masters
        from bot.services.reminders import find_masters_for_order, is_in_dnd
        masters_to_notify = await find_masters_for_order(session, data['category_id'], data['district_id'])

        from datetime import datetime
        from datetime import timezone, timedelta
        now_str = datetime.now(timezone(timedelta(hours=config.TZ_OFFSET_HOURS))).strftime("%H:%M")

        has_photos = len(data.get("order_photos", [])) > 0
        photo_mark = "\n🖼 <b>Есть фото</b>" if has_photos else ""

        for master in masters_to_notify:
            if is_in_dnd(now_str, master.dnd_start, master.dnd_end):
                continue
            try:
                if master.telegram_id == callback.from_user.id:
                    continue
                    
                master_text = (
                    f"🆕 <b>Новый заказ: {esc(cat.name)}</b>\n\n"
                    f"📝 {esc(data['description'])}\n"
                    f"💰 Бюджет: {data['budget'] or 'Договорная'}\n"
                    f"📍 Район: {esc(dist.name)}"
                    f"{photo_mark}"
                )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📥 Посмотреть и откликнуться", callback_data=f"master_view_order:{order_id}")
                ]])
                
                await callback.bot.send_message(master.telegram_id, master_text, parse_mode="HTML", reply_markup=keyboard)
            except Exception:
                pass
        
        await session.commit()
        
    await callback.message.edit_text(f"🚀 <b>Заявка №{order_id} опубликована!</b>\n\nМастера получили уведомления и скоро начнут откликаться.", parse_mode="HTML")
    await state.clear()
    from bot.keyboards.client import get_client_main_menu
    is_admin = callback.from_user.id in config.ADMIN_IDS
    await callback.message.answer("Вы в главном меню.", reply_markup=get_client_main_menu(is_admin=is_admin))
    await callback.answer()


@router.callback_query(F.data.startswith("order_remind:"))
async def order_remind_choice(callback: CallbackQuery):
    """Client's answer to «no bids yet — remind the masters?»."""
    from bot.services import reminders
    try:
        _, order_id, mode = callback.data.split(":")
        order_id = int(order_id)
    except ValueError:
        await callback.answer()
        return

    async with async_session_maker() as session:
        result = await reminders.set_client_choice(session, order_id, callback.from_user.id, mode)
        await session.commit()

    if result == "ok":
        if mode == reminders.MODE_SKIP:
            text = f"Хорошо, по заявке №{order_id} ничего не отправляю."
        else:
            who = "всем мастерам категории" if mode == reminders.MODE_ALL else "мастерам, которые ещё не открывали заказ"
            when = "Отправляю сейчас." if reminders.in_working_hours() else (
                f"Отправлю в рабочее время ({config.WORK_HOURS_START:02d}:00–{config.WORK_HOURS_END:02d}:00)."
            )
            text = f"🔔 Напомню {who}. {when}"
    else:
        text = {
            "closed": "Заявка уже закрыта.",
            "has_bids": "По заявке уже появились отклики — напоминание не нужно. 🎉",
            "already": "Вы уже ответили на этот вопрос.",
        }.get(result, "Заявка не найдена.")
    try:
        await callback.message.edit_text(text)
    except Exception:
        await callback.message.answer(text)
    await callback.answer()
