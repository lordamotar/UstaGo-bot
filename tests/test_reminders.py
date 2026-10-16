"""Re-notifying masters about orders without bids (bot/services/reminders.py). In-memory SQLite."""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bot.core.config import config
from bot.services import reminders as R
from database.base import Base
from database.models import (
    Bid, Category, MasterProfile, MasterStatus, Order, OrderStatus, OrderView, User, UserRole,
)

NOW = datetime(2026, 10, 16, 5, 0)  # 05:00 UTC = 10:00 local (UTC+5): inside working hours 9-21
NIGHT = datetime(2026, 10, 16, 18, 0)  # 23:00 local: outside working hours


@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    monkeypatch.setattr(config, "TZ_OFFSET_HOURS", 5)
    monkeypatch.setattr(config, "WORK_HOURS_START", 9)
    monkeypatch.setattr(config, "WORK_HOURS_END", 21)
    monkeypatch.setattr(config, "REMINDER_AFTER_MINUTES", 15)
    monkeypatch.setattr(config, "ORDER_TTL_HOURS", 72)


@pytest_asyncio.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class FakeBot:
    def __init__(self, fail_for=()):
        self.sent = []
        self.fail_for = set(fail_for)

    async def send_message(self, chat_id, text, **kw):
        if chat_id in self.fail_for:
            raise RuntimeError("blocked")
        self.sent.append((chat_id, text, kw))

    def to(self, chat_id):
        return [m for m in self.sent if m[0] == chat_id]


_tg = iter(range(5000, 10**6))


async def mk_user(s, role=UserRole.CLIENT, **kw):
    u = User(telegram_id=next(_tg), full_name="U", role=role, **kw)
    s.add(u)
    await s.flush()
    return u


async def mk_master(s, category, **kw):
    u = await mk_user(s, UserRole.MASTER, **kw)
    p = MasterProfile(user_id=u.id, status=MasterStatus.APPROVED)
    p.categories.append(category)
    s.add(p)
    await s.flush()
    return u, p


async def scenario(maker, age_minutes=20, status=OrderStatus.NEW):
    """client + order + masters: viewed, fresh, bidder, dnd, other_category."""
    async with maker() as s:
        cat = Category(name="Электрик")
        other = Category(name="Сантехник")
        s.add_all([cat, other])
        await s.flush()
        client = await mk_user(s)
        order = Order(client_id=client.id, category_id=cat.id, description="розетка", status=status,
                      created_at=NOW - timedelta(minutes=age_minutes))
        s.add(order)
        viewed, _ = await mk_master(s, cat)
        fresh, _ = await mk_master(s, cat)
        bidder, bidder_profile = await mk_master(s, cat)
        dnd, _ = await mk_master(s, cat, dnd_start="08:00", dnd_end="12:00")  # 10:00 local is inside
        stranger, _ = await mk_master(s, other)
        await s.flush()
        s.add(OrderView(order_id=order.id, user_id=viewed.id))
        s.add(Bid(order_id=order.id, master_id=bidder_profile.id, suggested_price=1000))
        await s.commit()
        return dict(order=order.id, client=client, viewed=viewed, fresh=fresh, bidder=bidder, dnd=dnd, stranger=stranger)


# ------------------------------------------------------------------ time helpers

@pytest.mark.parametrize("utc_hour,expected", [(3, False), (4, True), (5, True), (15, True), (16, False), (23, False)])
def test_working_hours(utc_hour, expected):
    assert R.in_working_hours(datetime(2026, 10, 16, utc_hour, 30)) is expected


def test_working_hours_over_midnight(monkeypatch):
    monkeypatch.setattr(config, "WORK_HOURS_START", 20)
    monkeypatch.setattr(config, "WORK_HOURS_END", 6)
    assert R.in_working_hours(datetime(2026, 10, 16, 18, 0))      # 23:00 local
    assert not R.in_working_hours(datetime(2026, 10, 16, 5, 0))   # 10:00 local


