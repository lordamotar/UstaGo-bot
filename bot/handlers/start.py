from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from bot.states import RegistrationStates

from sqlalchemy import select
from database.engine import async_session_maker
from database.models import User, UserRole

router = Router()

from bot.keyboards.registration import get_role_keyboard

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handles the /start command."""
    await state.clear() # Очищаем состояние стейт-машины, если пользователь его прервал
    
    text = (
        "🔧 Добро пожаловать в «Семей-Мастер»!\n\n"
        "Мы найдём проверенных мастеров в вашем районе.\n"
        "Всё просто:\n"
        "1. Нажмите «Создать заявку»\n"
        "2. Опишите задачу и укажите цену\n"
        "3. Получите отклики от мастеров за минуту\n\n"
        "🎁 Ваш первый заказ — бонус 100 баллов.\n\n"
        "👉 Кто вы?"
    )
    
    await message.answer(text, reply_markup=get_role_keyboard())

@router.message(F.text == "👤 Я клиент")
async def handle_client_role(message: Message):
    await message.answer(
        "Выбран профиль: Клиент. \nВ следующих обновлениях здесь появится кнопка создания заявки."
    )

from bot.keyboards.master import get_master_main_menu

@router.message(F.text == "🔨 Я мастер")
async def handle_master_role(message: Message, state: FSMContext):
    """
    Checks if user is already a MASTER, otherwise starts registration flow.
    """
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
    if user and user.role == UserRole.MASTER:
        await message.answer(
            "📍 Вы уже зарегистрированы как мастер в нашей системе!\n\n"
            "Вы можете управлять своим профилем и заказами в меню ниже:",
            reply_markup=get_master_main_menu()
        )
        return

    text = (
        "🧰 Отлично! Вы на шаг ближе к бесплатным заказам.\n\n"
        "Что вы получите:\n"
        "✅ Заказы от клиентов прямо в Telegram\n"
        "✅ Возможность приглашать коллег и получать баллы\n"
        "✅ Знак «Аккредитованный специалист» после проверки\n\n"
        "Для старта заполните короткую анкету:\n"
        "1. Ваше имя\n"
        "2. Категории услуг\n"
        "3. Краткое описание\n"
        "4. Ваш стаж\n"
        "5. Фото ваших работ\n"
        "6. Контактный номер\n\n"
        "🚀 Начнём! Напишите, как вас зовут."
    )
    
    await state.set_state(RegistrationStates.entering_name)
    await message.answer(text)
