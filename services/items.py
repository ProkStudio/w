from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Item, Purchase, User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def get_active_items(session: AsyncSession) -> list[Item]:
    query = (
        select(Item)
        .where(Item.expires_at > utc_now())
        .order_by(Item.expires_at.asc(), Item.created_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_item_by_id(session: AsyncSession, item_id: int) -> Item | None:
    result = await session.execute(select(Item).where(Item.id == item_id))
    return result.scalar_one_or_none()


async def get_active_item_by_id(session: AsyncSession, item_id: int) -> Item | None:
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.expires_at > utc_now())
    )
    return result.scalar_one_or_none()


async def create_item(
    session: AsyncSession,
    *,
    title: str,
    description: str,
    price: Decimal,
    content: str,
    expires_at: datetime,
) -> Item:
    item = Item(
        title=title.strip(),
        description=description.strip(),
        price=price,
        content=content.strip(),
        expires_at=expires_at,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_item(
    session: AsyncSession,
    *,
    item: Item,
    title: str,
    description: str,
    price: Decimal,
    content: str,
    expires_at: datetime,
) -> Item:
    item.title = title.strip()
    item.description = description.strip()
    item.price = price
    item.content = content.strip()
    item.expires_at = expires_at
    await session.commit()
    await session.refresh(item)
    return item


async def delete_item_by_id(session: AsyncSession, item_id: int) -> bool:
    result = await session.execute(delete(Item).where(Item.id == item_id))
    await session.commit()
    return (result.rowcount or 0) > 0


async def has_user_purchased_item(session: AsyncSession, user_id: int, item_id: int) -> bool:
    result = await session.execute(
        select(Purchase.id).where(Purchase.user_id == user_id, Purchase.item_id == item_id)
    )
    return result.scalar_one_or_none() is not None


async def create_purchase(
    session: AsyncSession,
    *,
    user_id: int,
    item_id: int,
    amount: Decimal,
    payment_method: str,
) -> Purchase:
    purchase = Purchase(
        user_id=user_id,
        item_id=item_id,
        amount=amount,
        payment_method=payment_method,
    )
    session.add(purchase)
    await session.commit()
    await session.refresh(purchase)
    return purchase


async def get_user_purchases(session: AsyncSession, user_id: int) -> list[Purchase]:
    result = await session.execute(
        select(Purchase)
        .where(Purchase.user_id == user_id)
        .options(selectinload(Purchase.item))
        .order_by(Purchase.created_at.desc())
    )
    return list(result.scalars().all())


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def count_active_items(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Item.id)).where(Item.expires_at > utc_now()))
    return int(result.scalar_one())


async def get_all_items(session: AsyncSession) -> list[Item]:
    result = await session.execute(select(Item).order_by(Item.created_at.desc()))
    return list(result.scalars().all())
