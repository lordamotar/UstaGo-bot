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
    pending_approval = State()         # Sent to admins for approval
