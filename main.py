from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ErrorEvent

from bot.handlers.admin import router as admin_router
from bot.handlers.payments import router as payments_router
from bot.handlers.user import router as user_router
from bot.middlewares.db import DbSessionMiddleware
from config import Settings, load_settings
from database import db


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def on_error(event: ErrorEvent) -> None:
    logging.exception("Unhandled update error: %s", event.exception)


def create_dispatcher(settings: Settings) -> Dispatcher:
    if db.SessionLocal is None:
        raise RuntimeError("SessionLocal is not initialized")

    dp = Dispatcher()
    dp.errors.register(on_error)
    dp.update.middleware(DbSessionMiddleware(db.SessionLocal))

    dp["settings"] = settings
    dp.include_router(user_router)
    dp.include_router(payments_router)
    dp.include_router(admin_router)
    return dp


async def run() -> None:
    settings = load_settings()
    db.init_db(settings.database_url)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = create_dispatcher(settings)
    await dp.start_polling(bot)


if __name__ == "__main__":
    configure_logging()
    asyncio.run(run())
