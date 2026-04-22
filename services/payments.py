from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import aiohttp


CRYPTOBOT_API_BASE = "https://pay.crypt.bot/api"


@dataclass(slots=True)
class CryptoInvoice:
    invoice_id: int
    pay_url: str
    amount: Decimal
    status: str
    payload: str


def to_stars_amount(value: Decimal) -> int:
    rounded = value.quantize(Decimal("1"))
    if rounded <= 0:
        raise ValueError("Item price must be positive for Telegram Stars")
    return int(rounded)


def build_invoice_payload(user_telegram_id: int, item_id: int, secret: str) -> str:
    raw = f"{user_telegram_id}:{item_id}"
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{raw}:{signature}"


def parse_and_validate_payload(payload: str, secret: str) -> tuple[int, int] | None:
    parts = payload.split(":")
    if len(parts) != 3:
        return None

    user_id, item_id, signature = parts
    raw = f"{user_id}:{item_id}"
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        return int(user_id), int(item_id)
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