@pytest.mark.parametrize("now,start,end,expected", [
    ("10:00", "08:00", "12:00", True),
    ("13:00", "08:00", "12:00", False),
    ("23:30", "22:00", "07:00", True),
    ("03:00", "22:00", "07:00", True),
    ("12:00", "22:00", "07:00", False),
    ("10:00", None, None, False),
    ("10:00", "09:00", "09:00", False),
])
def test_dnd(now, start, end, expected):
    assert R.is_in_dnd(now, start, end) is expected


# ------------------------------------------------------------------ who gets asked

@pytest.mark.asyncio
async def test_due_for_prompt_rules(maker):
    sc = await scenario(maker)
    async with maker() as s:
        assert [o.id for o in await R.due_for_prompt(s, NOW)] == []  # the order has a bid
    async with maker() as s:
        await s.execute(Bid.__table__.delete())
        await s.commit()
    async with maker() as s:
        assert [o.id for o in await R.due_for_prompt(s, NOW)] == [sc["order"]]
        assert await R.due_for_prompt(s, NOW - timedelta(minutes=10)) == []  # too fresh
        assert await R.due_for_prompt(s, NOW + timedelta(hours=100)) == []   # would be auto-closed anyway
        order = await s.get(Order, sc["order"])
        order.reminder_prompted_at = NOW
        await s.commit()
        assert await R.due_for_prompt(s, NOW) == []  # asked once


@pytest.mark.asyncio
async def test_feature_can_be_disabled(maker, monkeypatch):
    await scenario(maker)
    monkeypatch.setattr(config, "REMINDER_AFTER_MINUTES", 0)
    bot = FakeBot()
    res = await R.run_reminder_cycle(bot, maker, NOW)
    assert res.prompted == 0 and bot.sent == []


@pytest.mark.asyncio
async def test_cycle_asks_client_once_in_working_hours(maker):
    sc = await scenario(maker)
    async with maker() as s:
        await s.execute(Bid.__table__.delete())
        await s.commit()
    bot = FakeBot()
    assert (await R.run_reminder_cycle(bot, maker, NIGHT)).prompted == 0  # night: nothing
    assert bot.sent == []
    assert (await R.run_reminder_cycle(bot, maker, NOW)).prompted == 1
    chat_id, text, kw = bot.sent[0]
    assert chat_id == sc["client"].telegram_id and f"№{sc['order']}" in text
    data = [b.callback_data for row in kw["reply_markup"].inline_keyboard for b in row]
    assert data == [f"order_remind:{sc['order']}:all", f"order_remind:{sc['order']}:unopened", f"order_remind:{sc['order']}:skip"]
    assert (await R.run_reminder_cycle(bot, maker, NOW + timedelta(minutes=5))).prompted == 0  # never twice
    assert len(bot.sent) == 1


# ------------------------------------------------------------------ client's choice

@pytest.mark.asyncio
async def test_set_client_choice(maker):
    sc = await scenario(maker)
    tg = sc["client"].telegram_id
    async with maker() as s:
        assert await R.set_client_choice(s, sc["order"], tg + 777, R.MODE_ALL) == "not_found"  # not the owner
        assert await R.set_client_choice(s, sc["order"], tg, "nonsense") == "not_found"
        assert await R.set_client_choice(s, sc["order"], tg, R.MODE_ALL) == "has_bids"          # a bid appeared meanwhile
        await s.execute(Bid.__table__.delete())
        assert await R.set_client_choice(s, sc["order"], tg, R.MODE_UNOPENED) == "ok"
        assert await R.set_client_choice(s, sc["order"], tg, R.MODE_ALL) == "already"
        assert (await s.get(Order, sc["order"])).remind_mode == R.MODE_UNOPENED


@pytest.mark.asyncio
async def test_set_client_choice_closed_order(maker):
    sc = await scenario(maker, status=OrderStatus.CANCELLED)
    async with maker() as s:
        assert await R.set_client_choice(s, sc["order"], sc["client"].telegram_id, R.MODE_ALL) == "closed"


# ------------------------------------------------------------------ who gets reminded

