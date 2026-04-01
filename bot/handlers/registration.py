from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.states import RegistrationStates

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
    
    # Normally we'd fetch this dynamically from DB grouped by parents.
    for cat in MOCK_CATEGORIES:
        is_selected = cat["id"] in selected_ids
        prefix = "✅ " if is_selected else "❌ "
        
        btn = InlineKeyboardButton(
            text=f"{prefix}{cat['name']}",
            callback_data=f"cat_toggle:{cat['id']}"
        )
        buttons.append([btn])  # One per row for clarity, or group by 2
        
    # Add Save button
    buttons.append([InlineKeyboardButton(text="💾 Сохранить", callback_data="cat_save")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "Регистрация Мастера")  # Mock entry point
async def start_category_selection(message: Message, state: FSMContext):
    """Master arrives at the category selection stage."""
    await state.set_state(RegistrationStates.selecting_categories)
    # Initialize an empty set in FSM memory for selected categories
    await state.update_data(selected_categories=[])
    
    keyboard = build_categories_keyboard(set())
    await message.answer(
        "Выберите категории услуг, которые вы предоставляете (можно несколько):",
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
    
    # Update the keyboard in-place without throwing error if content is identical
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
         pass # Ignore 'message is not modified' errors

    await callback.answer()

@router.callback_query(RegistrationStates.selecting_categories, F.data == "cat_save")
async def save_categories(callback: CallbackQuery, state: FSMContext):
    """Processes the save action, validating at least 1 selection."""
    data = await state.get_data()
    selected_categories = data.get("selected_categories", [])
    
    if not selected_categories:
        await callback.answer("⚠️ Выберите хотя бы одну категорию!", show_alert=True)
        return
        
    # Selected successfully
    await state.set_state(RegistrationStates.uploading_photos)
    await callback.message.edit_text(
        "✅ Категории успешно сохранены!\n\n"
        "Теперь отправьте 1-3 фотографии ваших работ (или нажмите 'Пропустить', хотя с фото клиенты доверяют больше)."
    )
    await callback.answer()
