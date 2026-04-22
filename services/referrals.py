from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Referral, User


@dataclass(slots=True)
class ReferralStats:
    invited_count: int
    earned_total: Decimal


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    referrer_telegram_id: int | None = None,
) -> User:
    existing = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = existing.scalar_one_or_none()
    if user is not None:
        return user

    referrer_id: int | None = None
    if referrer_telegram_id and referrer_telegram_id != telegram_id:
        ref_result = await session.execute(select(User).where(User.telegram_id == referrer_telegram_id))
        referrer = ref_result.scalar_one_or_none()
        if referrer:
            referrer_id = referrer.id

    user = User(telegram_id=telegram_id, referrer_id=referrer_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_referral_stats(session: AsyncSession, user_id: int) -> ReferralStats:
    invited_result = await session.execute(
        select(func.count(User.id)).where(User.referrer_id == user_id)
    )
    invited_count = int(invited_result.scalar_one())

    earned_result = await session.execute(
        select(func.coalesce(func.sum(Referral.profit), 0)).where(Referral.referrer_id == user_id)
    )
    earned_total = Decimal(str(earned_result.scalar_one()))
    return ReferralStats(invited_count=invited_count, earned_total=earned_total)


async def apply_referral_reward(
    session: AsyncSession,
    *,
    buyer: User,
    purchase_amount: Decimal,
    percent: Decimal,
) -> Decimal:
    if buyer.referrer_id is None:
        return Decimal("0")

    reward = (purchase_amount * percent / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_DOWN,
    )
    if reward <= 0:
        return Decimal("0")

    referrer = await get_user_by_id(session, buyer.referrer_id)
    if referrer is None:
        return Decimal("0")

    referrer.balance = Decimal(referrer.balance) + reward
    referral_record = Referral(
        referrer_id=referrer.id,
        user_id=buyer.id,
        profit=reward,
    )
    session.add(referral_record)
    await session.commit()
    return reward
