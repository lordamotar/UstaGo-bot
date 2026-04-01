from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.states import RegistrationStates
from sqlalchemy import select
from bot.core.config import config
from database.engine import async_session_maker
from database.models import User, MasterProfile, MasterStatus, Category, UserRole

# Dummy list of subcategories reflecting the PRD
MOCK_CATEGORIES = [
    {"id": 1, "name": "Электрик"},
    {"id": 2, "name": "Сантехник"},
    {"id": 3, "name": "Сборка мебели"},
    {"id": 4, "name": "Вскрытие замков"},
    {"id": 5, "name": "Уборка квартир"},
    {"id": 6, "name": "Мойка окон"}
]

router = Router()

def build_categories_keyboard(selected_ids: set) -> InlineKeyboardMarkup:
    """Builds the multi-select inline keyboard based on selected category IDs."""
    buttons = []
    for cat in MOCK_CATEGORIES:
        is_selected = cat["id"] in selected_ids
        prefix = "✅ " if is_selected else "❌ "
        btn = InlineKeyboardButton(
            text=f"{prefix}{cat['name']}",
            callback_data=f"cat_toggle:{cat['id']}"
        )
        buttons.append([btn])
    buttons.append([InlineKeyboardButton(text="💾 Сохранить", callback_data="cat_save")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(RegistrationStates.entering_name)
async def process_name(message: Message, state: FSMContext):
    """Saves name and asks for experience."""
    await state.update_data(full_name=message.text)
    await state.set_state(RegistrationStates.entering_experience)
    await message.answer(
        f"Приятно познакомиться, {message.text}!\n\n"
        "Сколько лет вы работаете в своей сфере? (Например: 5 лет или 'с 2015 года')"
    )


@router.message(RegistrationStates.entering_experience)
async def process_experience(message: Message, state: FSMContext):
    """Saves experience and moves to category selection."""
    await state.update_data(experience=message.text)
    await state.set_state(RegistrationStates.selecting_categories)
    await state.update_data(selected_categories=[])
    
    keyboard = build_categories_keyboard(set())
    await message.answer(
        "Отлично! Теперь выберите категории услуг, которые вы предоставляете (можно несколько):",
        reply_markup=keyboard
    )


@router.callback_query(RegistrationStates.selecting_categories, F.data.startswith("cat_toggle:"))
async def toggle_category(callback: CallbackQuery, state: FSMContext):
    """Handles category multi-selection toggles."""
    cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_categories = set(data.get("selected_categories", []))
    
    if cat_id in selected_categories:
        selected_categories.remove(cat_id)
    else:
        selected_categories.add(cat_id)
        
    await state.update_data(selected_categories=list(selected_categories))
    keyboard = build_categories_keyboard(selected_categories)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
         pass
    await callback.answer()


@router.callback_query(RegistrationStates.selecting_categories, F.data == "cat_save")
async def save_categories(callback: CallbackQuery, state: FSMContext):
    """Processes the save action, moves to photo upload."""
    data = await state.get_data()
    selected_categories = data.get("selected_categories", [])
    
    if not selected_categories:
        await callback.answer("⚠️ Выберите хотя бы одну категорию!", show_alert=True)
        return
        
    await state.set_state(RegistrationStates.uploading_photos)
    await state.update_data(photos=[])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить / Готово", callback_data="photo_done")]
    ])
    
    await callback.message.edit_text(
        "✅ Категории успешно сохранены!\n\n"
        "Теперь отправьте 1–3 фотографии ваших работ.\n"
        "Когда закончите, нажмите кнопку ниже.",
        reply_markup=keyboard
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
        await state.set_state(RegistrationStates.entering_description)
        await message.answer("Максимум 3 фото получено. Теперь напишите краткое описание вашего опыта.")
    else:
        await message.answer(f"Получено фото №{count}. Можете отправить еще или нажать 'Готово'.")


@router.callback_query(RegistrationStates.uploading_photos, F.data == "photo_done")
async def finish_photos(callback: CallbackQuery, state: FSMContext):
    """Finishes photo step even if 0 or 1-2 photos sent."""
    await state.set_state(RegistrationStates.entering_description)
    await callback.message.edit_text("Отлично! Теперь напишите краткое описание вашего опыта (1-2 предложения).")
    await callback.answer()


@router.message(RegistrationStates.entering_description)
async def process_description(message: Message, state: FSMContext):
    """Final registration step: saves everything to database."""
    description = message.text
    data = await state.get_data()
    
    # DB Save Logic
    async with async_session_maker() as session:
        # Check if user already exists
        user_stmt = select(User).where(User.telegram_id == message.from_user.id)
        existing_user = await session.execute(user_stmt)
        user = existing_user.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                full_name=data['full_name'],
                username=message.from_user.username,
                role=UserRole.MASTER
            )
            session.add(user)
            await session.flush()
        else:
            user.role = UserRole.MASTER
            user.full_name = data['full_name']
        
        # Create or update Master Profile
        # Note: In a real app we'd need to create categories in DB first.
        # For MVP, we'll just handle the master_profile record.
        profile = MasterProfile(
            user_id=user.id,
            description=description,
            experience=data['experience'],
            status=MasterStatus.PENDING
        )
        session.add(profile)
        await session.flush()  # To get the profile.id
        master_profile_id = profile.id
        await session.commit()

    # Notify Admins with action buttons
    admin_text = (
        "🆕 Новая заявка от Мастера!\n\n"
        f"Фио: {data['full_name']}\n"
        f"Стаж: {data['experience']}\n"
        f"Описание: {description}\n"
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
        "Мы пришлем вам уведомление, как только ваш профиль будет одобрен."
    )
    await message.answer(success_text)
