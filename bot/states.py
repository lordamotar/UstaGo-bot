from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    """
    Finite State Machine for Master Registration path.
    """
    choosing_role = State()            # /start -> Client or Master
    entering_name = State()            # 1. Ваше имя
    selecting_categories = State()     # 2. Категории услуг
    entering_description = State()     # 3. Краткое описание
    entering_experience = State()      # 4. Стаж
    uploading_photos = State()         # 5. Фото работ
    sharing_phone = State()            # 6. Поделиться номером
class EditProfileStates(StatesGroup):
    choosing_field = State()
    editing_name = State()
    selecting_categories = State()
    editing_description = State()

class ManagePhotoStates(StatesGroup):
    main = State()
    adding_photos = State()
    deleting_photos = State()

class SettingsStates(StatesGroup):
    choosing_districts = State()
    entering_dnd_start = State()
    entering_dnd_end = State()

class OrderCreationStates(StatesGroup):
    requiring_phone = State()
    selecting_category = State()
    entering_description = State()
    entering_budget = State()
    selecting_district = State()
    uploading_photos = State()
    confirming = State()

class BidStates(StatesGroup):
    entering_price = State()
    entering_message = State()

class ReviewStates(StatesGroup):
    rating = State()
    comment = State()

class AdminStates(StatesGroup):
    adding_category = State()
    adding_district = State()
