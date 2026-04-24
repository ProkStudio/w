from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import (
    back_to_main_kb,
    buy_methods_kb,
    catalog_kb,
    item_card_kb,
    main_menu_kb,
    my_purchases_kb,
)
from services import items as item_service
from services import referrals as referral_service

router = Router(name="user")


def format_remaining_time(expires_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    diff = expires_at - now
    total_seconds = int(diff.total_seconds())
    if total_seconds <= 0:
        return "Истёк"

    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}д {hours}ч {minutes}м"
    return f"{hours}ч {minutes}м"


def fmt_money(value: Decimal) -> str:
    return f"{Decimal(value):.2f} RUB"


@router.message(CommandStart())
async def start_handler(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    if message.from_user is None:
        return

    ref_id: int | None = None
    if command.args and command.args.isdigit():
        ref_id = int(command.args)

    await referral_service.get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        referrer_telegram_id=ref_id,
    )

    await message.answer(
        "Добро пожаловать в магазин цифровых товаров.\nВыберите раздел:",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:catalog")
async def menu_catalog(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None:
        return

    active_items = await item_service.get_active_items(session)
    if not active_items:
        await callback.message.edit_text(
            "Сейчас нет активных товаров.",
            reply_markup=back_to_main_kb(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "Каталог активных товаров:",
        reply_markup=catalog_kb(active_items, page=1),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("menu:catalog:page:"))
async def menu_catalog_page(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None:
        return

    active_items = await item_service.get_active_items(session)
    if not active_items:
        await callback.message.edit_text(
            "Сейчас нет активных товаров.",
            reply_markup=back_to_main_kb(),
        )
        await callback.answer()
        return

    page = int(callback.data.split(":")[-1])
    await callback.message.edit_text(
        "Каталог активных товаров:",
        reply_markup=catalog_kb(active_items, page=page),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:catalog:noop")
async def menu_catalog_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("item:"))
async def item_card(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None:
        return

    item_id = int(callback.data.split(":")[1])
    item = await item_service.get_active_item_by_id(session, item_id)
    if item is None:
        await callback.answer("Товар недоступен или срок действия истёк.", show_alert=True)
        return

    text = (
        f"🧾 <b>{item.title}</b>\n\n"
        f"{item.description}\n\n"
        f"Цена: <b>{fmt_money(item.price)}</b>\n"
        f"До окончания: <b>{format_remaining_time(item.expires_at)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=item_card_kb(item.id))
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def choose_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.from_user is None:
        return

    item_id = int(callback.data.split(":")[1])
    item = await item_service.get_active_item_by_id(session, item_id)
    if item is None:
        await callback.answer("Товар недоступен.", show_alert=True)
        return

    user = await referral_service.get_or_create_user(session, callback.from_user.id)
    if await item_service.has_user_purchased_item(session, user.id, item_id):
        await callback.answer("Вы уже купили этот товар.", show_alert=True)
        return

    await callback.message.edit_text(
        f"Выберите способ оплаты для товара: {item.title}",
        reply_markup=buy_methods_kb(item_id),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def menu_profile(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    user = await referral_service.get_or_create_user(session, callback.from_user.id)
    stats = await referral_service.get_referral_stats(session, user.id)
    me = await callback.bot.get_me()
    referral_link = f"https://t.me/{me.username}?start={callback.from_user.id}"

    text = (
        f"👤 Ваш профиль\n\n"
        f"ID: <code>{callback.from_user.id}</code>\n"
        f"Баланс: <b>{fmt_money(user.balance)}</b>\n\n"
        f"Реферальная ссылка:\n{referral_link}\n\n"
        f"Приглашено: <b>{stats.invited_count}</b>\n"
        f"Заработано с рефералов: <b>{fmt_money(stats.earned_total)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:purchases")
async def menu_purchases(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.from_user is None:
        return

    user = await referral_service.get_or_create_user(session, callback.from_user.id)
    purchases = await item_service.get_user_purchases(session, user.id)
    if not purchases:
        await callback.message.edit_text(
            "У вас пока нет покупок.",
            reply_markup=back_to_main_kb(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "Ваши покупки:",
        reply_markup=my_purchases_kb(purchases),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("purchase:"))
async def open_purchase(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.from_user is None:
        return

    item_id = int(callback.data.split(":")[1])
    user = await referral_service.get_or_create_user(session, callback.from_user.id)

    has_access = await item_service.has_user_purchased_item(session, user.id, item_id)
    if not has_access:
        await callback.answer("Покупка не найдена.", show_alert=True)
        return

    item = await item_service.get_item_by_id(session, item_id)
    if item is None:
        await callback.answer("Товар больше не существует.", show_alert=True)
        return

    await callback.message.edit_text(
        f"📦 <b>{item.title}</b>\n\n{item.content}",
        reply_markup=back_to_main_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:support")
async def menu_support(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    await callback.message.edit_text(
        "ℹ️ Поддержка\n\nЕсли возникли вопросы, напишите администратору @your_support.",
        reply_markup=back_to_main_kb(),
    )
    await callback.answer()
