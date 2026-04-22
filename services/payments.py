from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Any

import aiohttp

from config import Settings


CRYPTOBOT_API_BASE = "https://pay.crypt.bot/api"
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CryptoInvoice:
    invoice_id: int
    pay_url: str
    amount: Decimal
    status: str
    payload: str


@dataclass(slots=True)
class PricingQuote:
    price_rub: Decimal
    usd_rub: Decimal
    stars_amount: int
    crypto_amount: Decimal


class RubRateProvider:
    def __init__(self) -> None:
        self._cached_usd_rub: Decimal | None = None
        self._expires_at: datetime | None = None

    async def get_usd_rub(self, *, fallback: Decimal, ttl_sec: int) -> Decimal:
        now = datetime.now(timezone.utc)
        if self._cached_usd_rub is not None and self._expires_at is not None and now < self._expires_at:
            return self._cached_usd_rub

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://open.er-api.com/v6/latest/USD", timeout=15) as response:
                    data = await response.json()
                    rate = Decimal(str(data["rates"]["RUB"]))
                    if rate <= 0:
                        raise ValueError("USD/RUB rate must be positive")
                    self._cached_usd_rub = rate
                    self._expires_at = now + timedelta(seconds=max(ttl_sec, 60))
                    return rate
        except Exception:
            logger.exception("Failed to fetch USD/RUB rate, using fallback")
            self._cached_usd_rub = fallback
            self._expires_at = now + timedelta(seconds=max(ttl_sec, 60))
            return fallback


rate_provider = RubRateProvider()


def _to_stars_from_rub(price_rub: Decimal, usd_rub: Decimal, usd_per_star: Decimal) -> int:
    if price_rub <= 0:
        raise ValueError("Item price must be positive")
    if usd_rub <= 0 or usd_per_star <= 0:
        raise ValueError("Rates must be positive")

    stars = (price_rub / usd_rub / usd_per_star).quantize(Decimal("1"), rounding=ROUND_CEILING)
    return max(int(stars), 1)


def _to_crypto_amount_from_rub(price_rub: Decimal, usd_rub: Decimal) -> Decimal:
    if price_rub <= 0:
        raise ValueError("Item price must be positive")
    if usd_rub <= 0:
        raise ValueError("USD/RUB rate must be positive")
    return (price_rub / usd_rub).quantize(Decimal("0.01"), rounding=ROUND_CEILING)


async def build_pricing_quote(price_rub: Decimal, settings: Settings) -> PricingQuote:
    usd_rub = await rate_provider.get_usd_rub(
        fallback=settings.usd_rub_fallback,
        ttl_sec=settings.rate_cache_ttl_sec,
    )
    stars_amount = _to_stars_from_rub(price_rub, usd_rub, settings.usd_per_star)
    crypto_amount = _to_crypto_amount_from_rub(price_rub, usd_rub)
    return PricingQuote(
        price_rub=price_rub,
        usd_rub=usd_rub,
        stars_amount=stars_amount,
        crypto_amount=crypto_amount,
    )


def build_invoice_payload(
    user_telegram_id: int,
    item_id: int,
    secret: str,
    quote_value: str | None = None,
) -> str:
    raw = f"{user_telegram_id}:{item_id}" if quote_value is None else f"{user_telegram_id}:{item_id}:{quote_value}"
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{raw}:{signature}"


def parse_and_validate_payload(payload: str, secret: str) -> tuple[int, int, str | None] | None:
    parts = payload.split(":")
    if len(parts) not in (3, 4):
        return None

    if len(parts) == 3:
        user_id, item_id, signature = parts
        quote_value = None
        raw = f"{user_id}:{item_id}"
    else:
        user_id, item_id, quote_value, signature = parts
        raw = f"{user_id}:{item_id}:{quote_value}"

    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        return int(user_id), int(item_id), quote_value
    except ValueError:
        return None


class CryptoBotClient:
    def __init__(self, token: str) -> None:
        self.token = token

    async def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Crypto-Pay-API-Token": self.token}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CRYPTOBOT_API_BASE}/{method}",
                json=payload,
                headers=headers,
                timeout=20,
            ) as response:
                data = await response.json()
                if not data.get("ok"):
                    raise RuntimeError(
                        f"CryptoBot API error ({method}): {data.get('error', 'unknown')}"
                    )
                return data["result"]

    async def create_invoice(
        self,
        *,
        amount: Decimal,
        asset: str,
        description: str,
        payload: str,
    ) -> CryptoInvoice:
        result = await self._request(
            "createInvoice",
            {
                "asset": asset,
                "amount": str(amount),
                "description": description[:1000],
                "payload": payload[:256],
                "allow_comments": False,
                "allow_anonymous": False,
            },
        )
        return CryptoInvoice(
            invoice_id=result["invoice_id"],
            pay_url=result["pay_url"],
            amount=Decimal(str(result["amount"])),
            status=result["status"],
            payload=result.get("payload", ""),
        )

    async def get_invoice(self, invoice_id: int) -> CryptoInvoice | None:
        result = await self._request("getInvoices", {"invoice_ids": str(invoice_id)})
        items = result.get("items", [])
        if not items:
            return None

        item = items[0]
        return CryptoInvoice(
            invoice_id=item["invoice_id"],
            pay_url=item["pay_url"],
            amount=Decimal(str(item["amount"])),
            status=item["status"],
            payload=item.get("payload", ""),
        )
