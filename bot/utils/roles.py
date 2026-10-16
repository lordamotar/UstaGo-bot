"""Role helpers for the bot.

The bot lets people switch between "client" and "master" mode by writing
``users.role``. Admin panel access is also decided by ``users.role == ADMIN``,
so a naive overwrite silently locks an admin out of the panel (403 on login).
"""
from database.models import User, UserRole


def set_mode_role(user: User, role: UserRole) -> bool:
    """Switch a user's bot mode without ever demoting an ADMIN.

    Returns True if the role was changed, False if it was left untouched
    (user is an admin or already has this role).
    """
    if user.role == UserRole.ADMIN or user.role == role:
        return False
    user.role = role
    return True
