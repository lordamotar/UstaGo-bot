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
    from database.models import AdminLog, Bid, MasterProfile, Order, TopUpRequest, Transaction
    async with async_session_maker() as s:
        ids = (await s.execute(select(User.id).where(User.telegram_id >= TG_BASE, User.telegram_id < TG_BASE + 10_000))).scalars().all()
        order_ids = (await s.execute(select(Order.id).where(Order.client_id.in_(ids)))).scalars().all()
        await s.execute(delete(Bid).where(Bid.order_id.in_(order_ids)))
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


# ---------------- admin panel: search / card / export / funnel / cancel ----------------

async def _order(env, client_id, status=None, description="Течёт кран", budget=5000, category="Сантехник"):
    from database.models import Category, Order, OrderStatus
    async with env.maker() as s:
        cat = (await s.execute(select(Category).where(Category.name == category))).scalar_one_or_none()
        if not cat:
            cat = Category(name=category)
            s.add(cat)
            await s.flush()
        o = Order(client_id=client_id, category_id=cat.id, description=description, budget=budget,
                  status=status or OrderStatus.NEW)
        s.add(o)
        await s.commit()
        return o.id


async def _bid(env, order_id, master_id, status="pending", price=3000):
    from database.models import Bid
    async with env.maker() as s:
        b = Bid(order_id=order_id, master_id=master_id, suggested_price=price, status=status)
        s.add(b)
        await s.commit()
        return b.id


async def test_users_search_by_name_username_phone_and_id(env):
    uid, tg = await _user(env, name="Зульфия Уникальная", username="zulf_unique", phone_number="+77001112233")
    for q in ("Уникальн", "@zulf_unique", "zulf_uni", "7001112233", str(tg), str(uid)):
        r = await env.client.get("/api/v1/users", params={"q": q})
        assert r.status_code == 200, r.text
        assert uid in [u["id"] for u in r.json()["items"]], q
    miss = await env.client.get("/api/v1/users", params={"q": "нет-такого-zzz"})
    assert miss.json()["total"] == 0


async def test_users_filter_by_master_status(env):
    from database.models import MasterStatus
    pending_uid, _, _ = await _master(env, MasterStatus.PENDING, name="Ожидающий Мастер")
    ok_uid, _, _ = await _master(env, MasterStatus.APPROVED, name="Одобренный Мастер")
    r = await env.client.get("/api/v1/users", params={"master_status": "PENDING", "q": "Мастер"})
    ids = [u["id"] for u in r.json()["items"]]
    assert pending_uid in ids and ok_uid not in ids


async def test_user_card_has_history(env):
    from database.models import MasterStatus
    uid, _, master_id = await _master(env, MasterStatus.APPROVED)
    client_id, _ = await _user(env)
    oid = await _order(env, client_id)
    await _bid(env, oid, master_id, "accepted")
    await env.client.post(f"/api/v1/masters/{master_id}/adjust-points", json={"amount": 100, "description": "тест"})

    card = (await env.client.get(f"/api/v1/users/{uid}")).json()
    assert card["points"] == 100
    assert card["transactions"] and card["transactions"][0]["amount"] == 100
    assert card["bids"][0]["order_id"] == oid
    assert card["master_data"]["processed_orders"] == 1
    assert (await env.client.get(f"/api/v1/users/{client_id}")).json()["orders"][0]["id"] == oid
    assert (await env.client.get("/api/v1/users/999999999")).status_code == 404


async def test_orders_search_and_filters(env):
    client_id, _ = await _user(env, name="Клиент Поисковый")
    oid = await _order(env, client_id, description="Уникальное описание qwerty123", category="Электрик-тест")
    for q in ("qwerty123", "Электрик-тест", "Поисковый", f"#{oid}", str(oid)):
        r = await env.client.get("/api/v1/orders", params={"q": q})
        assert oid in [o["id"] for o in r.json()["items"]], q
    r = await env.client.get("/api/v1/orders", params={"q": "qwerty123", "status": "CANCELLED"})
    assert r.json()["total"] == 0
    item = (await env.client.get("/api/v1/orders", params={"q": "qwerty123"})).json()["items"][0]
    assert item["client_name"] == "Клиент Поисковый" and item["bids_count"] == 0


