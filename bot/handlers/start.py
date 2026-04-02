from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from bot.states import RegistrationStates

from sqlalchemy import select
from database.engine import async_session_maker
from database.models import User, UserRole

router = Router()

from bot.keyboards.registration import get_role_keyboard

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject = None):
    """Handles the /start command."""
    await state.clear()
    
    # Referral tracking
    ref_id = None
    args = command.args if command else None
    if args and args.startswith("ref_"):
        try:
            ref_id = int(args.split("_")[1])
        except (IndexError, ValueError):
            pass

    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user:
            # Create new user with referral if provided
            inviter_id = None
            if ref_id and ref_id != message.from_user.id:
                inv_stmt = select(User.id).where(User.telegram_id == ref_id)
                inviter_id = (await session.execute(inv_stmt)).scalar()
            
            user = User(
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
                referred_by=inviter_id
            )
            session.add(user)
            await session.commit()
            print(f"DEBUG: New user created {message.from_user.id}, ref: {inviter_id}")
        else:
            # If user exists but has no referrer, try to add it from the link
            if not user.referred_by and ref_id and ref_id != message.from_user.id:
                inv_stmt = select(User.id).where(User.telegram_id == ref_id)
                inviter_id = (await session.execute(inv_stmt)).scalar()
                if inviter_id:
                    user.referred_by = inviter_id
                    await session.commit()
                    print(f"DEBUG: Referrer {inviter_id} added to existing user {message.from_user.id}")

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
    
    from bot.core.config import config
    is_admin = message.from_user.id in config.ADMIN_IDS
    await message.answer(text, reply_markup=get_role_keyboard(is_admin=is_admin))

@router.message(F.text == "👤 Я клиент")
async def handle_client_role(message: Message, state: FSMContext):
    """Handles client role choosing."""
    from bot.keyboards.client import get_client_main_menu
    await state.clear()
    
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if user:
            user.role = UserRole.CLIENT
            await session.commit()
            
            from bot.core.config import config
            is_admin = message.from_user.id in config.ADMIN_IDS
            
            # If no phone, request it
            if not user.phone_number:
                kb = ReplyKeyboardMarkup(keyboard=[
                    [KeyboardButton(text="📱 Отправить номер", request_contact=True)]
                ], resize_keyboard=True)
                await message.answer(
                    "📱 Для продолжения нам нужен ваш номер телефона. "
                    "Он будет передан мастеру только после того, как вы одобрите его отклик.",
                    reply_markup=kb
                )
                return
    
    await message.answer(
        "🌆 <b>Добро пожаловать в кабинет клиента!</b>\n\n"
        "Здесь вы можете создать заявку и получить отклики от лучших мастеров города Семей.",
        parse_mode="HTML",
        reply_markup=get_client_main_menu(is_admin=is_admin)
    )

@router.message(F.contact)
async def handle_contact(message: Message):
    """Saves user phone number from contact sharing."""
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if user:
            user.phone_number = message.contact.phone_number
            await session.commit()
            
            from bot.keyboards.client import get_client_main_menu
            await message.answer(
                "✅ Номер сохранен! Теперь вы можете создавать заявки.",
                reply_markup=get_client_main_menu()
            )

from bot.keyboards.master import get_master_main_menu

@router.message(F.text.in_(["🔨 Я мастер", "🔨 Стать мастером"]))
async def handle_master_role(message: Message, state: FSMContext):
    """
    Checks if user already has a MasterProfile, otherwise starts registration flow.
    """
    from database.models import MasterProfile
    from sqlalchemy.orm import selectinload
    
    async with async_session_maker() as session:
        # Load user with master_profile to see if they EVER registered
        stmt = select(User).options(selectinload(User.master_profile)).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user and user.master_profile:
            # User IS a master, just return them to master mode
            user.role = UserRole.MASTER
            await session.commit()
            
            from bot.core.config import config
            is_admin = message.from_user.id in config.ADMIN_IDS
            
            await message.answer(
                "✨ <b>С возвращением в кабинет мастера!</b>\n\n"
                "Ваш профиль активен. Вы можете просматривать заказы и управлять своей анкетой.",
                parse_mode="HTML",
                reply_markup=get_master_main_menu(is_admin=is_admin)
            )
            return

    # If NOT a master - start registration
    text = (
        "🧰 Отлично! Вы на шаг ближе к заказам.\n\n"
        "Мы поможем вам найти клиентов. Заполните короткую анкету:\n"
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

