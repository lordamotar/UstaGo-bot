from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext

router = Router()

def get_role_keyboard() -> ReplyKeyboardMarkup:
    """Returns the keyboard for role selection."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Я клиент"),
                KeyboardButton(text="🔨 Я мастер")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

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

@router.message(F.text == "🔨 Я мастер")
async def handle_master_role(message: Message):
    text = (
        "🧰 Отлично! Вы на шаг ближе к бесплатным заказам.\n\n"
        "Что вы получите:\n"
        "✅ Заказы от клиентов прямо в Telegram\n"
        "✅ Возможность приглашать коллег и получать баллы\n"
        "✅ Знак «Аккредитованный специалист» после проверки\n\n"
        "Для старта заполните короткую анкету:\n"
        "1. Ваше имя\n"
        "2. Категории услуг\n"
        "3. Фото работ\n"
        "4. Краткое описание\n\n"
        "🚀 Начнём?"
    )
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Регистрация Мастера")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(text, reply_markup=keyboard)

@router.message()
async def catch_all(message: Message):
    """Fallback handler to see all incoming messages."""
    await message.answer(f"Я получил твое сообщение: {message.text}. Но пока не знаю, что с ним делать.")
