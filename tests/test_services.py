"""Tests for the real business logic in bot/services (billing, bidding, orders) and bot/utils/parsing.

They run against an in-memory SQLite database; row locks (FOR UPDATE) are no-ops there, so concurrency
is not covered here — only the rules themselves.

Run with:  python -m pytest tests/test_services.py -v
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bot.core.config import config
from bot.services import billing, bidding
from bot.services.orders import cancel_order, expire_stale_orders
from bot.utils.parsing import parse_amount
from database.base import Base
from database.models import (
    Bid, Category, MasterProfile, MasterStatus, Order, OrderStatus, Transaction, TransactionType, User, UserRole,
)


@pytest_asyncio.fixture
async def session():
    """In-memory SQLite by default.

    Set TEST_DATABASE_URL (e.g. postgresql+asyncpg://...) to run the very same tests against a real,
    already-migrated PostgreSQL (`alembic upgrade head`); every test is rolled back, nothing is persisted.
    """
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        engine = create_async_engine(url)
    else:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
        await s.rollback()
    await engine.dispose()


_tg = iter(range(1000, 10**6))


async def make_user(s, name="User", role=UserRole.CLIENT, points=0, referred_by=None) -> User:
    user = User(telegram_id=next(_tg), full_name=name, role=role, points=points, referred_by=referred_by)
    s.add(user)
    await s.flush()
    return user


async def make_master(s, name="Master", points=200, status=MasterStatus.APPROVED, referred_by=None):
    user = await make_user(s, name, UserRole.MASTER, points, referred_by)
    profile = MasterProfile(user_id=user.id, status=status)
    s.add(profile)
    await s.flush()
    return user, profile


async def make_order(s, client, status=OrderStatus.NEW, created_at=None) -> Order:
    category = (await s.execute(select(Category))).scalars().first()
    if category is None:
        category = Category(name="Электрик")
        s.add(category)
        await s.flush()
    order = Order(client_id=client.id, category_id=category.id, description="test", status=status)
    if created_at:
        order.created_at = created_at
    s.add(order)
    await s.flush()
    return order


async def balance(s, user) -> int:
    await s.refresh(user)
    return user.points


async def tx_count(s, user_id=None) -> int:
    q = select(func.count(Transaction.id))
    if user_id:
        q = q.where(Transaction.user_id == user_id)
    return (await s.execute(q)).scalar()


# ---------------------------------------------------------------- parsing

@pytest.mark.parametrize("text,expected", [
    ("15000", 15000),
    ("5 000", 5000),
    ("5 000 тг", 5000),
    ("от 5 000 до 7 000", 5000),
    ("5000-7000", 5000),
    ("договорная", None),
    ("", None),
    (None, None),
])
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


# ---------------------------------------------------------------- billing

async def test_charge_and_credit_update_balance_and_log_transactions(session):
    user = await make_user(session, points=100)
    order = await make_order(session, await make_user(session, "Client"))
    await billing.charge(session, user.id, 30, TransactionType.CONTACT_FEE, "fee", order_id=order.id)
    await billing.credit(session, user.id, 5, TransactionType.ADMIN_ADJUSTMENT, "bonus")
    assert await balance(session, user) == 75
    fee_tx = (await session.execute(select(Transaction).where(Transaction.type == TransactionType.CONTACT_FEE))).scalar_one()
    assert fee_tx.amount == -30 and fee_tx.order_id == order.id


async def test_charge_with_insufficient_funds_changes_nothing(session):
    user = await make_user(session, points=20)
    with pytest.raises(billing.InsufficientFunds):
        await billing.charge(session, user.id, 50, TransactionType.CONTACT_FEE, "fee")
    assert await balance(session, user) == 20
    assert await tx_count(session) == 0


async def test_zero_and_negative_amounts_are_rejected(session):
    user = await make_user(session, points=100)
    with pytest.raises(ValueError):
        await billing.adjust(session, user.id, 0, TransactionType.ADMIN_ADJUSTMENT, "x")
    with pytest.raises(ValueError):
        await billing.credit(session, user.id, -5, TransactionType.ADMIN_ADJUSTMENT, "x")
    with pytest.raises(ValueError):
        await billing.charge(session, user.id, -5, TransactionType.CONTACT_FEE, "x")


async def test_refund_returns_paid_amount_exactly_once(session):
    client = await make_user(session)
    master, _ = await make_master(session, points=200)
    order = await make_order(session, client)
    await billing.charge(session, master.id, 50, TransactionType.CONTACT_FEE,
                         billing.bid_fee_description(order.id), order.id)
    assert await billing.refund_order_fees(session, order.id, master.id) == 50
    assert await billing.refund_order_fees(session, order.id, master.id) == 0
    assert await balance(session, master) == 200


async def test_refund_is_zero_when_nothing_was_paid(session):
    client = await make_user(session)
    master, _ = await make_master(session, points=200)
    order = await make_order(session, client)
    assert await billing.refund_order_fees(session, order.id, master.id) == 0
    assert await balance(session, master) == 200


async def test_refund_covers_legacy_fee_without_order_id(session):
    client = await make_user(session)
    master, _ = await make_master(session, points=150)
    order = await make_order(session, client)
    session.add(Transaction(user_id=master.id, amount=-50, type=TransactionType.CONTACT_FEE,
                            description=billing.bid_fee_description(order.id)))
    await session.flush()
    assert await billing.refund_order_fees(session, order.id, master.id) == 50
    assert await balance(session, master) == 200


async def test_approve_master_pays_welcome_and_referral_once(session):
    inviter = await make_user(session, "Inviter", points=0)
    master, profile = await make_master(session, points=0, status=MasterStatus.PENDING, referred_by=inviter.id)

    result = await billing.approve_master(session, profile)
    assert result.granted and result.welcome == billing.WELCOME_BONUS
    assert result.inviter_telegram_id == inviter.telegram_id
    assert await balance(session, master) == billing.WELCOME_BONUS
    assert await balance(session, inviter) == billing.REFERRER_REWARD

    again = await billing.approve_master(session, profile)
    assert again.granted is False
    assert await balance(session, master) == billing.WELCOME_BONUS
    assert await balance(session, inviter) == billing.REFERRER_REWARD


async def test_reapproval_after_rejection_does_not_pay_twice(session):
    inviter = await make_user(session, "Inviter")
    master, profile = await make_master(session, points=0, status=MasterStatus.PENDING, referred_by=inviter.id)
    await billing.approve_master(session, profile)
    profile.status = MasterStatus.REJECTED
    result = await billing.approve_master(session, profile)
    assert result.granted and result.welcome == 0 and result.inviter_telegram_id is None
    assert await balance(session, master) == billing.WELCOME_BONUS
    assert await balance(session, inviter) == billing.REFERRER_REWARD


# ---------------------------------------------------------------- bidding

async def test_successful_bid_charges_fee_and_creates_bid(session):
    client = await make_user(session)
    master, profile = await make_master(session, points=120)
    order = await make_order(session, client)

    result = await bidding.place_bid(session, master.telegram_id, order.id, 15000, "hi", free_orders=False)

    assert result.error is None
    assert result.client_telegram_id == client.telegram_id
    assert await balance(session, master) == 120 - billing.BID_COST
    bid = (await session.execute(select(Bid))).scalar_one()
    assert bid.suggested_price == 15000 and bid.master_id == profile.id
    fee = (await session.execute(select(Transaction).where(Transaction.type == TransactionType.CONTACT_FEE))).scalar_one()
    assert fee.order_id == order.id


async def test_free_mode_does_not_charge(session):
    client = await make_user(session)
    master, _ = await make_master(session, points=0)
    order = await make_order(session, client)
    result = await bidding.place_bid(session, master.telegram_id, order.id, 1000, "hi", free_orders=True)
    assert result.error is None
    assert await balance(session, master) == 0
    assert await tx_count(session) == 0


@pytest.mark.parametrize("status", [MasterStatus.PENDING, MasterStatus.REJECTED])
async def test_unapproved_master_cannot_bid_even_in_free_mode(session, status):
    client = await make_user(session)
    master, _ = await make_master(session, points=500, status=status)
    order = await make_order(session, client)
    result = await bidding.place_bid(session, master.telegram_id, order.id, 1000, "hi", free_orders=True)
    assert result.error and result.bid is None
    assert await balance(session, master) == 500


async def test_insufficient_balance_creates_no_bid_and_no_charge(session):
    client = await make_user(session)
    master, _ = await make_master(session, points=10)
    order = await make_order(session, client)
    result = await bidding.place_bid(session, master.telegram_id, order.id, 1000, "hi", free_orders=False)
    assert result.error and "Недостаточно" in result.error
    assert await balance(session, master) == 10
    assert (await session.execute(select(func.count(Bid.id)))).scalar() == 0


async def test_duplicate_bid_is_blocked_and_not_charged_twice(session):
    client = await make_user(session)
    master, _ = await make_master(session, points=200)
    order = await make_order(session, client)
    assert (await bidding.place_bid(session, master.telegram_id, order.id, 1, "a", False)).error is None
    second = await bidding.place_bid(session, master.telegram_id, order.id, 1, "b", False)
    assert second.error
    assert await balance(session, master) == 200 - billing.BID_COST


@pytest.mark.parametrize("status", [OrderStatus.ACTIVE, OrderStatus.COMPLETED, OrderStatus.CANCELLED])
async def test_cannot_bid_on_closed_order(session, status):
    client = await make_user(session)
    master, _ = await make_master(session, points=200)
    order = await make_order(session, client, status=status)
    assert (await bidding.place_bid(session, master.telegram_id, order.id, 1, "a", False)).error
    assert await balance(session, master) == 200


async def test_master_cannot_bid_on_own_order(session):
    master, _ = await make_master(session, points=200)
    order = await make_order(session, master)
    assert (await bidding.place_bid(session, master.telegram_id, order.id, 1, "a", False)).error


async def test_bid_limit_per_order(session, monkeypatch):
    monkeypatch.setattr(config, "MAX_BIDS_PER_ORDER", 2)
    client = await make_user(session)
    order = await make_order(session, client)
    for i in range(2):
        m, _ = await make_master(session, f"M{i}", points=200)
        assert (await bidding.place_bid(session, m.telegram_id, order.id, 1, "a", False)).error is None
    late, _ = await make_master(session, "Late", points=200)
    result = await bidding.place_bid(session, late.telegram_id, order.id, 1, "a", False)
    assert result.error and "максимальное" in result.error
    assert await balance(session, late) == 200


async def test_rejected_bids_do_not_count_towards_the_limit(session, monkeypatch):
    monkeypatch.setattr(config, "MAX_BIDS_PER_ORDER", 1)
    client = await make_user(session)
    order = await make_order(session, client)
    first, _ = await make_master(session, "First", points=200)
    await bidding.place_bid(session, first.telegram_id, order.id, 1, "a", False)
    (await session.execute(select(Bid))).scalar_one().status = "rejected"
    second, _ = await make_master(session, "Second", points=200)
    assert (await bidding.place_bid(session, second.telegram_id, order.id, 1, "a", False)).error is None


# ---------------------------------------------------------------- orders

async def test_cancel_order_refunds_active_bidders_but_not_rejected(session):
    client = await make_user(session)
    order = await make_order(session, client)
    kept, _ = await make_master(session, "Kept", points=200)
    rejected, _ = await make_master(session, "Rejected", points=200)
    await bidding.place_bid(session, kept.telegram_id, order.id, 1, "a", False)
    await bidding.place_bid(session, rejected.telegram_id, order.id, 1, "b", False)
    for bid in (await session.execute(select(Bid).join(MasterProfile).where(MasterProfile.user_id == rejected.id))).scalars():
        bid.status = "rejected"

    notices = await cancel_order(session, order.id)

    assert [n.master_telegram_id for n in notices] == [kept.telegram_id]
    assert notices[0].refunded == billing.BID_COST
    assert await balance(session, kept) == 200
    assert await balance(session, rejected) == 200 - billing.BID_COST
    await session.refresh(order)
    assert order.status == OrderStatus.CANCELLED


async def test_cancelling_twice_never_refunds_twice(session):
    client = await make_user(session)
    order = await make_order(session, client)
    master, _ = await make_master(session, points=200)
    await bidding.place_bid(session, master.telegram_id, order.id, 1, "a", False)
    await cancel_order(session, order.id)
    assert await cancel_order(session, order.id) == []
    assert await balance(session, master) == 200


async def test_free_mode_bid_gets_no_refund_on_cancel(session):
    client = await make_user(session)
    order = await make_order(session, client)
    master, _ = await make_master(session, points=0)
    await bidding.place_bid(session, master.telegram_id, order.id, 1, "a", free_orders=True)
    notices = await cancel_order(session, order.id)
    assert notices[0].refunded == 0
    assert await balance(session, master) == 0


async def test_expire_stale_orders_only_touches_old_new_orders(session):
    client = await make_user(session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    old = await make_order(session, client, created_at=now - timedelta(hours=100))
    fresh = await make_order(session, client, created_at=now - timedelta(hours=1))
    old_active = await make_order(session, client, status=OrderStatus.ACTIVE, created_at=now - timedelta(hours=100))
    master, _ = await make_master(session, points=200)
    await bidding.place_bid(session, master.telegram_id, old.id, 1, "a", False)

    expired = await expire_stale_orders(session, ttl_hours=72, now=now)

    assert [e.order_id for e in expired] == [old.id]
    assert expired[0].client_telegram_id == client.telegram_id
    assert expired[0].notices[0].refunded == billing.BID_COST
    assert await balance(session, master) == 200
    for o in (old, fresh, old_active):
        await session.refresh(o)
    assert (old.status, fresh.status, old_active.status) == (
        OrderStatus.CANCELLED, OrderStatus.NEW, OrderStatus.ACTIVE)


# ---------------------------------------------------------------- concurrency (real PostgreSQL only)

@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="needs a real PostgreSQL (row locks)")
async def test_parallel_bids_cannot_overdraw_the_balance():
    """The master can afford exactly ONE bid; two bids on different orders race — only one may win."""
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        client = await make_user(s, "Race client")
        master, _ = await make_master(s, "Race master", points=billing.BID_COST)
        first, second = await make_order(s, client), await make_order(s, client)
        await s.commit()
        client_id, master_id, tg, order_ids = client.id, master.id, master.telegram_id, [first.id, second.id]

    async def attempt(order_id):
        async with maker() as s:
            result = await bidding.place_bid(s, tg, order_id, 1, "x", free_orders=False)
            if result.error is None:
                await s.commit()
            return result.error

    try:
        results = await asyncio.gather(*(attempt(o) for o in order_ids))
        assert sorted(r is None for r in results) == [False, True], results
        async with maker() as s:
            assert (await s.get(User, master_id)).points == 0
            assert (await s.execute(select(func.count(Bid.id)).where(Bid.order_id.in_(order_ids)))).scalar() == 1
    finally:
        async with maker() as s:
            await s.execute(delete(Bid).where(Bid.order_id.in_(order_ids)))
            await s.execute(delete(Transaction).where(Transaction.user_id == master_id))
            await s.execute(delete(Order).where(Order.id.in_(order_ids)))
            await s.execute(delete(MasterProfile).where(MasterProfile.user_id == master_id))
            await s.execute(delete(User).where(User.id.in_([client_id, master_id])))
            await s.commit()
        await engine.dispose()
