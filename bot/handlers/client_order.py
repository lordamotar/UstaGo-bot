from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.states import OrderCreationStates
from database.engine import async_session_maker
from database.models import User, Order, Category, District, OrderStatus, MasterProfile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from bot.keyboards.client import get_inline_categories, get_inline_districts, get_order_confirmation_keyboard

router = Router()

@router.message(F.text == "➕ Создать заявку")
async def start_order_creation(message: Message, state: FSMContext):
    await state.set_state(OrderCreationStates.selecting_category)
    async with async_session_maker() as session:
        res = await session.execute(select(Category))
        categories = res.scalars().all()
    
    await message.answer(
        "🏷️ *Выберите категорию услуги:*",
        parse_mode="Markdown",
        reply_markup=get_inline_categories(categories)
    )

@router.callback_query(OrderCreationStates.selecting_category, F.data.startswith("sel_cat:"))
async def process_cat_selection(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(OrderCreationStates.entering_description)
    await callback.message.edit_text("📝 *Опишите, что нужно сделать:*", parse_mode="Markdown")
    await callback.answer()

@router.message(OrderCreationStates.entering_description)
async def process_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(OrderCreationStates.entering_budget)
    await message.answer("💰 *Укажите ваш бюджет (в тенге):*\nОтправьте число или напишите «договорная».")

@router.message(OrderCreationStates.entering_budget)
async def process_budget(message: Message, state: FSMContext):
    budget_text = message.text
    budget = None
    try:
        # Simple extraction of number
        import re
        nums = re.findall(r'\d+', budget_text)
        if nums:
            budget = int(nums[0])
    except Exception:
        pass
    
    await state.update_data(budget=budget, budget_text=budget_text)
    await state.set_state(OrderCreationStates.selecting_district)
    
    async with async_session_maker() as session:
        res = await session.execute(select(District))
        districts = res.scalars().all()
    
    await message.answer("📍 *В каком районе нужно выполнить работу?*", parse_mode="Markdown", reply_markup=get_inline_districts(districts))

@router.callback_query(OrderCreationStates.selecting_district, F.data.startswith("sel_dist:"))
async def process_dist_selection(callback: CallbackQuery, state: FSMContext):
    dist_id = int(callback.data.split(":")[1])
    await state.update_data(district_id=dist_id)
    await state.set_state(OrderCreationStates.confirming)
    
    data = await state.get_data()
    async with async_session_maker() as session:
        cat = await session.get(Category, data['category_id'])
        dist = await session.get(District, dist_id)
        
    text = (
        "📊 *Ваша заявка:* \n\n"
        f"🏷️ Категория: {cat.name}\n"
        f"📝 Описание: {data['description']}\n"
        f"💰 Бюджет: {data['budget_text']}\n"
        f"📍 Район: {dist.name}\n\n"
        "Опубликовать?"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_order_confirmation_keyboard())
    await callback.answer()

@router.callback_query(OrderCreationStates.confirming, F.data == "order_confirm")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    async with async_session_maker() as session:
        # Get User ID
        res = await session.execute(select(User.id).where(User.telegram_id == callback.from_user.id))
        user_id = res.scalar()
        
        new_order = Order(
            client_id=user_id,
            category_id=data['category_id'],
            district_id=data['district_id'],
            description=data['description'],
            budget=data['budget'],
            status=OrderStatus.NEW
        )
        session.add(new_order)
        await session.commit()
        order_id = new_order.id
        
    await callback.message.edit_text(f"🚀 *Заявка №{order_id} опубликована!*\n\nМастера получили уведомления и скоро начнут откликаться.", parse_mode="Markdown")
    await state.clear()
    await callback.answer()
