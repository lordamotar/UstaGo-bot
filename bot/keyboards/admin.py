from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Main administrative keyboard."""
    keyboard = [
        [KeyboardButton(text="⏳ Заявки мастеров"), KeyboardButton(text="📋 Все заказы")],
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="💰 Пополнение баллов")],
        [KeyboardButton(text="🗂️ Категории"), KeyboardButton(text="📍 Районы")],
        [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="🚫 Баны")],
        [KeyboardButton(text="🔙 Выход из админки")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_list_management_keyboard(items: list, prefix: str) -> InlineKeyboardMarkup:
    """Builds a keyboard for lists like categories or districts with delete buttons."""
    keyboard = []
    for item in items:
        keyboard.append([
            InlineKeyboardButton(text=f"🗑️ {item.name}", callback_data=f"{prefix}_del:{item.id}")
        ])
    keyboard.append([InlineKeyboardButton(text=f"➕ Добавить", callback_data=f"{prefix}_add")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_back_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="admin_back")]
    ])
