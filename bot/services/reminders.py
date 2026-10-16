"""Re-notifying masters about an order nobody has bid on.

Flow
1. ``REMINDER_AFTER_MINUTES`` after creation a NEW order without bids makes the bot ask the client once
   what to do: remind all masters of the category / only those who have not opened the order / do nothing.
2. The choice is stored on the order (``remind_mode``).
3. The reminder itself is sent only in working hours (local time = ``TZ_OFFSET_HOURS``), skips masters in
   "do not disturb", masters who already bid and (in "unopened" mode) masters who have already opened the card.
Each order is prompted once and reminded once.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import selectinload

from bot.core.config import config
from database.models import (
    Bid, Category, MasterProfile, Order, OrderStatus, OrderView, User, UserRole, master_district_areas,
)

logger = logging.getLogger(__name__)

MODE_ALL = "all"
MODE_UNOPENED = "unopened"
MODE_SKIP = "skip"
MODES = (MODE_ALL, MODE_UNOPENED, MODE_SKIP)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_time(now: Optional[datetime] = None) -> datetime:
    """Local wall-clock time (naive) for the configured TZ offset. `now` is a naive UTC datetime."""
    return (now or utcnow()) + timedelta(hours=config.TZ_OFFSET_HOURS)


def in_working_hours(now: Optional[datetime] = None) -> bool:
    start, end = config.WORK_HOURS_START, config.WORK_HOURS_END
    hour = local_time(now).hour
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # window over midnight


def is_in_dnd(now_s: str, start_s: Optional[str], end_s: Optional[str]) -> bool:
    """Is 'HH:MM' inside the master's do-not-disturb window?"""
    if not start_s or not end_s or start_s == end_s:
        return False
    if start_s < end_s:
        return start_s <= now_s < end_s
    return now_s >= start_s or now_s < end_s


async def find_masters_for_order(session, category_id: int, district_id: Optional[int]) -> List[User]:
    """Masters who should hear about an order: approved-by-role MASTER, notifications on, visible,
    subscribed to the category and working in the district (or with no district limit)."""
    stmt = (
        select(User).join(User.master_profile).join(MasterProfile.categories)
        .where(
            User.role == UserRole.MASTER,
            User.notifications_enabled == True,  # noqa: E712
            User.visible_for_new_orders == True,  # noqa: E712
            Category.id == category_id,
        )
    )
    has_no_districts = ~exists().where(master_district_areas.c.master_profile_id == MasterProfile.id)
    works_in_district = exists().where(
        (master_district_areas.c.master_profile_id == MasterProfile.id)
        & (master_district_areas.c.district_id == district_id)
    )
    stmt = stmt.where(or_(works_in_district, has_no_districts)).distinct()
    return list((await session.execute(stmt)).scalars().all())


async def record_view(session, order_id: int, user_id: int) -> None:
    """Remember that a master opened the order card (idempotent). Does NOT commit."""
    if await session.get(OrderView, (order_id, user_id)) is None:
        session.add(OrderView(order_id=order_id, user_id=user_id))


async def due_for_prompt(session, now: Optional[datetime] = None) -> List[Order]:
    """NEW orders without bids that have waited long enough and whose client was not asked yet."""
    if config.REMINDER_AFTER_MINUTES <= 0:
        return []
    now = now or utcnow()
    stmt = (
        select(Order).options(selectinload(Order.client), selectinload(Order.category))
        .where(
            Order.status == OrderStatus.NEW,
            Order.reminder_prompted_at.is_(None),
            Order.created_at <= now - timedelta(minutes=config.REMINDER_AFTER_MINUTES),
            ~exists().where(Bid.order_id == Order.id),
        )
    )
    if config.ORDER_TTL_HOURS > 0:  # do not nag about orders that are about to be auto-closed
        stmt = stmt.where(Order.created_at > now - timedelta(hours=config.ORDER_TTL_HOURS))
    return list((await session.execute(stmt)).scalars().all())


async def set_client_choice(session, order_id: int, client_telegram_id: int, mode: str) -> str:
    """Stores the client's decision. Returns: ok | not_found | closed | has_bids | already. Does NOT commit."""
    if mode not in MODES:
        return "not_found"
    order = (await session.execute(
        select(Order).options(selectinload(Order.client)).where(Order.id == order_id).with_for_update()
    )).scalar_one_or_none()
    if not order or order.client.telegram_id != client_telegram_id:
        return "not_found"
    if order.status != OrderStatus.NEW:
        return "closed"
    if order.remind_mode is not None:
        return "already"
    has_bids = (await session.execute(select(exists().where(Bid.order_id == order.id)))).scalar()
    if has_bids:
        return "has_bids"
    order.remind_mode = mode
    return "ok"


