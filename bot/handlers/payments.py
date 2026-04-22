from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import back_to_main_kb, cryptobot_invoice_kb
from config import Settings
from services import items as item_service
from services import payments as payment_service
from services import referrals as referral_service

router = Router(name="payments")
logger = logging.getLogger(__name__)


async def finalize_purchase(
    *,
    session: AsyncSession,
    buyer_telegram_id: int,
    item_id: int,
    payment_method: str,
    amount: Decimal,
    settings: Settings,
) -> tuple[bool, str]:
    buyer = await referral_service.get_or_create_user(session, buyer_telegram_id)
    item = await item_service.get_item_by_id(session, item_id)
    if item is None:
        return False, "Товар не найден."
    if item.expires_at <= item_service.utc_now():
        return False, "Срок действия товара истёк."

    if await item_service.has_user_purchased_item(session, buyer.id, item_id):
        return False, "Вы уже купили этот товар."

    try:
        await item_service.create_purchase(
            session,
            user_id=buyer.id,
            item_id=item_id,
            amount=amount,
            payment_method=payment_method,
        )
    except IntegrityError:
        await session.rollback()
        return False, "Покупка уже была сохранена."

    await referral_service.apply_referral_reward(
        session,
        buyer=buyer,
        purchase_amount=amount,
        percent=settings.referral_percent,
    )

    return True, item.content


@router.callback_query(F.data.startswith("pay:stars:"))
async def start_stars_payment(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if callback.from_user is None:
        return

    item_id = int(callback.data.split(":")[2])
    item = await item_service.get_active_item_by_id(session, item_id)
    if item is None:
        await callback.answer("Товар недоступен.", show_alert=True)
        return

    buyer = await referral_service.get_or_create_user(session, callback.from_user.id)
    if await item_service.has_user_purchased_item(session, buyer.id, item_id):
        await callback.answer("Вы уже купили этот товар.", show_alert=True)
        return

    try:
        quote = await payment_service.build_pricing_quote(Decimal(item.price), settings)
    except Exception:
        logger.exception("Failed to build Stars quote")
        await callback.answer("Не удалось рассчитать цену для Stars. Попробуйте позже.", show_alert=True)
        return
    stars_amount = quote.stars_amount
    payload = payment_service.build_invoice_payload(
        user_telegram_id=callback.from_user.id,
        item_id=item_id,
        secret=settings.bot_token,
        quote_value=str(stars_amount),
    )
    prices = [LabeledPrice(label=item.title[:32], amount=stars_amount)]

    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=settings.stars_title[:32],
        description=f"{item.description[:170]}\n\nЦена: {Decimal(item.price):.2f} RUB (~{stars_amount} ⭐)",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",
    )
    await callback.answer("Счёт отправлен в чат.")


