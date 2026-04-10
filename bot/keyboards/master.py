from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def build_districts_keyboard(selected_names: list, all_districts: list) -> InlineKeyboardMarkup:
    """Builds the multi-select district keyboard in 2 columns."""
    keyboard = []
    row = []
    for dist_name in all_districts:
        icon = "✅ " if dist_name in selected_names else ""
        row.append(InlineKeyboardButton(text=f"{icon}{dist_name}", callback_data=f"dist_toggle:{dist_name}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="💾 Сохранить", callback_data="dist_save")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_edit_profile_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline menu for choosing which field to edit."""
    keyboard = [
        [InlineKeyboardButton(text="📛 Имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="🗂️ Категории", callback_data="edit_categories")],
        [InlineKeyboardButton(text="📝 Описание «О себе»", callback_data="edit_description")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_photo_management_keyboard(count: int) -> InlineKeyboardMarkup:
    """Inline menu for managing portfolio photos."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить фото", callback_data="add_photos")],
        # Bulk delete removed, individual buttons used under photos
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_master_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Returns the main menu for registered Masters."""
    keyboard = [
        [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="⭐ Рейтинг и отзывы")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💰 Баланс")],
        [KeyboardButton(text="🔗 Рефералы"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="📩 Обратная связь"), KeyboardButton(text="🏠 Выход в главное меню")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="👨‍✈️ Админ-панель")])
        
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

def get_refill_methods_keyboard(crypto_on: bool, bank_on: bool) -> InlineKeyboardMarkup:
    """Keyboard for selecting active payment methods under Balance."""
    keyboard = []
    if crypto_on:
        keyboard.append([InlineKeyboardButton(text="💎 Криптовалюта", callback_data="refill_master:crypto")])
    if bank_on:
        keyboard.append([InlineKeyboardButton(text="💳 Банковская карта / Ссылка", callback_data="refill_master:bank")])
    
    keyboard.append([InlineKeyboardButton(text="📜 История операций", callback_data="refill_history")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
