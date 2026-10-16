"""Bot role switching must never demote an ADMIN (that locks them out of the panel)."""
from types import SimpleNamespace

from bot.utils.roles import set_mode_role
from database.models import UserRole


def _u(role):
    return SimpleNamespace(role=role)


def test_admin_is_never_demoted():
    for target in (UserRole.CLIENT, UserRole.MASTER):
        u = _u(UserRole.ADMIN)
        assert set_mode_role(u, target) is False
        assert u.role == UserRole.ADMIN


def test_client_and_master_switch_normally():
    u = _u(UserRole.CLIENT)
    assert set_mode_role(u, UserRole.MASTER) is True
    assert u.role == UserRole.MASTER
    assert set_mode_role(u, UserRole.CLIENT) is True
    assert u.role == UserRole.CLIENT


def test_same_role_is_noop():
    u = _u(UserRole.MASTER)
    assert set_mode_role(u, UserRole.MASTER) is False
