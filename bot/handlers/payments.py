from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from database.engine import async_session_maker
from database.models import User, SystemSettings, TopUpRequest
from bot.keyboards.client import get_payment_methods_keyboard
from bot.states import TopUpStates
from bot.core.config import config
from sqlalchemy import select

router = Router()

# @router.message(F.text == "💰 Пополнить баланс")
# async def refill_balance_start(message: Message):
#     """Shows available payment methods based on admin settings."""
#     async with async_session_maker() as session:
#         settings = await session.get(SystemSettings, 1)
#         if not settings or (not settings.crypto_enabled and not settings.bank_enabled):
#             await message.answer("❌ Извините, пополнение баланса временно недоступно. Обратитесь в поддержку.")
#             return
#             
#     text = (
#         "💰 <b>Пополнение баланса</b>\n\n"
#         "Выберите удобный способ оплаты ниже. После оплаты вам нужно будет прислать скриншот или фото квитанции для подтверждения."
#     )
#     await message.answer(text, parse_mode="HTML", reply_markup=get_payment_methods_keyboard(settings.crypto_enabled, settings.bank_enabled))

@router.callback_query(F.data == "refill_cancel")
async def cancel_refill(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Пополнение отменено.")
    await callback.answer()

@router.callback_query(F.data.startswith("refill_method:"))
async def refill_method_choice(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":")[1]
    await state.update_data(payment_method=method)
    
    await state.set_state(TopUpStates.entering_amount)
    await callback.message.edit_text(
        f"💳 Вы выбрали: <b>{method.upper()}</b>\n\n"
        "Введите сумму пополнения (в баллах) числом:",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TopUpStates.entering_amount)
async def process_refill_amount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите число (только цифры).")
        return
        
    amount = int(message.text)
    if amount <= 0:
        await message.answer("⚠️ Сумма должна быть больше 0.")
        return
        
    await state.update_data(amount=amount)
    data = await state.get_data()
    method = data['payment_method']
    
    async with async_session_maker() as session:
        settings = await session.get(SystemSettings, 1)
        details = (settings.crypto_address if method == "crypto" else settings.bank_details) or "реквизиты не установлены"
        
    kb = []
    is_link = details.startswith("http")
    
    if method == "crypto":
        kb.append([InlineKeyboardButton(text="🔗 Telegram Wallet", url="https://t.me/wallet")])
    elif method == "bank" and is_link:
        kb.append([InlineKeyboardButton(text="🏛 Перейти к оплате", url=details)])
        
    kb_markup = InlineKeyboardMarkup(inline_keyboard=kb) if kb else None

    # Use <code> for copy-on-tap unless it's a redirect URL
    formatted_details = f"<code>{details}</code>" if not is_link else "нажмите кнопку ниже"

    instr = (
        f"💎 <b>Инструкция по оплате ({method.upper()}):</b>\n\n"
        f"💵 Сумма к пополнению: <b>{amount} баллов</b>\n"
        f"🔹 Реквизиты: {formatted_details}\n\n"
        "📍 <b>ВАЖНО:</b> После перевода нажмите на 📎 <b>скрепку</b> внизу и отправьте <b>фото/скриншот</b> квитанции об оплате.\n\n"
        "Ваша заявка будет проверена администратором в ближайшее время."
    )
    await state.set_state(TopUpStates.uploading_receipt)
    await message.answer(instr, parse_mode="HTML", reply_markup=kb_markup)

@router.message(TopUpStates.uploading_receipt, F.photo)
async def process_refill_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data['amount']
    method = data['payment_method']
    photo_id = message.photo[-1].file_id
    
    async with async_session_maker() as session:
        # Get DB User ID
        res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = res.scalar_one()
        
        # Create request
        new_request = TopUpRequest(
            user_id=user.id,
            amount=amount,
            method=method,
            receipt_photo=photo_id,
            status="PENDING"
        )
        session.add(new_request)
        await session.commit()
    
    await state.clear()
    await message.answer("✅ <b>Ваша заявка принята!</b>\nАдминистратор проверит платеж и начислит баллы. Вы получите уведомление.", parse_mode="HTML")
    
    # Notify Admins
    admin_notif = (
        f"💰 <b>Новая заявка на пополнение!</b>\n\n"
        f"👤 От: {user.full_name} (<code>{user.telegram_id}</code>)\n"
        f"💵 Сумма: <b>{amount}</b>\n"
        f"🔹 Метод: {method}\n\n"
        "Перейдите в админ-панель -> Настройки оплаты -> Заявки, чтобы одобрить."
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_photo(admin_id, photo_id, caption=admin_notif, parse_mode="HTML")
        except Exception: pass

@router.message(TopUpStates.uploading_receipt)
async def process_refill_receipt_invalid(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте именно <b>фото/скриншот</b> квитанции (используйте 📎 <b>скрепку</b>).")
