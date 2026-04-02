from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from bot.keyboards.master import get_master_main_menu
from bot.states import RegistrationStates
from sqlalchemy import select
from bot.core.config import config
from database.engine import async_session_maker
from database.models import User, MasterProfile, MasterStatus, Category, UserRole

router = Router()

from bot.keyboards.registration import (
    build_categories_keyboard, 
    get_photo_done_keyboard, 
    get_phone_sharing_keyboard
)

@router.message(RegistrationStates.entering_name)
async def process_name(message: Message, state: FSMContext):
    """1. Saves name and asks for categories."""
    await state.update_data(full_name=message.text)
    await state.set_state(RegistrationStates.selecting_categories)
    
    async with async_session_maker() as session:
        res = await session.execute(select(Category))
        categories = res.scalars().all()
        cats_list = [{"id": c.id, "name": c.name} for c in categories]
        await state.update_data(all_categories=cats_list, selected_categories=[])
    
    keyboard = build_categories_keyboard(set(), cats_list)
    await message.answer(
        f"Приятно познакомиться, {message.text}!\n\n"
        "2. Выберите категории услуг, которые вы предоставляете (можно несколько):",
        reply_markup=keyboard
    )

@router.callback_query(RegistrationStates.selecting_categories, F.data.startswith("cat_toggle:"))
async def toggle_category(callback: CallbackQuery, state: FSMContext):
    """Handles category multi-selection toggles."""
    cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_categories = set(data.get("selected_categories", []))
    cats_list = data.get("all_categories", [])
    
    if cat_id in selected_categories:
        selected_categories.remove(cat_id)
    else:
        selected_categories.add(cat_id)
        
    await state.update_data(selected_categories=list(selected_categories))
    keyboard = build_categories_keyboard(selected_categories, cats_list)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
         pass
    await callback.answer()


@router.callback_query(RegistrationStates.selecting_categories, F.data == "cat_save")
async def save_categories(callback: CallbackQuery, state: FSMContext):
    """Processes categories, moves to 3. Description."""
    data = await state.get_data()
    selected_categories = data.get("selected_categories", [])
    
    if not selected_categories:
        await callback.answer("⚠️ Выберите хотя бы одну категорию!", show_alert=True)
        return
        
    await state.set_state(RegistrationStates.entering_description)
    await callback.message.edit_text(
        "✅ Категории успешно сохранены!\n\n"
        "3. Напишите краткое описание вашего опыта (1–2 предложения)."
    )
    await callback.answer()


@router.message(RegistrationStates.uploading_photos, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Handles photo uploads (storing file_ids)."""
    data = await state.get_data()
    photos = data.get("photos", [])
    
    # Save the highest resolution photo file_id
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    
    count = len(photos)
    if count >= 3:
        await state.set_state(RegistrationStates.sharing_phone)
        
        keyboard = get_phone_sharing_keyboard()
        await message.answer(
            "Максимум 3 фото получено. 6. Теперь поделитесь вашим номером телефона. "
            "Он будет передаваться клиенту, когда вы договоритесь о заказе.",
            reply_markup=keyboard
        )
    else:
        keyboard = get_photo_done_keyboard()
        await message.answer(
            f"✅ Фото №{count} получено.\n"
            "Вы можете отправить еще (макс. 3) или нажать кнопку ниже, если закончили.",
            reply_markup=keyboard
        )


@router.callback_query(RegistrationStates.uploading_photos, F.data == "photo_done")
async def finish_photos(callback: CallbackQuery, state: FSMContext):
    """6. Finishes photos, moves to phone sharing."""
    await state.set_state(RegistrationStates.sharing_phone)
    
    keyboard = get_phone_sharing_keyboard()
    
    await callback.message.answer(
        "Почти готово! 6. Поделитесь вашим номером телефона. "
        "Он будет передаваться клиенту, когда вы договоритесь о заказе.",
        reply_markup=keyboard
    )
    await callback.answer()
@router.message(RegistrationStates.entering_description)
async def process_description(message: Message, state: FSMContext):
    """4. Saves description and asks for experience."""
    await state.update_data(description=message.text)
    await state.set_state(RegistrationStates.entering_experience)
    await message.answer(
        "Отлично! 4. Сколько лет вы работаете в своей сфере? (Например: 5 лет или 'с 2015 года')"
    )


@router.message(RegistrationStates.entering_experience)
async def process_experience(message: Message, state: FSMContext):
    """5. Saves experience and moves to photo upload."""
    await state.update_data(experience=message.text)
    await state.set_state(RegistrationStates.uploading_photos)
    await state.update_data(photos=[])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить / Готово", callback_data="photo_done")]
    ])
    
    await message.answer(
        "Принято. 5. Теперь отправьте 1–3 фотографии ваших работ.\n"
        "Когда закончите, нажмите кнопку ниже под сообщением.",
        reply_markup=keyboard
    )


@router.message(RegistrationStates.sharing_phone, F.contact)
async def process_phone(message: Message, state: FSMContext):
    """Final registration step: saves everything to database including phone."""
    phone = message.contact.phone_number
    data = await state.get_data()
    
    # DB Save Logic
    async with async_session_maker() as session:
        user_stmt = select(User).where(User.telegram_id == message.from_user.id)
        existing_user = await session.execute(user_stmt)
        user = existing_user.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                full_name=data['full_name'],
                username=message.from_user.username,
                phone_number=phone,
                role=UserRole.MASTER
            )
            session.add(user)
            await session.flush()
        else:
            user.role = UserRole.MASTER
            user.full_name = data['full_name']
            user.phone_number = phone
        
        profile = MasterProfile(
            user_id=user.id,
            description=data['description'],
            experience=data['experience'],
            status=MasterStatus.PENDING
        )
        session.add(profile)
        await session.flush()
        master_profile_id = profile.id
        await session.commit()

    # Notify Admins with action buttons
    admin_text = (
        "🆕 Новая заявка от Мастера!\n\n"
        f"Фио: {data['full_name']}\n"
        f"Телефон: {phone}\n"
        f"Стаж: {data['experience']}\n"
        f"Описание: {data['description']}\n"
        f"TG: @{message.from_user.username or 'no_username'} ({message.from_user.id})"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve:{master_profile_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject:{master_profile_id}")
        ]
    ])
    
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, admin_text, reply_markup=keyboard)
        except Exception:
            pass
    await state.set_state(RegistrationStates.pending_approval)
    
    success_text = (
        "⏳ Анкета отправлена на проверку!\n\n"
        "Мы внимательно проверяем каждого мастера, чтобы сохранить доверие клиентов.\n"
        "Вы уже можете посмотреть возможности вашего личного кабинета под этим сообщением."
    )
    await message.answer(success_text, reply_markup=get_master_main_menu())
