from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_role_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Returns the keyboard for role selection."""
    keyboard = [
        [
            KeyboardButton(text="👤 Я клиент"),
            KeyboardButton(text="🔨 Я мастер")
        ]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="👨‍✈️ Админ-панель")])
        
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

def build_categories_keyboard(selected_ids: set, mock_categories: list) -> InlineKeyboardMarkup:
    """Builds the multi-select category keyboard."""
    keyboard = []
    for cat in mock_categories:
        icon = "✅ " if cat["id"] in selected_ids else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"{icon}{cat['name']}",
                callback_data=f"cat_toggle:{cat['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="💾 Сохранить и продолжить", callback_data="cat_save")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_photo_done_keyboard() -> InlineKeyboardMarkup:
    """Keyboard after uploading a photo."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Готово, к следующему шагу", callback_data="photo_done")]
    ])

def get_phone_sharing_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for phone number sharing."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
