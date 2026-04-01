from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_master_main_menu() -> ReplyKeyboardMarkup:
    """Returns the main menu for registered Masters."""
    keyboard = [
        [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="⭐ Рейтинг и отзывы")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💰 Баланс")],
        [KeyboardButton(text="🔗 Рефералы"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="🆘 Помощь"), KeyboardButton(text="🏠 Выход в главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_profile_menu() -> ReplyKeyboardMarkup:
    """Buttons inside the Profile section."""
    keyboard = [
        [KeyboardButton(text="✏️ Редактировать")],
        [KeyboardButton(text="📸 Фото")],
        [KeyboardButton(text="🎗️ Мой статус"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🔙 Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_orders_menu() -> ReplyKeyboardMarkup:
    """Buttons inside My Orders section."""
    keyboard = [
        [KeyboardButton(text="🔄 Доступные заказы")],
        [KeyboardButton(text="⏳ Мои активные заказы")],
        [KeyboardButton(text="✅ Выполненные заказы")],
        [KeyboardButton(text="🔙 Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_balance_menu() -> ReplyKeyboardMarkup:
    """Buttons inside Balance section."""
    keyboard = [
        [KeyboardButton(text="💸 Вывести баллы"), KeyboardButton(text="💸 Пополнить баллы")],
        [KeyboardButton(text="📜 История операций")],
        [KeyboardButton(text="🔙 Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_settings_menu() -> ReplyKeyboardMarkup:
    """Buttons inside Settings section."""
    keyboard = [
        [KeyboardButton(text="🔔 Уведомления"), KeyboardButton(text="📍 Районы работы")],
        [KeyboardButton(text="🚫 Режим «Не беспокоить»")],
        [KeyboardButton(text="🔑 Сменить статус видимости")],
        [KeyboardButton(text="🔙 Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