@router.pre_checkout_query()
async def process_pre_checkout(
    pre_checkout_query: PreCheckoutQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    payload_data = payment_service.parse_and_validate_payload(
        pre_checkout_query.invoice_payload,
        settings.bot_token,
    )
    if payload_data is None:
        await pre_checkout_query.answer(ok=False, error_message="Некорректный payload")
        return

    payload_user_id, item_id, payload_stars = payload_data
    item = await item_service.get_active_item_by_id(session, item_id)
    if item is None:
        await pre_checkout_query.answer(ok=False, error_message="Товар недоступен")
        return

    if payload_stars is None or not payload_stars.isdigit():
        await pre_checkout_query.answer(ok=False, error_message="Некорректный payload")
        return

    expected_amount = int(payload_stars)
    if (
        pre_checkout_query.from_user.id != payload_user_id
        or pre_checkout_query.currency != "XTR"
        or pre_checkout_query.total_amount != expected_amount
    ):
        await pre_checkout_query.answer(ok=False, error_message="Ошибка в параметрах оплаты")
        return

    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_stars_payment(
    message: Message,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if message.from_user is None or message.successful_payment is None:
        return

    payload_data = payment_service.parse_and_validate_payload(
        message.successful_payment.invoice_payload,
        settings.bot_token,
    )
    if payload_data is None:
        logger.warning("Invalid successful payment payload")
        await message.answer("Ошибка подтверждения оплаты. Обратитесь в поддержку.")
        return

    payload_user_id, item_id, payload_stars = payload_data
    if payload_user_id != message.from_user.id:
        logger.warning("Mismatched successful payment user")
        await message.answer("Ошибка подтверждения оплаты. Обратитесь в поддержку.")
        return

    item = await item_service.get_item_by_id(session, item_id)
    if item is None:
        await message.answer("Товар не найден.")
        return

    if payload_stars is None or not payload_stars.isdigit():
        await message.answer("Ошибка проверки payload оплаты.")
        return
    expected_amount = int(payload_stars)
    if (
        message.successful_payment.currency != "XTR"
        or message.successful_payment.total_amount != expected_amount
    ):
        logger.warning("Invalid payment amount or currency for item_id=%s", item_id)
        await message.answer("Ошибка проверки суммы оплаты.")
        return

    ok, result = await finalize_purchase(
        session=session,
        buyer_telegram_id=message.from_user.id,
        item_id=item_id,
        payment_method="stars",
        amount=Decimal(item.price),
        settings=settings,
    )
    if not ok:
        await message.answer(result)
        return

    await message.answer(
        f"✅ Оплата подтверждена!\n\nВаш контент:\n{result}",
        reply_markup=back_to_main_kb(),
    )


@router.callback_query(F.data.startswith("pay:crypto:"))
async def start_cryptobot_payment(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    item_id = int(callback.data.split(":")[2])
    item = await item_service.get_active_item_by_id(session, item_id)
    if item is None:
        await callback.answer("Товар недоступен.", show_alert=True)
        return

    buyer = await referral_service.get_or_create_user(session, callback.from_user.id)
    if await item_service.has_user_purchased_item(session, buyer.id, item_id):
        await callback.answer("Вы уже купили этот товар.", show_alert=True)
        return

    try:
        quote = await payment_service.build_pricing_quote(Decimal(item.price), settings)
    except Exception:
        logger.exception("Failed to build CryptoBot quote")
        await callback.answer("Не удалось рассчитать цену для CryptoBot. Попробуйте позже.", show_alert=True)
        return
    crypto_amount = quote.crypto_amount
    payload = payment_service.build_invoice_payload(
        user_telegram_id=callback.from_user.id,
        item_id=item_id,
        secret=settings.cryptobot_token,
        quote_value=str(crypto_amount),
    )
    client = payment_service.CryptoBotClient(settings.cryptobot_token)
    try:
        invoice = await client.create_invoice(
            amount=crypto_amount,
            asset=settings.cryptobot_asset,
            description=f"{item.title} (item_id={item.id})",
            payload=payload,
        )
    except Exception:
        logger.exception("CryptoBot create_invoice failed")
        await callback.answer("Не удалось создать счёт. Попробуйте позже.", show_alert=True)
        return

    await callback.message.edit_text(
        f"Счёт создан.\nК оплате: {crypto_amount} {settings.cryptobot_asset} (~{Decimal(item.price):.2f} RUB)\n\n"
        "Оплатите и нажмите Проверить оплату.",
        reply_markup=cryptobot_invoice_kb(invoice.pay_url, invoice.invoice_id, item.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("check_crypto:"))
async def check_cryptobot_payment(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    _, invoice_raw, item_raw = callback.data.split(":")
    invoice_id = int(invoice_raw)
    item_id = int(item_raw)

    item = await item_service.get_item_by_id(session, item_id)
    if item is None:
        await callback.answer("Товар не найден.", show_alert=True)
        return

    client = payment_service.CryptoBotClient(settings.cryptobot_token)
    try:
        invoice = await client.get_invoice(invoice_id)
    except Exception:
        logger.exception("CryptoBot get_invoice failed")
        await callback.answer("Ошибка проверки оплаты. Повторите позже.", show_alert=True)
        return
    if invoice is None:
        await callback.answer("Счёт не найден.", show_alert=True)
        return

    payload_data = payment_service.parse_and_validate_payload(invoice.payload, settings.cryptobot_token)
    if payload_data is None:
        await callback.answer("Ошибка проверки платежа.", show_alert=True)
        return

    payload_user_id, payload_item_id, payload_crypto_amount = payload_data
    if payload_user_id != callback.from_user.id or payload_item_id != item_id:
        await callback.answer("Счёт не принадлежит вам.", show_alert=True)
        return

    if payload_crypto_amount is None:
        await callback.answer("Некорректный payload счёта.", show_alert=True)
        return

    if invoice.status != "paid":
        await callback.answer("Оплата пока не подтверждена.", show_alert=True)
        return

    try:
        expected_crypto_amount = Decimal(payload_crypto_amount)
    except InvalidOperation:
        await callback.answer("Ошибка проверки суммы счёта.", show_alert=True)
        return

    if Decimal(invoice.amount) != expected_crypto_amount:
        await callback.answer("Неверная сумма в счёте.", show_alert=True)
        return

    ok, result = await finalize_purchase(
        session=session,
        buyer_telegram_id=callback.from_user.id,
        item_id=item_id,
        payment_method="cryptobot",
        amount=Decimal(item.price),
        settings=settings,
    )
    if not ok:
        await callback.answer(result, show_alert=True)
        return

    await callback.message.edit_text(
        f"✅ Оплата подтверждена!\n\nВаш контент:\n{result}",
        reply_markup=back_to_main_kb(),
    )
    await callback.answer("Товар выдан")
