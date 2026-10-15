"""Points (balance) operations.

Every function works inside the caller's session/transaction and does NOT commit:
the caller decides when the unit of work is complete. User rows are locked with
SELECT ... FOR UPDATE, so parallel operations cannot overdraw a balance.
"""
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, or_, select

from database.models import MasterProfile, MasterStatus, Transaction, TransactionType, User

BID_COST = 50
WELCOME_BONUS = 2000
REFERRER_REWARD = 1000
WELCOME_DESCRIPTION = "Приветственный бонус при регистрации"


class InsufficientFunds(Exception):
    """Raised when an operation would make a balance negative."""


def bid_fee_description(order_id: int) -> str:
    return f"Отклик на заказ №{order_id}"


async def lock_user(session, user_id: int) -> User:
    return (await session.execute(
        select(User).where(User.id == user_id).with_for_update()
    )).scalar_one()


async def adjust(
    session,
    user_id: int,
    amount: int,
    tx_type: TransactionType,
    description: str,
    order_id: Optional[int] = None,
) -> User:
    """Changes balance by `amount` (may be negative) and records a transaction."""
    if amount == 0:
        raise ValueError("amount must not be zero")
    user = await lock_user(session, user_id)
    if user.points + amount < 0:
        raise InsufficientFunds(f"balance {user.points}, change {amount}")
    user.points += amount
    session.add(Transaction(
        user_id=user.id, amount=amount, type=tx_type, description=description, order_id=order_id,
    ))
    await session.flush()
    return user


async def credit(session, user_id, amount, tx_type, description, order_id=None) -> User:
    if amount <= 0:
        raise ValueError("credit amount must be positive")
    return await adjust(session, user_id, amount, tx_type, description, order_id)


async def charge(session, user_id, amount, tx_type, description, order_id=None) -> User:
    if amount <= 0:
        raise ValueError("charge amount must be positive")
    return await adjust(session, user_id, -amount, tx_type, description, order_id)


async def refund_order_fees(session, order_id: int, user_id: int, reason: str = "заказ отменён") -> int:
    """Returns what the user actually paid for bidding on this order, minus anything already refunded.

    Safe to call repeatedly: a second call refunds nothing.
    """
    description = bid_fee_description(order_id)
    paid = (await session.execute(
        select(func.coalesce(func.sum(-Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.CONTACT_FEE,
            or_(Transaction.order_id == order_id, Transaction.description == description),
        )
    )).scalar() or 0
    already = (await session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.REFUND,
            Transaction.order_id == order_id,
        )
    )).scalar() or 0
    to_refund = paid - already
    if to_refund <= 0:
        return 0
    await credit(session, user_id, to_refund, TransactionType.REFUND,
                 f"Возврат баллов: заказ №{order_id} — {reason}", order_id)
    return to_refund


@dataclass
class ApprovalResult:
    granted: bool                      # False when the master was already approved (nothing changed)
    welcome: int = 0
    inviter_telegram_id: Optional[int] = None
    inviter_bonus: int = 0


async def approve_master(session, profile: MasterProfile) -> ApprovalResult:
    """Approves a master and pays the welcome and referral bonuses — each at most once."""
    if profile.status == MasterStatus.APPROVED:
        return ApprovalResult(granted=False)
    profile.status = MasterStatus.APPROVED
    user = await lock_user(session, profile.user_id)
    result = ApprovalResult(granted=True)

    welcome_paid = (await session.execute(
        select(Transaction.id).where(
            Transaction.user_id == user.id,
            Transaction.type == TransactionType.REFERRAL_BONUS,
            Transaction.description == WELCOME_DESCRIPTION,
        )
    )).first()
    if not welcome_paid:
        await credit(session, user.id, WELCOME_BONUS, TransactionType.REFERRAL_BONUS, WELCOME_DESCRIPTION)
        result.welcome = WELCOME_BONUS

    if user.referred_by:
        marker = f"[ref:{user.id}]"
        reward_paid = (await session.execute(
            select(Transaction.id).where(
                Transaction.user_id == user.referred_by,
                Transaction.type == TransactionType.REFERRAL_BONUS,
                Transaction.description.like(f"%{marker}"),
            )
        )).first()
        if not reward_paid:
            inviter = await credit(
                session, user.referred_by, REFERRER_REWARD, TransactionType.REFERRAL_BONUS,
                f"Бонус за регистрацию мастера {user.full_name} {marker}",
            )
            result.inviter_telegram_id = inviter.telegram_id
            result.inviter_bonus = REFERRER_REWARD
    return result
