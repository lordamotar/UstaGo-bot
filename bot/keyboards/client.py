from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_inline_categories(categories: list) -> InlineKeyboardMarkup:
    """Inline keyboard for client selecting a category in 2 columns."""
    keyboard = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(text=cat.name, callback_data=f"sel_cat:{cat.id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_inline_districts(districts: list) -> InlineKeyboardMarkup:
    """Inline keyboard for selecting a district in 2 columns."""
    keyboard = []
    row = []
    for d in districts:
        row.append(InlineKeyboardButton(text=d.name, callback_data=f"sel_dist:{d.id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
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
        [KeyboardButton(text="⏳ Мои заявки")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="📩 Обратная связь")],
        [KeyboardButton(text="❓ FAQ"), KeyboardButton(text="🔨 Стать мастером")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="👨‍✈️ Админ-панель")])
        
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_payment_methods_keyboard(crypto_on: bool, bank_on: bool) -> InlineKeyboardMarkup:
    """Keyboard for selecting active payment methods."""
    keyboard = []
    if crypto_on:
        keyboard.append([InlineKeyboardButton(text="🔗 Криптовалюта (BTC/USDT)", callback_data="refill_method:crypto")])
    if bank_on:
        keyboard.append([InlineKeyboardButton(text="🏛 Банковский перевод (Карта/Ссылка)", callback_data="refill_method:bank")])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="refill_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