async def due_for_send(session) -> List[Order]:
    return list((await session.execute(
        select(Order).options(selectinload(Order.client), selectinload(Order.category), selectinload(Order.district))
        .where(
            Order.status == OrderStatus.NEW,
            Order.remind_mode.in_((MODE_ALL, MODE_UNOPENED)),
            Order.reminder_sent_at.is_(None),
        )
    )).scalars().all())


async def reminder_recipients(session, order: Order, now: Optional[datetime] = None) -> List[User]:
    masters = await find_masters_for_order(session, order.category_id, order.district_id)
    bidders = set((await session.execute(
        select(User.id).join(MasterProfile, MasterProfile.user_id == User.id)
        .join(Bid, Bid.master_id == MasterProfile.id).where(Bid.order_id == order.id)
    )).scalars().all())
    viewed = set()
    if order.remind_mode == MODE_UNOPENED:
        viewed = set((await session.execute(
            select(OrderView.user_id).where(OrderView.order_id == order.id)
        )).scalars().all())
    now_s = local_time(now).strftime("%H:%M")
    return [
        m for m in masters
        if m.id != order.client_id and m.id not in bidders and m.id not in viewed
        and not is_in_dnd(now_s, m.dnd_start, m.dnd_end)
    ]


@dataclass
class CycleResult:
    prompted: int = 0
    reminded_orders: int = 0
    reminded_masters: int = 0


def prompt_keyboard(order_id: int):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Напомнить всем мастерам", callback_data=f"order_remind:{order_id}:{MODE_ALL}")],
        [InlineKeyboardButton(text="👀 Только тем, кто не открывал заказ", callback_data=f"order_remind:{order_id}:{MODE_UNOPENED}")],
        [InlineKeyboardButton(text="Не нужно", callback_data=f"order_remind:{order_id}:{MODE_SKIP}")],
    ])


async def run_reminder_cycle(bot, session_maker, now: Optional[datetime] = None) -> CycleResult:
    """One pass of the background worker. `bot` only needs an async send_message()."""
    from bot.utils.text import esc
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    now = now or utcnow()
    result = CycleResult()
    if config.REMINDER_AFTER_MINUTES <= 0 or not in_working_hours(now):
        return result

    # 1) ask clients whose order got no bids
    async with session_maker() as session:
        for order in await due_for_prompt(session, now):
            order.reminder_prompted_at = now  # mark first: never nag twice, even if sending fails
            try:
                await bot.send_message(
                    order.client.telegram_id,
                    f"⏳ <b>По заявке №{order.id} ({esc(order.category.name)}) пока нет откликов.</b>\n\n"
                    "Мастера могли не заметить уведомление. Напомнить им о заказе?",
                    parse_mode="HTML",
                    reply_markup=prompt_keyboard(order.id),
                )
                result.prompted += 1
            except Exception as e:
                logger.warning(f"Could not ask client {order.client.telegram_id} about reminder: {e}")
        await session.commit()

    # 2) send the reminders the clients asked for
    async with session_maker() as session:
        for order in await due_for_send(session):
            order.reminder_sent_at = now
            recipients = await reminder_recipients(session, order, now)
            text = (
                f"🔔 <b>Напоминание: заказ №{order.id} всё ещё ждёт откликов</b>\n\n"
                f"📂 {esc(order.category.name)}\n"
                f"📝 {esc((order.description or '')[:300])}\n"
                f"💰 Бюджет: {order.budget or 'Договорная'}\n"
                f"📍 Район: {esc(order.district.name if order.district else '—')}"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📥 Посмотреть и откликнуться", callback_data=f"master_view_order:{order.id}")
            ]])
            sent = 0
            for master in recipients:
                try:
                    await bot.send_message(master.telegram_id, text, parse_mode="HTML", reply_markup=kb)
                    sent += 1
                except Exception as e:
                    logger.warning(f"Could not remind master {master.telegram_id}: {e}")
            result.reminded_orders += 1
            result.reminded_masters += sent
            logger.info(f"Order #{order.id}: reminder ({order.remind_mode}) sent to {sent} masters")
            try:
                await bot.send_message(
                    order.client.telegram_id,
                    f"✅ Напомнил мастерам о заявке №{order.id} (получили: {sent}).",
                )
            except Exception:
                pass
        await session.commit()
    return result
