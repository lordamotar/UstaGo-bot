from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.states import OrderCreationStates
from database.engine import async_session_maker
from database.models import User, Order, Category, District, OrderStatus, MasterProfile, UserRole
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
        # Get User internal ID by telegram_id
        user_stmt = select(User).where(User.telegram_id == callback.from_user.id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        
        if not user:
            # Fallback if somehow user isn't in DB - should not happen if they used /start
            user = User(
                telegram_id=callback.from_user.id,
                full_name=callback.from_user.full_name,
                username=callback.from_user.username
            )
            session.add(user)
            await session.flush() # Ensure we get user.id before order creation
        
        user_id = user.id
        
        new_order = Order(
            client_id=user_id,
            category_id=data['category_id'],
            district_id=data['district_id'],
            description=data['description'],
            budget=data['budget'],
            status=OrderStatus.NEW
        )
        session.add(new_order)
        await session.flush() # Get ID without commit yet
        order_id = new_order.id
        
        # Get category and district names
        cat = await session.get(Category, data['category_id'])
        dist = await session.get(District, data['district_id'])
        
        # Notify Masters
        # Filter by category AND district (or masters who work everywhere)
        from sqlalchemy import or_, not_, exists
        from database.models import master_district_areas
        
        master_stmt = select(User).join(User.master_profile).join(MasterProfile.categories).where(
            User.role == UserRole.MASTER,
            User.notifications_enabled == True,
            User.visible_for_new_orders == True,
            Category.id == data['category_id']
        )
        
        # Add District filter
        # A master should get notification if:
        # 1. They have this district in their work areas
        # 2. OR they have NO districts selected (works everywhere)
        
        has_no_districts = ~exists().where(master_district_areas.c.master_profile_id == MasterProfile.id)
        works_in_district = exists().where(
            (master_district_areas.c.master_profile_id == MasterProfile.id) & 
            (master_district_areas.c.district_id == data['district_id'])
        )
        
        master_stmt = master_stmt.where(or_(works_in_district, has_no_districts))
        
        res = await session.execute(master_stmt)
        masters_to_notify = res.scalars().all()
        print(f"DEBUG: Found {len(masters_to_notify)} masters to notify for order {order_id}")
        
        for master in masters_to_notify:
            try:
                # SKIP notifying the person who created the order if they are also a master
                if master.telegram_id == callback.from_user.id:
                    continue
                    
                master_text = (
                    f"🆕 *Новый заказ: {cat.name}!*\n\n"
                    f"📝 {data['description']}\n"
                    f"💰 Бюджет: {data['budget'] or 'Договорная'}\n"
                    f"📍 Район: {dist.name}"
                )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📥 Посмотреть и откликнуться", callback_data=f"master_view_order:{order_id}")
                ]])
                
                await callback.bot.send_message(master.telegram_id, master_text, parse_mode="Markdown", reply_markup=keyboard)
            except Exception as e:
                print(f"ERROR: Failed to notify master {master.telegram_id}: {e}")
        
        await session.commit()
        
    await callback.message.edit_text(f"🚀 *Заявка №{order_id} опубликована!*\n\nМастера получили уведомления и скоро начнут откликаться.", parse_mode="Markdown")
    await state.clear()
    from bot.core.config import config
    is_admin = callback.from_user.id in config.ADMIN_IDS
    from bot.keyboards.client import get_client_main_menu
    await callback.message.answer("Вы в главном меню.", reply_markup=get_client_main_menu(is_admin=is_admin))
    await callback.answer()
