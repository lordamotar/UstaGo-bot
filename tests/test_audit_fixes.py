"""Regression tests for the security audit findings:
 1. only the owner of an order may view it / accept / reject its bids (bot/handlers/client_cabinet.py)
 2. support-ticket text is HTML-escaped before it is sent to admins
 3. backups can only be read/deleted directly inside BACKUP_DIR
Handler tests need a real PostgreSQL (TEST_DATABASE_URL), like test_start_tracking.py.
"""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

needs_pg = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="needs a real PostgreSQL")

TG_BASE = 9_300_000_000


# ------------------------------------------------------------------ backups (no DB needed)

def test_backup_path_cannot_escape_the_backup_dir(tmp_path, monkeypatch):
    from admin_api import backups
    base = tmp_path / "backups"
    base.mkdir()
    (base / "ok.json").write_text("{}")
    outside = tmp_path / "secret.txt"
    outside.write_text("do not delete")
    evil_dir = tmp_path / "backups_evil"
    evil_dir.mkdir()
    (evil_dir / "x.json").write_text("{}")
    (base / "sub").mkdir()
    (base / "sub" / "n.json").write_text("{}")
    monkeypatch.setattr(backups, "BACKUP_DIR", str(base))

    assert backups.get_backup_path("ok.json") == str(base / "ok.json")
    for bad in (str(outside), "../secret.txt", "..", ".", "", "sub/n.json", "../backups_evil/x.json",
                str(evil_dir / "x.json"), "missing.json", "sub"):
        assert backups.get_backup_path(bad) is None, bad
        assert backups.delete_backup(bad) is False, bad
    assert outside.exists() and (evil_dir / "x.json").exists() and (base / "sub" / "n.json").exists()

    assert backups.delete_backup("ok.json") is True
    assert not (base / "ok.json").exists()


# ------------------------------------------------------------------ handlers (PostgreSQL)

@pytest_asyncio.fixture
async def maker():
    from database.engine import async_session_maker, engine
    from database.models import Bid, MasterProfile, Order, OrderView, SupportTicket, User
    yield async_session_maker
    async with async_session_maker() as s:
        ids = select(User.id).where(User.telegram_id >= TG_BASE, User.telegram_id < TG_BASE + 1000)
        await s.execute(delete(Bid).where(Bid.order_id.in_(select(Order.id).where(Order.client_id.in_(ids)))))
        await s.execute(delete(OrderView).where(OrderView.user_id.in_(ids)))
        await s.execute(delete(Order).where(Order.client_id.in_(ids)))
        await s.execute(delete(SupportTicket).where(SupportTicket.user_id.in_(ids)))
        await s.execute(delete(MasterProfile).where(MasterProfile.user_id.in_(ids)))
        await s.execute(delete(User).where(User.id.in_(ids)))
        await s.commit()
    await engine.dispose()


async def _world(maker):
    """owner (client) + stranger (another client) + master with one pending bid on the owner's order."""
    from database.models import Bid, BidStatus, Category, MasterProfile, MasterStatus, Order, OrderStatus, User, UserRole
    async with maker() as s:
        cat = (await s.execute(select(Category))).scalars().first()
        if cat is None:
            cat = Category(name="Тест")
            s.add(cat)
            await s.flush()
        owner = User(telegram_id=TG_BASE + 1, full_name="Owner", role=UserRole.CLIENT, phone_number="+7000")
        stranger = User(telegram_id=TG_BASE + 2, full_name="Stranger", role=UserRole.CLIENT, phone_number="+7111")
        master = User(telegram_id=TG_BASE + 3, full_name="Master", role=UserRole.MASTER, phone_number="+7222")
        s.add_all([owner, stranger, master])
        await s.flush()
        prof = MasterProfile(user_id=master.id, status=MasterStatus.APPROVED)
        order = Order(client_id=owner.id, category_id=cat.id, description="secret order", status=OrderStatus.NEW)
        s.add_all([prof, order])
        await s.flush()
        bid = Bid(order_id=order.id, master_id=prof.id, suggested_price=1000, status=BidStatus.PENDING)
        s.add(bid)
        await s.commit()
        return dict(owner=owner.telegram_id, stranger=stranger.telegram_id, master=master.telegram_id,
                    order=order.id, bid=bid.id)


def _msg():
    bot = SimpleNamespace(send_message=AsyncMock())
    # like a real callback: the message belongs to the BOT, so message.from_user must never be trusted
    return SimpleNamespace(answer=AsyncMock(), bot=bot, from_user=SimpleNamespace(id=1, is_bot=True))


