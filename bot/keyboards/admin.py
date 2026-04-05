from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Main administrative keyboard."""
    keyboard = [
        [KeyboardButton(text="⏳ Заявки мастеров"), KeyboardButton(text="📋 Все заказы")],
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="💰 Пополнение баллов")],
        [KeyboardButton(text="🗂️ Категории"), KeyboardButton(text="📍 Районы")],
        [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="⚙️ Настройки оплаты")],
        [KeyboardButton(text="🚫 Баны"), KeyboardButton(text="🔙 Выход из админки")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_payment_settings_keyboard(crypto_on: bool, bank_on: bool) -> InlineKeyboardMarkup:
    """Keyboard to manage payment methods in admin panel."""
    crypto_text = "🟢 Крипто: ВКЛ" if crypto_on else "🔴 Крипто: ВЫКЛ"
    bank_text = "🟢 Банк: ВКЛ" if bank_on else "🔴 Банк: ВЫКЛ"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=crypto_text, callback_data="pay_toggle:crypto")],
        [InlineKeyboardButton(text="📝 Изменить адрес (Крипта)", callback_data="pay_edit:crypto")],
        [InlineKeyboardButton(text=bank_text, callback_data="pay_toggle:bank")],
        [InlineKeyboardButton(text="📝 Изменить реквизиты (Банк)", callback_data="pay_edit:bank")],
        [InlineKeyboardButton(text="📦 Все заявки на пополнение", callback_data="pay_requests")]
    ])

def get_topup_review_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Approval or rejection keyboard for the admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"tr_approve:{request_id}")],
        [InlineKeyboardButton(text="❌ Отказать", callback_data=f"tr_reject:{request_id}")]
    ])

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
