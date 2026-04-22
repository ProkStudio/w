from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    database_url: str
    admin_id: int
    admin_password: str
    cryptobot_token: str
    cryptobot_asset: str
    referral_percent: Decimal
    stars_title: str
    usd_rub_fallback: Decimal
    usd_per_star: Decimal
    rate_cache_ttl_sec: int


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    admin_id_raw = os.getenv("ADMIN_ID", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "grihaeblan228").strip()
    cryptobot_token = os.getenv("CRYPTOBOT_TOKEN", "").strip()
    cryptobot_asset = os.getenv("CRYPTOBOT_ASSET", "USDT").strip()
    referral_percent_raw = os.getenv("REFERRAL_PERCENT", "10").strip()
    stars_title = os.getenv("STARS_TITLE", "Покупка цифрового товара").strip()
    usd_rub_fallback_raw = os.getenv("USD_RUB_FALLBACK", "95").strip()
    usd_per_star_raw = os.getenv("USD_PER_STAR", "0.013").strip()
    rate_cache_ttl_sec_raw = os.getenv("RATE_CACHE_TTL_SEC", "600").strip()

    if not bot_token:
        raise ValueError("BOT_TOKEN is required")
    if not database_url:
        raise ValueError("DATABASE_URL is required")
    if not admin_id_raw:
        raise ValueError("ADMIN_ID is required")
    if not admin_password:
        raise ValueError("ADMIN_PASSWORD is required")
    if not cryptobot_token:
        raise ValueError("CRYPTOBOT_TOKEN is required")

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        admin_id=int(admin_id_raw),
        admin_password=admin_password,
        cryptobot_token=cryptobot_token,
        cryptobot_asset=cryptobot_asset,
        referral_percent=Decimal(referral_percent_raw),
        stars_title=stars_title,
        usd_rub_fallback=Decimal(usd_rub_fallback_raw),
        usd_per_star=Decimal(usd_per_star_raw),
        rate_cache_ttl_sec=int(rate_cache_ttl_sec_raw),
    )
