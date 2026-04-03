from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_inline_categories(categories: list) -> InlineKeyboardMarkup:
    """Inline keyboard for client selecting a category."""
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(text=cat.name, callback_data=f"sel_cat:{cat.id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_inline_districts(districts: list) -> InlineKeyboardMarkup:
    """Inline keyboard for selecting a district."""
    keyboard = []
    for d in districts:
        keyboard.append([InlineKeyboardButton(text=d.name, callback_data=f"sel_dist:{d.id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_order_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="order_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="order_cancel")]
    ])

def get_client_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Main menu for clients."""
    keyboard = [
        [KeyboardButton(text="➕ Создать заявку")],
        [KeyboardButton(text="⏳ Мои заявки"), KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="📩 Обратная связь"), KeyboardButton(text="🔨 Стать мастером")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="👨‍✈️ Админ-панель")])
        
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
