from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import admin_menu_kb, delete_items_kb
from config import Settings
from services import items as item_service

router = Router(name="admin")


class AddItemStates(StatesGroup):
    title = State()
    description = State()
    price = State()
    expires_at = State()
    content = State()


def is_admin(user_id: int, settings: Settings) -> bool:
    return user_id == settings.admin_id


@router.message(Command("admin"))
async def admin_command(
    message: Message,
    settings: Settings,
) -> None:
    if message.from_user is None or not is_admin(message.from_user.id, settings):
        await message.answer("Недостаточно прав.")
        return

    await message.answer("Админ-панель:", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:back")
async def admin_back(callback: CallbackQuery, settings: Settings) -> None:
    if callback.message is None or not is_admin(callback.from_user.id, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    await callback.message.edit_text("Админ-панель:", reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:add_item")
async def admin_add_item_start(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    if callback.message is None or not is_admin(callback.from_user.id, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AddItemStates.title)
    await callback.message.answer("Введите название товара:")
    await callback.answer()


@router.message(AddItemStates.title)
async def admin_add_item_title(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(AddItemStates.description)
    await message.answer("Введите описание товара:")


@router.message(AddItemStates.description)
async def admin_add_item_description(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(AddItemStates.price)
    await message.answer("Введите цену (например 10 или 10.50):")


@router.message(AddItemStates.price)
async def admin_add_item_price(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    raw = message.text.replace(",", ".").strip()
    try:
        price = Decimal(raw)
    except InvalidOperation:
        await message.answer("Неверная цена. Введите число, например: 10.50")
        return

    if price <= 0:
        await message.answer("Цена должна быть больше нуля.")
        return

    await state.update_data(price=str(price.quantize(Decimal("0.01"))))
    await state.set_state(AddItemStates.expires_at)
    await message.answer('Введите expires_at в формате "2026-04-30 18:00" (UTC):')


@router.message(AddItemStates.expires_at)
async def admin_add_item_expires_at(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    try:
        dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        await message.answer('Неверный формат. Используйте "YYYY-MM-DD HH:MM"')
        return

    if dt <= datetime.now(timezone.utc):
        await message.answer("Время окончания должно быть в будущем.")
        return

    await state.update_data(expires_at=dt.isoformat())
    await state.set_state(AddItemStates.content)
    await message.answer("Введите контент, который получит покупатель:")


@router.message(AddItemStates.content)
async def admin_add_item_content(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if not message.text:
        return

    data = await state.get_data()
    title = data["title"]
    description = data["description"]
    price = Decimal(data["price"])
    expires_at = datetime.fromisoformat(data["expires_at"])
    content = message.text.strip()

    item = await item_service.create_item(
        session,
        title=title,
        description=description,
        price=price,
        expires_at=expires_at,
        content=content,
    )

    await state.clear()
    await message.answer(
        f"Товар создан: #{item.id} {item.title}",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "admin:list_items")
async def admin_list_items(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if callback.message is None or not is_admin(callback.from_user.id, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    all_items = await item_service.get_all_items(session)
    if not all_items:
        await callback.message.edit_text("Список товаров пуст.", reply_markup=admin_menu_kb())
        await callback.answer()
        return

    now = datetime.now(timezone.utc)
    lines = ["📋 Товары:"]
    for item in all_items:
        status = "активен" if item.expires_at > now else "истёк"
        lines.append(
            f"#{item.id} | {item.title} | {item.price} | {item.expires_at.strftime('%Y-%m-%d %H:%M')} UTC | {status}"
        )

    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:delete_item_menu")
async def admin_delete_item_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if callback.message is None or not is_admin(callback.from_user.id, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    all_items = await item_service.get_all_items(session)
    if not all_items:
        await callback.message.edit_text("Нет товаров для удаления.", reply_markup=admin_menu_kb())
        await callback.answer()
        return

    await callback.message.edit_text(
        "Выберите товар для удаления:",
        reply_markup=delete_items_kb(all_items),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:delete_item:"))
async def admin_delete_item(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if callback.message is None or not is_admin(callback.from_user.id, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    item_id = int(callback.data.split(":")[-1])
    deleted = await item_service.delete_item_by_id(session, item_id)
    if not deleted:
        await callback.answer("Товар не найден.", show_alert=True)
        return

    await callback.message.edit_text(
        f"Товар #{item_id} удалён.",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer("Удалено")
