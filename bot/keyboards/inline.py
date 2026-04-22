from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Item, Purchase


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍 Каталог", callback_data="menu:catalog")
    builder.button(text="👤 Профиль", callback_data="menu:profile")
    builder.button(text="📦 Мои покупки", callback_data="menu:purchases")
    builder.button(text="ℹ️ Поддержка", callback_data="menu:support")
    builder.adjust(1)
    return builder.as_markup()


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu:home")]]
    )


def catalog_kb(items: list[Item]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=f"{item.title} - {item.price}", callback_data=f"item:{item.id}")
    builder.button(text="⬅️ Назад", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def item_card_kb(item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Купить", callback_data=f"buy:{item_id}")
    builder.button(text="⬅️ Назад", callback_data="menu:catalog")
    builder.adjust(1)
    return builder.as_markup()


def buy_methods_kb(item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Telegram Stars", callback_data=f"pay:stars:{item_id}")
    builder.button(text="🪙 CryptoBot", callback_data=f"pay:crypto:{item_id}")
    builder.button(text="⬅️ Назад", callback_data=f"item:{item_id}")
    builder.adjust(1)
    return builder.as_markup()


def cryptobot_invoice_kb(pay_url: str, invoice_id: int, item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить в CryptoBot", url=pay_url)
    builder.button(text="Проверить оплату", callback_data=f"check_crypto:{invoice_id}:{item_id}")
    builder.button(text="⬅️ Назад", callback_data=f"item:{item_id}")
    builder.adjust(1)
    return builder.as_markup()


def my_purchases_kb(purchases: list[Purchase]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for purchase in purchases:
        title = purchase.item.title if purchase.item else f"Товар #{purchase.item_id}"
        builder.button(text=title, callback_data=f"purchase:{purchase.item_id}")
    builder.button(text="⬅️ Назад", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить товар", callback_data="admin:add_item")
    builder.button(text="📋 Список товаров", callback_data="admin:list_items")
    builder.button(text="❌ Удалить товар", callback_data="admin:delete_item_menu")
    builder.adjust(1)
    return builder.as_markup()


def delete_items_kb(items: list[Item]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=f"❌ {item.title}", callback_data=f"admin:delete_item:{item.id}")
    builder.button(text="⬅️ Назад", callback_data="admin:back")
    builder.adjust(1)
    return builder.as_markup()
