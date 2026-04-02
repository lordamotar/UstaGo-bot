from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Main administrative keyboard."""
    keyboard = [
        [KeyboardButton(text="⏳ Заявки мастеров"), KeyboardButton(text="📋 Все заказы")],
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="💰 Пополнение баллов")],
        [KeyboardButton(text="🔙 Выход из админки")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_back_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="admin_back")]
    ])
