from __future__ import annotations

from decimal import Decimal

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Item, Purchase


def _slice_page[T](items: list[T], page: int, page_size: int) -> tuple[list[T], int]:
    if page_size <= 0:
        page_size = 5
    total_pages = max((len(items) + page_size - 1) // page_size, 1)
    page = min(max(page, 1), total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total_pages


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


def catalog_kb(items: list[Item], page: int = 1, page_size: int = 6) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    page_items, total_pages = _slice_page(items, page, page_size)
    for item in page_items:
        builder.button(
            text=f"{item.title} - {Decimal(item.price):.2f} RUB",
            callback_data=f"item:{item.id}",
        )
    if total_pages > 1:
        if page > 1:
            builder.button(text="◀️", callback_data=f"menu:catalog:page:{page - 1}")
        builder.button(text=f"{page}/{total_pages}", callback_data="menu:catalog:noop")
        if page < total_pages:
            builder.button(text="▶️", callback_data=f"menu:catalog:page:{page + 1}")
    builder.button(text="⬅️ Назад", callback_data="menu:home")
    builder.adjust(1, 3, 1)
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
    builder.button(text="✏️ Изменить товар", callback_data="admin:edit_item_menu")
    builder.button(text="📋 Список товаров", callback_data="admin:list_items")
    builder.button(text="❌ Удалить товар", callback_data="admin:delete_item_menu")
    builder.adjust(1)
    return builder.as_markup()


def delete_items_kb(
    items: list[Item],
    *,
    scope: str,
    page: int = 1,
    page_size: int = 6,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    page_items, total_pages = _slice_page(items, page, page_size)
    for item in page_items:
        builder.button(text=f"❌ {item.title}", callback_data=f"admin:delete_item:{item.id}")
    if total_pages > 1:
        if page > 1:
            builder.button(text="◀️", callback_data=f"admin:delete_item_scope:{scope}:{page - 1}")
        builder.button(text=f"{page}/{total_pages}", callback_data="admin:noop")
        if page < total_pages:
            builder.button(text="▶️", callback_data=f"admin:delete_item_scope:{scope}:{page + 1}")
    builder.button(text="⬅️ К папкам", callback_data="admin:delete_item_menu")
    builder.adjust(1, 3, 1)
    return builder.as_markup()


def edit_items_kb(
    items: list[Item],
    *,
    scope: str,
    page: int = 1,
    page_size: int = 6,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    page_items, total_pages = _slice_page(items, page, page_size)
    for item in page_items:
        builder.button(text=f"✏️ {item.title}", callback_data=f"admin:edit_item:{item.id}")
    if total_pages > 1:
        if page > 1:
            builder.button(text="◀️", callback_data=f"admin:edit_item_scope:{scope}:{page - 1}")
        builder.button(text=f"{page}/{total_pages}", callback_data="admin:noop")
        if page < total_pages:
            builder.button(text="▶️", callback_data=f"admin:edit_item_scope:{scope}:{page + 1}")
    builder.button(text="⬅️ К папкам", callback_data="admin:edit_item_menu")
    builder.adjust(1, 3, 1)
    return builder.as_markup()


def item_form_kb(*, mode: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    prefix = "admin:create_field" if mode == "create" else "admin:edit_field"
    save_action = "admin:create_save" if mode == "create" else "admin:edit_save"

    builder.button(text="Название", callback_data=f"{prefix}:title")
    builder.button(text="Описание", callback_data=f"{prefix}:description")
    builder.button(text="Цена (RUB)", callback_data=f"{prefix}:price")
    builder.button(text="Окончание", callback_data=f"{prefix}:expires_at")
    builder.button(text="Контент", callback_data=f"{prefix}:content")
    builder.button(text="✅ Сохранить", callback_data=save_action)
    builder.button(text="❌ Отмена", callback_data="admin:form_cancel")
    builder.adjust(1)
    return builder.as_markup()


def admin_items_scope_kb(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📂 Активные", callback_data=f"admin:{action}_scope:active:1")
    builder.button(text="🗃 Архивные", callback_data=f"admin:{action}_scope:archive:1")
    builder.button(text="📦 Все", callback_data=f"admin:{action}_scope:all:1")
    builder.button(text="⬅️ Назад", callback_data="admin:back")
    builder.adjust(1)
    return builder.as_markup()


def admin_list_items_pages_kb(scope: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if total_pages > 1:
        if page > 1:
            builder.button(text="◀️", callback_data=f"admin:list_items_scope:{scope}:{page - 1}")
        builder.button(text=f"{page}/{total_pages}", callback_data="admin:noop")
        if page < total_pages:
            builder.button(text="▶️", callback_data=f"admin:list_items_scope:{scope}:{page + 1}")
    builder.button(text="⬅️ К папкам", callback_data="admin:list_items")
    builder.adjust(3, 1)
    return builder.as_markup()
