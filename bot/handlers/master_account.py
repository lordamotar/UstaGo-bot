from aiogram import Router, F, types
from aiogram.types import Message
from sqlalchemy import select
from database.engine import async_session_maker
from database.models import User, MasterProfile, MasterStatus, Category
from bot.keyboards.master import get_master_main_menu, get_profile_menu, get_orders_menu, get_balance_menu, get_settings_menu

router = Router()

@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message):
    """
    Shows master profile and submenu.
    """
    from sqlalchemy.orm import selectinload
    async with async_session_maker() as session:
        stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.master_profile:
            await message.answer("❌ Профиль мастера не найден. Попробуйте зарегистрироваться заново.")
            return

        if not user:
            return

        profile = user.master_profile
        points = user.points
        
        status_emoji = "🎗️ Аккредитован" if profile.status == MasterStatus.APPROVED else "⏳ На модерации"
        
        # Format profile message
        text = (
            f"👤 *Ваш профиль*\n"
            f"Имя: {user.full_name}\n"
            f"Рейтинг: {profile.rating} ⭐\n"
            f"Статус: {status_emoji}\n"
            f"Баланс: {points} баллов\n\n"
            f"Описание: {profile.description or '—'}\n"
            f"Стаж: {profile.experience or '—'}"
        )
        
        await message.answer(text, parse_mode="Markdown", reply_markup=get_profile_menu())

@router.message(F.text == "📋 Мои заказы")
async def show_orders_menu(message: Message):
    await message.answer("📋 Выберите категорию заказов:", reply_markup=get_orders_menu())

@router.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    async with async_session_maker() as session:
        stmt = select(User.points).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        points = res.scalar() or 0
        
    text = (
        f"💰 Ваш баланс: {points} баллов\n\n"
        "Лицензия на один контакт: 50 баллов.\n"
        "Берется только в случае, если клиент выбрал вас."
    )
    await message.answer(text, reply_markup=get_balance_menu())

@router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message):
    await message.answer("⚙️ Настройки профиля и уведомлений:", reply_markup=get_settings_menu())

@router.message(F.text == "🔙 Назад в меню")
async def return_to_main_master_menu(message: Message):
    await message.answer("📋 Главное меню мастера", reply_markup=get_master_main_menu())

@router.message(F.text == "🏠 Выход в главное меню")
async def exit_to_client_mode(message: Message):
    from bot.handlers.start import get_role_keyboard
    await message.answer("🔄 Вы переключились в режим клиента.", reply_markup=get_role_keyboard())

# --- PROFILE SUBMENU ---
@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    # Mock stats for now
    text = (
        "📊 *Статистика*\n\n"
        "Выполнено заказов: 0\n"
        "Отзывов получено: 0\n"
        "Средний чек: —\n"
        "Доход за месяц: 0 баллов"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🎗️ Мой статус")
async def show_accreditation(message: Message):
    text = (
        "🎗️ *Аккредитация мастера*\n\n"
        "Ваш профиль проходит проверку модератором.\n"
        "Проверенные мастера получают:\n"
        "1. Приоритет в списке (выше других).\n"
        "2. Метка «Проверено» в профиле.\n"
        "3. Больше доверия от заказчиков."
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "✏️ Редактировать")
async def edit_profile_start(message: Message):
    await message.answer("🛠️ Функция редактирования профиля будет доступна в следующем обновлении.")

@router.message(F.text == "📸 Фото")
async def edit_photos_start(message: Message):
    await message.answer("📸 Функция обновления портфолио будет доступна в следующем обновлении.")

# --- ORDERS SUBMENU ---
@router.message(F.text == "🔄 Доступные заказы")
async def show_available_orders(message: Message):
    await message.answer("🔄 Список новых заказов пуст. Мы сообщим вам, когда появится работа в ваших категориях!")

@router.message(F.text == "⏳ Мои активные заказы")
async def show_active_orders(message: Message):
    await message.answer("⏳ У вас пока нет активных заказов. Откликнитесь на заявку в списке доступных!")

@router.message(F.text == "✅ Выполненные заказы")
async def show_completed_orders(message: Message):
    await message.answer("✅ В вашей истории пока нет завершенных заказов.")

# --- BALANCE SUBMENU ---
@router.message(F.text == "💸 Вывести баллы")
@router.message(F.text == "💸 Пополнить баллы")
async def balance_placeholder(message: Message):
    await message.answer("🚧 Финансовые операции пока производятся через администратора. Функция оплаты в боте скоро появится.")

@router.message(F.text == "📜 История операций")
async def show_balance_history(message: Message):
    await message.answer("📜 История операций пока пуста.")

# --- SETTINGS SUBMENU ---
@router.message(F.text.in_({"🔔 Уведомления", "📍 Районы работы", "🚫 Режим «Не беспокоить»", "🔑 Сменить статус видимости"}))
async def settings_placeholders(message: Message):
    await message.answer(f"⚙️ Раздел «{message.text}» находится в разработке.")

@router.message(F.text == "🆘 Помощь")
async def show_help(message: Message):
    text = (
        "🆘 *Центр помощи*\n\n"
        "1. Как получить аккредитацию? Загрузите реальные фото и дождитесь проверки.\n"
        "2. Как работают баллы? Вы платите за контакт с клиентом.\n"
        "3. Почему нет заказов? Проверьте настройки видимости в Профиле.\n\n"
        "Нужен человек? Свяжитесь с @admin"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🔗 Рефералы")
async def show_referrals(message: Message):
    # Referral link based on bot username
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"
    
    text = (
        "🔗 *Реферальная программа*\n\n"
        f"Ваша ссылка: `{ref_link}`\n\n"
        "За каждого мастера, который пройдет модерацию по вашей ссылке, вы получите 50 баллов!"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "⭐ Рейтинг и отзывы")
async def show_rating(message: Message):
    await message.answer("⭐ Ваша статистика отзывов:\nПока нет отзывов (раздел в разработке).")
