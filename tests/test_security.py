"""Login protection logic without a database (in-memory fallback of the store)."""
import pytest

from admin_api import security


@pytest.fixture(autouse=True)
def memory_only(monkeypatch):
    s = security.Store()
    monkeypatch.setattr(s, "_client", lambda: None)
    monkeypatch.setattr(security, "store", s)
    return s


async def _fail(user, ip, n):
    for _ in range(n):
        await security.ensure_login_allowed(user, ip)
        await security.register_login_failure(user, ip)


async def test_user_is_locked_only_from_the_attacking_ip():
    await _fail("boss", "1.1.1.1", 5)
    with pytest.raises(Exception) as e:
        await security.ensure_login_allowed("boss", "1.1.1.1")
    assert e.value.status_code == 429
    await security.ensure_login_allowed("boss", "2.2.2.2")  # the real admin from another IP is not locked out


async def test_one_ip_spraying_many_usernames_gets_locked():
    for i in range(20):
        await security.register_login_failure(f"user{i}", "9.9.9.9")
    with pytest.raises(Exception) as e:
        await security.ensure_login_allowed("brand-new-name", "9.9.9.9")
    assert e.value.status_code == 429


async def test_distributed_guessing_of_one_username_gets_locked():
    for i in range(30):
        await security.register_login_failure("victim", f"10.0.0.{i}")
    with pytest.raises(Exception):
        await security.ensure_login_allowed("victim", "10.0.1.1")


async def test_success_clears_user_ip_counter():
    await _fail("u1", "3.3.3.3", 4)
    await security.clear_login_failures("u1", "3.3.3.3")
    await _fail("u1", "3.3.3.3", 4)  # would have been locked without the reset
    await security.ensure_login_allowed("u1", "3.3.3.3")


async def test_2fa_code_single_use_and_attempt_limit():
    await security.save_2fa_code("a", "123456")
    assert await security.check_2fa_code("a", "123456") == "ok"
    assert await security.check_2fa_code("a", "123456") == "missing"
    await security.save_2fa_code("b", "123456")
    results = [await security.check_2fa_code("b", "000000") for _ in range(5)]
    assert results == ["wrong"] * 4 + ["locked"]
    assert await security.check_2fa_code("b", "123456") == "missing"  # code burnt after too many tries


async def test_effective_role_defaults_to_superadmin():
    class U: admin_role = None
    assert security.effective_role(U()) == "superadmin"
    U.admin_role = "finance"
    assert security.effective_role(U()) == "finance"
