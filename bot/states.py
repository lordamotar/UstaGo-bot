from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    """
    Finite State Machine for Master Registration path.
    """
    choosing_role = State()            # /start -> Client or Master
    entering_name = State()            # Input display name
    selecting_categories = State()     # Multi-select inline keyboard
    uploading_photos = State()         # Send 1-3 photos
    entering_description = State()     # Send bio/experience
    pending_approval = State()         # Sent to admins for approval
