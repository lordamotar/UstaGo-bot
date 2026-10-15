"""Admin API tests against a REAL PostgreSQL (skipped unless TEST_DATABASE_URL is set).

    TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/ustago_test python -m pytest tests/test_admin_api.py

The database must be migrated (`alembic upgrade head`) and must NOT be production: the tests change
system settings. Test users live in a reserved telegram_id range and are removed afterwards.
"""
import os
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="needs a real PostgreSQL")

TG_BASE = 9_000_000_000
_counter = iter(range(TG_BASE, TG_BASE + 10_000))


@pytest_asyncio.fixture
async def env(monkeypatch):
    from admin_api import main as api
    from database.engine import async_session_maker, engine
    from database.models import UserRole, User

    notify = AsyncMock()
    monkeypatch.setattr(api, "notify_user", notify)

    async with async_session_maker() as s:
        admin = User(telegram_id=next(_counter), full_name="Test Admin", username="test_admin", role=UserRole.ADMIN)
        s.add(admin)
        await s.commit()
        admin_id = admin.id

    async def fake_admin():
        async with async_session_maker() as s:
            return await s.get(User, admin_id)

    api.app.dependency_overrides[api.get_current_user] = fake_admin
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test")
    yield type("Env", (), {"client": client, "notify": notify, "admin_id": admin_id, "maker": async_session_maker})

    api.app.dependency_overrides.clear()
    await client.aclose()
    from database.models import AdminLog, MasterProfile, Order, TopUpRequest, Transaction
    async with async_session_maker() as s:
        ids = (await s.execute(select(User.id).where(User.telegram_id >= TG_BASE, User.telegram_id < TG_BASE + 10_000))).scalars().all()
        for model, col in ((AdminLog, AdminLog.admin_id), (Transaction, Transaction.user_id),
                           (TopUpRequest, TopUpRequest.user_id), (MasterProfile, MasterProfile.user_id),
                           (Order, Order.client_id)):
            await s.execute(delete(model).where(col.in_(ids)))
        await s.execute(delete(User).where(User.id.in_(ids)))
        await s.commit()
    await engine.dispose()


async def _user(env, **kw):
    from database.models import User
    async with env.maker() as s:
        u = User(telegram_id=next(_counter), full_name=kw.pop("name", "Test User"), **kw)
        s.add(u)
        await s.commit()
        return u.id, u.telegram_id


async def _points(env, user_id):
    from database.models import User
    async with env.maker() as s:
        return (await s.get(User, user_id)).points


async def _topup(env, user_id, amount=1000):
    from database.models import TopUpRequest
    async with env.maker() as s:
        req = TopUpRequest(user_id=user_id, amount=amount, method="BANK", status="PENDING")
        s.add(req)
        await s.commit()
        return req.id


async def test_approving_topup_credits_balance_once_and_is_audited(env):
    from database.models import AdminLog, Transaction, TransactionType
    uid, tg = await _user(env)
    req_id = await _topup(env, uid, 1000)

    r = await env.client.patch(f"/api/v1/topups/{req_id}", json={"status": "APPROVED"})
    assert r.status_code == 200, r.text
    assert await _points(env, uid) == 1000
    env.notify.assert_awaited_once()
    assert env.notify.await_args.args[0] == tg

    again = await env.client.patch(f"/api/v1/topups/{req_id}", json={"status": "APPROVED"})
    assert again.status_code == 404
    assert await _points(env, uid) == 1000

    async with env.maker() as s:
        tx = (await s.execute(select(Transaction).where(Transaction.user_id == uid))).scalar_one()
        assert tx.type == TransactionType.TOPUP and tx.amount == 1000
        log = (await s.execute(select(AdminLog).where(AdminLog.admin_id == env.admin_id))).scalars().first()
        assert log and log.action == "TOPUP_APPROVED"


async def test_rejecting_topup_does_not_credit(env):
    uid, _ = await _user(env)
    req_id = await _topup(env, uid, 500)
    r = await env.client.patch(f"/api/v1/topups/{req_id}", json={"status": "REJECTED"})
    assert r.status_code == 200, r.text
    assert await _points(env, uid) == 0


async def test_topup_rejects_unknown_status(env):
    uid, _ = await _user(env)
    req_id = await _topup(env, uid)
    r = await env.client.patch(f"/api/v1/topups/{req_id}", json={"status": "WHATEVER"})
    assert r.status_code == 400
    assert await _points(env, uid) == 0


async def test_settings_can_be_updated(env):
    r = await env.client.patch("/api/v1/settings", json={"free_orders_enabled": True})
    assert r.status_code == 200, r.text
    assert (await env.client.get("/api/v1/settings")).json()["free_orders_enabled"] is True
    await env.client.patch("/api/v1/settings", json={"free_orders_enabled": False})


async def _master(env, status, **kw):
    from database.models import MasterProfile, UserRole
    uid, tg = await _user(env, role=UserRole.MASTER, **kw)
    async with env.maker() as s:
        p = MasterProfile(user_id=uid, status=status)
        s.add(p)
        await s.commit()
        return uid, tg, p.id


async def test_approving_master_via_api_pays_welcome_bonus_once(env):
    from database.models import MasterStatus
    uid, tg, master_id = await _master(env, MasterStatus.PENDING)

    r = await env.client.patch(f"/api/v1/masters/{master_id}", json={"status": "APPROVED"})
    assert r.status_code == 200, r.text
    assert await _points(env, uid) == 2000

    await env.client.patch(f"/api/v1/masters/{master_id}", json={"status": "APPROVED"})
    assert await _points(env, uid) == 2000


async def test_adjust_points_never_goes_negative(env):
    from database.models import MasterStatus
    uid, _, master_id = await _master(env, MasterStatus.APPROVED, points=100)

    ok = await env.client.post(f"/api/v1/masters/{master_id}/adjust-points", json={"amount": -60, "description": "fine"})
    assert ok.status_code == 200 and ok.json()["new_balance"] == 40

    too_much = await env.client.post(f"/api/v1/masters/{master_id}/adjust-points", json={"amount": -60, "description": "fine"})
    assert too_much.status_code == 400
    assert await _points(env, uid) == 40


async def test_bulk_adjust_skips_masters_who_would_go_negative(env):
    from database.models import MasterStatus
    rich, _, rich_m = await _master(env, MasterStatus.APPROVED, points=100)
    poor, _, poor_m = await _master(env, MasterStatus.APPROVED, points=10)

    r = await env.client.post("/api/v1/finance/bulk-adjust-points",
                              json={"master_ids": [rich_m, poor_m], "amount": -50, "description": "penalty"})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "success", "count": 1, "skipped": 1}
    assert await _points(env, rich) == 50
    assert await _points(env, poor) == 10