async def test_admin_cancel_order_refunds_masters_and_notifies(env):
    from database.models import MasterStatus, OrderStatus, Order, Transaction, TransactionType
    from bot.services import billing
    client_id, client_tg = await _user(env)
    m_uid, m_tg, m_id = await _master(env, MasterStatus.APPROVED)
    oid = await _order(env, client_id)
    async with env.maker() as s:
        await billing.credit(s, m_uid, 100, TransactionType.TOPUP, "init")
        await billing.charge(s, m_uid, billing.BID_COST, TransactionType.CONTACT_FEE, "fee", order_id=oid)
        await s.commit()
    await _bid(env, oid, m_id)
    assert await _points(env, m_uid) == 50

    r = await env.client.post(f"/api/v1/orders/{oid}/cancel")
    assert r.status_code == 200, r.text
    assert await _points(env, m_uid) == 100
    async with env.maker() as s:
        assert (await s.get(Order, oid)).status == OrderStatus.CANCELLED
    notified = {c.args[0] for c in env.notify.await_args_list}
    assert {client_tg, m_tg} <= notified
    assert (await env.client.post(f"/api/v1/orders/{oid}/cancel")).status_code == 400


async def test_funnel_counts(env):
    from database.models import MasterStatus, OrderStatus
    client_id, _ = await _user(env)
    _, _, m_id = await _master(env, MasterStatus.APPROVED)
    before = (await env.client.get("/api/v1/stats/funnel", params={"days": 1})).json()
    o1 = await _order(env, client_id)
    o2 = await _order(env, client_id, status=OrderStatus.COMPLETED)
    await _order(env, client_id, status=OrderStatus.CANCELLED)
    await _bid(env, o1, m_id)
    await _bid(env, o2, m_id, "accepted")
    after = (await env.client.get("/api/v1/stats/funnel", params={"days": 1})).json()
    assert after["created"] - before["created"] == 3
    assert after["with_bids"] - before["with_bids"] == 2
    assert after["completed"] - before["completed"] == 1
    assert after["cancelled"] - before["cancelled"] == 1
    assert after["median_first_bid_minutes"] is not None


