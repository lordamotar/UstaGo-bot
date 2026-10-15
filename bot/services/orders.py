from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from bot.services import billing
from database.models import Bid, MasterProfile, Order, OrderStatus


@dataclass
class CancelNotice:
    master_telegram_id: int
    bid_status: str
    refunded: int


@dataclass
class ExpiredOrder:
    order_id: int
    client_telegram_id: int
    notices: List[CancelNotice] = field(default_factory=list)


async def cancel_order(session, order_id: int, reason: str = "отменён клиентом") -> List[CancelNotice]:
    """Cancels an open order and refunds bid fees to every master with a non-rejected bid. Does NOT commit."""
    order = (await session.execute(
        select(Order)
        .options(selectinload(Order.bids).joinedload(Bid.master).joinedload(MasterProfile.user))
        .where(Order.id == order_id)
    )).scalar_one_or_none()
    if not order or order.status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED):
        return []
    order.status = OrderStatus.CANCELLED

    notices: List[CancelNotice] = []
    seen = set()
    for bid in order.bids:
        if bid.status == "rejected":
            continue
        master_user = bid.master.user
        if master_user.id in seen:
            continue
        seen.add(master_user.id)
        refunded = await billing.refund_order_fees(session, order.id, master_user.id, reason)
        notices.append(CancelNotice(master_user.telegram_id, bid.status, refunded))
    return notices


async def expire_stale_orders(session, ttl_hours: int, now: Optional[datetime] = None) -> List[ExpiredOrder]:
    """Cancels NEW orders older than `ttl_hours` (client never picked a master). Does NOT commit."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=ttl_hours)
    stale = (await session.execute(
        select(Order).options(selectinload(Order.client))
        .where(Order.status == OrderStatus.NEW, Order.created_at < cutoff)
    )).scalars().all()

    expired: List[ExpiredOrder] = []
    for order in stale:
        notices = await cancel_order(session, order.id, "срок заявки истёк")
        expired.append(ExpiredOrder(order.id, order.client.telegram_id, notices))
    return expired