async def _order(maker, order_id):
    from database.models import Order
    async with maker() as s:
        return (await s.execute(select(Order).where(Order.id == order_id))).scalar_one()


async def _bid(maker, bid_id):
    from database.models import Bid
    async with maker() as s:
        return (await s.execute(select(Bid).where(Bid.id == bid_id))).scalar_one()


@needs_pg
@pytest.mark.asyncio
async def test_stranger_cannot_accept_someone_elses_bid(maker):
    from bot.handlers.client_cabinet import process_accept_bid
    from database.models import BidStatus, OrderStatus
    w = await _world(maker)
    m = _msg()
    await process_accept_bid(m, w["bid"], w["stranger"])
    assert "не являетесь владельцем" in m.answer.call_args.args[0]
    m.bot.send_message.assert_not_called()                      # no phone numbers were leaked to anyone
    assert (await _order(maker, w["order"])).status == OrderStatus.NEW
    assert (await _bid(maker, w["bid"])).status == BidStatus.PENDING


@needs_pg
@pytest.mark.asyncio
async def test_owner_can_accept_and_second_accept_is_refused(maker):
    from bot.handlers.client_cabinet import process_accept_bid
    from database.models import BidStatus, OrderStatus
    w = await _world(maker)
    m = _msg()
    await process_accept_bid(m, w["bid"], w["owner"])
    assert (await _order(maker, w["order"])).status == OrderStatus.ACTIVE
    assert (await _bid(maker, w["bid"])).status == BidStatus.ACCEPTED
    assert m.bot.send_message.await_args.args[0] == w["master"]  # the master got the client's contacts

    m2 = _msg()
    await process_accept_bid(m2, w["bid"], w["owner"])           # double tap / replayed command
    assert m2.bot.send_message.await_count == 0
    assert "недоступен" in m2.answer.call_args.args[0]


@needs_pg
@pytest.mark.asyncio
async def test_rejected_bid_cannot_be_accepted(maker):
    from bot.handlers.client_cabinet import process_accept_bid
    from database.models import Bid, BidStatus, OrderStatus
    w = await _world(maker)
    async with maker() as s:
        (await s.get(Bid, w["bid"])).status = BidStatus.REJECTED
        await s.commit()
    m = _msg()
    await process_accept_bid(m, w["bid"], w["owner"])
    assert (await _order(maker, w["order"])).status == OrderStatus.NEW


@needs_pg
@pytest.mark.asyncio
async def test_only_owner_sees_the_order(maker):
    from bot.handlers.client_cabinet import process_view_order
    w = await _world(maker)
    m = _msg()
    await process_view_order(m, w["order"], w["stranger"])
    assert m.answer.await_count == 1 and "не найдена" in m.answer.call_args.args[0]
    assert "secret order" not in m.answer.call_args.args[0]

    m = _msg()
    await process_view_order(m, w["order"], w["owner"])
    assert "secret order" in m.answer.call_args_list[0].args[0]


@needs_pg
@pytest.mark.asyncio
async def test_stranger_cannot_reject_someone_elses_bid(maker):
    from bot.handlers.client_cabinet import client_reject_bid_callback
    from database.models import BidStatus

    def cb(tg_id, bid_id):
        return SimpleNamespace(
            data=f"client_reject_bid:{bid_id}", from_user=SimpleNamespace(id=tg_id),
            answer=AsyncMock(), bot=SimpleNamespace(send_message=AsyncMock()),
            message=SimpleNamespace(delete=AsyncMock()),
        )

    w = await _world(maker)
    c = cb(w["stranger"], w["bid"])
    await client_reject_bid_callback(c)
    assert (await _bid(maker, w["bid"])).status == BidStatus.PENDING
    c.bot.send_message.assert_not_called()

    c = cb(w["owner"], w["bid"])
    await client_reject_bid_callback(c)
    assert (await _bid(maker, w["bid"])).status == BidStatus.REJECTED


@needs_pg
@pytest.mark.asyncio
async def test_support_text_is_escaped_for_admins(maker, monkeypatch):
    from bot.core.config import config
    from bot.handlers.support import process_support_msg
    await _world(maker)
    monkeypatch.setattr(config, "ADMIN_IDS", [42])
    m = _msg()
    m.from_user = SimpleNamespace(id=TG_BASE + 2)
    m.text = "цена < 5000 и > 2000 <script>"
    await process_support_msg(m, SimpleNamespace(clear=AsyncMock()))
    sent = m.bot.send_message.await_args.args[1]
    assert "&lt; 5000" in sent and "<script>" not in sent