async def test_csv_export_escapes_formulas_and_respects_filters(env):
    uid, _ = await _user(env, name="=HYPERLINK(\"http://evil\")", username="csv_user_x")
    r = await env.client.get("/api/v1/users/export", params={"q": "csv_user_x"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.content.decode("utf-8-sig")
    assert "'=HYPERLINK" in body and ";=HYPERLINK" not in body
    assert body.count("\n") == 2  # header + one row

    client_id, _ = await _user(env)
    oid = await _order(env, client_id, description="export-marker-777")
    o = await env.client.get("/api/v1/orders/export", params={"q": "export-marker-777"})
    assert f"{oid};" in o.content.decode("utf-8-sig")


# ---------------- roles / login protection ----------------

async def _as_role(env, role):
    """Swap the authenticated admin for one with the given admin_role."""
    from admin_api import main as api
    from database.models import User, UserRole
    uid, _ = await _user(env, role=UserRole.ADMIN, admin_role=role)

    async def fake():
        async with env.maker() as s:
            return await s.get(User, uid)
    api.app.dependency_overrides[api.get_current_user] = fake
    return uid


async def test_moderator_can_moderate_but_not_touch_money_or_settings(env):
    from database.models import MasterStatus
    await _as_role(env, "moderator")
    _, _, master_id = await _master(env, MasterStatus.PENDING)

    ok = await env.client.patch(f"/api/v1/masters/{master_id}", json={"status": "APPROVED"})
    assert ok.status_code == 200, ok.text
    assert (await env.client.post(f"/api/v1/masters/{master_id}/adjust-points",
                                  json={"amount": 10, "description": "x"})).status_code == 403
    assert (await env.client.patch("/api/v1/settings", json={"free_orders_enabled": True})).status_code == 403
    assert (await env.client.get("/api/v1/logs")).status_code == 403
    assert (await env.client.get("/api/v1/backups")).status_code == 403
    assert (await env.client.get("/api/v1/users")).status_code == 200  # read access is for every admin


async def test_finance_can_move_points_but_not_moderate(env):
    from database.models import MasterStatus
    await _as_role(env, "finance")
    uid, _, master_id = await _master(env, MasterStatus.APPROVED)

    ok = await env.client.post(f"/api/v1/masters/{master_id}/adjust-points", json={"amount": 10, "description": "x"})
    assert ok.status_code == 200, ok.text
    assert await _points(env, uid) == 10
    assert (await env.client.patch(f"/api/v1/masters/{master_id}", json={"status": "REJECTED"})).status_code == 403
    client_id, _ = await _user(env)
    oid = await _order(env, client_id)
    assert (await env.client.post(f"/api/v1/orders/{oid}/cancel")).status_code == 403


async def test_legacy_admin_without_role_is_superadmin(env):
    # the default fixture admin has admin_role = NULL
    assert (await env.client.get("/api/v1/auth/me")).json()["admin_role"] == "superadmin"
    assert (await env.client.get("/api/v1/logs")).status_code == 200


async def test_superadmin_manages_roles_with_guards(env):
    from database.models import UserRole
    target, _ = await _user(env, role=UserRole.ADMIN)
    r = await env.client.patch(f"/api/v1/admins/{target}", json={"admin_role": "finance"})
    assert r.status_code == 200, r.text
    assert any(a["id"] == target and a["admin_role"] == "finance" for a in (await env.client.get("/api/v1/admins")).json())
    assert (await env.client.patch(f"/api/v1/admins/{target}", json={"admin_role": "root"})).status_code == 400
    assert (await env.client.patch(f"/api/v1/admins/{env.admin_id}", json={"admin_role": "finance"})).status_code == 400
    plain, _ = await _user(env)
    assert (await env.client.patch(f"/api/v1/admins/{plain}", json={"admin_role": "finance"})).status_code == 404


async def _admin_with_password(env, password="correct-horse"):
    from admin_api.main import get_password_hash
    from database.models import UserRole
    uid, tg = await _user(env, role=UserRole.ADMIN, username=f"adm_{next(_counter)}", hashed_password=get_password_hash(password))
    from database.models import User
    async with env.maker() as s:
        return (await s.get(User, uid)).username, tg


async def test_full_login_with_2fa_and_lockout(env, monkeypatch):
    from admin_api import main as api
    api.app.dependency_overrides.clear()
    sent = []
    async def fake_send(chat_id, text, **kw): sent.append(text)
    monkeypatch.setattr(api.bot_instance, "send_message", fake_send)
    username, _ = await _admin_with_password(env)

    # wrong 2FA code does not give a token, right one does
    r = await env.client.post("/api/v1/auth/login", data={"username": username, "password": "correct-horse"})
    assert r.status_code == 200 and r.json()["requires_2fa"], r.text
    import re
    code = re.search(r"<code>(\d{6})</code>", sent[-1]).group(1)
    wrong = "000000" if code != "000000" else "111111"
    assert (await env.client.post("/api/v1/auth/verify-2fa", json={"username": username, "code": wrong})).status_code == 400
    ok = await env.client.post("/api/v1/auth/verify-2fa", json={"username": username, "code": code})
    assert ok.status_code == 200 and ok.json()["access_token"]
    # the code is single-use
    assert (await env.client.post("/api/v1/auth/verify-2fa", json={"username": username, "code": code})).status_code == 400

    # five bad passwords lock this username from this IP, even the right password is refused afterwards
    for _ in range(5):
        bad = await env.client.post("/api/v1/auth/login", data={"username": username, "password": "nope"})
        assert bad.status_code == 401
    locked = await env.client.post("/api/v1/auth/login", data={"username": username, "password": "correct-horse"})
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) > 0
