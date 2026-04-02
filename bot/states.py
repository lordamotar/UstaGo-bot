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

class OrderCreationStates(StatesGroup):
    selecting_category = State()
    entering_description = State()
    entering_budget = State()
    selecting_district = State()
    confirming = State()
