from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from bot.core.config import config
from bot.services import billing
from database.models import (
    Bid, MasterStatus, Order, OrderStatus, TransactionType, User,
)
from database.models import BidStatus


@dataclass
class BidResult:
    error: Optional[str] = None
    bid: Optional[Bid] = None
    master_user: Optional[User] = None
    client_telegram_id: Optional[int] = None


async def bid_block_reason(session, user: Optional[User], order_id: int) -> Optional[str]:
    """Human-readable reason why this user cannot bid on the order, or None if bidding is allowed.

    `user` must be loaded together with `master_profile`.
    """
    profile = user.master_profile if user else None
    if not profile or profile.status != MasterStatus.APPROVED:
        return "❌ Откликаться могут только мастера, прошедшие модерацию."
    order = (await session.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order or order.status != OrderStatus.NEW:
        return "⚠️ Заказ уже недоступен для откликов."
    if order.client_id == user.id:
        return "❌ Нельзя откликаться на собственный заказ."
    duplicate = (await session.execute(
        select(Bid.id).where(Bid.order_id == order_id, Bid.master_id == profile.id)
    )).first()
    if duplicate:
        return "⚠️ Вы уже откликались на этот заказ."
    active_bids = (await session.execute(
        select(func.count(Bid.id)).where(Bid.order_id == order_id, Bid.status != BidStatus.REJECTED)
    )).scalar() or 0
    if active_bids >= config.MAX_BIDS_PER_ORDER:
        return "⚠️ К этой заявке уже набрано максимальное число откликов."
    return None


async def place_bid(
    session, telegram_id: int, order_id: int, price: Optional[int], message_text: str, free_orders: bool
) -> BidResult:
    """Validates, charges the fee and creates the bid. Does NOT commit."""
    user = (await session.execute(
        select(User).options(selectinload(User.master_profile))
        .where(User.telegram_id == telegram_id).with_for_update()
    )).scalar_one_or_none()
    reason = await bid_block_reason(session, user, order_id)
    if reason:
        return BidResult(error=reason)

    if not free_orders:
        try:
            await billing.charge(
                session, user.id, billing.BID_COST, TransactionType.CONTACT_FEE,
                billing.bid_fee_description(order_id), order_id,
            )
        except billing.InsufficientFunds:
            return BidResult(error=f"❌ Недостаточно баллов (нужно {billing.BID_COST}).")

    bid = Bid(order_id=order_id, master_id=user.master_profile.id,
              suggested_price=price or 0, message=message_text)
    session.add(bid)
    await session.flush()
    order = (await session.execute(
        select(Order).options(selectinload(Order.client)).where(Order.id == order_id)
    )).scalar_one()
    return BidResult(bid=bid, master_user=user, client_telegram_id=order.client.telegram_id)