@pytest.mark.asyncio
async def test_remind_all_skips_bidder_dnd_and_other_categories(maker):
    sc = await scenario(maker)
    async with maker() as s:
        order = await s.get(Order, sc["order"])
        order.remind_mode = R.MODE_ALL
        order.reminder_prompted_at = NOW
        await s.commit()
    bot = FakeBot()
    res = await R.run_reminder_cycle(bot, maker, NOW)
    got = {m[0] for m in bot.sent}
    assert sc["viewed"].telegram_id in got and sc["fresh"].telegram_id in got
    assert sc["bidder"].telegram_id not in got        # already bid
    assert sc["dnd"].telegram_id not in got           # do not disturb
    assert sc["stranger"].telegram_id not in got      # other category
    assert res.reminded_masters == 2 and res.reminded_orders == 1
    assert bot.to(sc["client"].telegram_id)           # client gets a confirmation
    assert "master_view_order:%d" % sc["order"] == bot.to(sc["fresh"].telegram_id)[0][2]["reply_markup"].inline_keyboard[0][0].callback_data


@pytest.mark.asyncio
async def test_remind_unopened_skips_those_who_viewed(maker):
    sc = await scenario(maker)
    async with maker() as s:
        order = await s.get(Order, sc["order"])
        order.remind_mode = R.MODE_UNOPENED
        order.reminder_prompted_at = NOW
        await s.commit()
    bot = FakeBot()
    await R.run_reminder_cycle(bot, maker, NOW)
    masters = {m[0] for m in bot.sent} - {sc["client"].telegram_id}
    assert masters == {sc["fresh"].telegram_id}


@pytest.mark.asyncio
async def test_reminder_waits_for_working_hours_and_is_sent_once(maker):
    sc = await scenario(maker)
    async with maker() as s:
        order = await s.get(Order, sc["order"])
        order.remind_mode = R.MODE_ALL
        order.reminder_prompted_at = NOW
        await s.commit()
    bot = FakeBot()
    await R.run_reminder_cycle(bot, maker, NIGHT)
    assert bot.sent == []                              # night: held back
    await R.run_reminder_cycle(bot, maker, NOW)
    n = len(bot.sent)
    assert n >= 2
    await R.run_reminder_cycle(bot, maker, NOW + timedelta(minutes=1))
    assert len(bot.sent) == n                          # only once
    async with maker() as s:
        assert (await s.get(Order, sc["order"])).reminder_sent_at is not None


@pytest.mark.asyncio
async def test_skip_sends_nothing(maker):
    sc = await scenario(maker)
    async with maker() as s:
        order = await s.get(Order, sc["order"])
        order.remind_mode = R.MODE_SKIP
        order.reminder_prompted_at = NOW
        await s.commit()
    bot = FakeBot()
    await R.run_reminder_cycle(bot, maker, NOW)
    assert bot.sent == []


@pytest.mark.asyncio
async def test_blocked_master_does_not_break_the_cycle(maker):
    sc = await scenario(maker)
    async with maker() as s:
        order = await s.get(Order, sc["order"])
        order.remind_mode = R.MODE_ALL
        order.reminder_prompted_at = NOW
        await s.commit()
    bot = FakeBot(fail_for={sc["viewed"].telegram_id})
    res = await R.run_reminder_cycle(bot, maker, NOW)
    assert res.reminded_masters == 1
    assert bot.to(sc["fresh"].telegram_id)


@pytest.mark.asyncio
async def test_record_view_is_idempotent(maker):
    sc = await scenario(maker)
    async with maker() as s:
        await R.record_view(s, sc["order"], sc["fresh"].id)
        await s.commit()
        await R.record_view(s, sc["order"], sc["fresh"].id)
        await R.record_view(s, sc["order"], sc["viewed"].id)  # already there
        await s.commit()
        rows = (await s.execute(select(OrderView).where(OrderView.order_id == sc["order"]))).scalars().all()
        assert sorted(r.user_id for r in rows) == sorted([sc["fresh"].id, sc["viewed"].id])
