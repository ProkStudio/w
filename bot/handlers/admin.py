from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import admin_menu_kb, delete_items_kb, edit_items_kb, item_form_kb
from config import Settings
from services import items as item_service

router = Router(name="admin")
AUTHORIZED_ADMINS: set[int] = set()


class AdminAuthState(StatesGroup):
    waiting_password = State()


class ItemFormState(StatesGroup):
    waiting_value = State()


def is_admin(user_id: int, settings: Settings) -> bool:
    return user_id == settings.admin_id


def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_ADMINS


def _format_form_preview(data: dict[str, str | None], *, mode: str) -> str:
    title = data.get("title") or "None"
    description = data.get("description") or "None"
    price = data.get("price") or "None"
    expires_at = data.get("expires_at") or "None"
    content = data.get("content") or "None"
    action = "Создание товара" if mode == "create" else "Редактирование товара"
    return (
        f"{action}\n\n"
        f"Название - {title}\n"
        f"Описание - {description}\n"
        f"Цена (RUB) - {price}\n"
        f"Окончание (UTC) - {expires_at}\n"
        f"Контент - {content}\n\n"
        "Нажми на поле, чтобы заполнить/изменить."
    )


def _all_fields_filled(data: dict[str, str | None]) -> bool:
    return all(data.get(key) for key in ("title", "description", "price", "expires_at", "content"))


async def _show_form(message: Message, state: FSMContext, *, mode: str) -> None:
    data = await state.get_data()
    await message.answer(
        _format_form_preview(data, mode=mode),
        reply_markup=item_form_kb(mode=mode),
    )


async def _show_form_callback(callback: CallbackQuery, state: FSMContext, *, mode: str) -> None:
    if callback.message is None:
        return
    data = await state.get_data()
    await callback.message.edit_text(
        _format_form_preview(data, mode=mode),
        reply_markup=item_form_kb(mode=mode),
    )


@router.message(Command("admin"))
async def admin_command(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    if message.from_user is None or not is_admin(message.from_user.id, settings):
        await message.answer("Недостаточно прав.")
        return

    if not is_authorized(message.from_user.id):
        await state.set_state(AdminAuthState.waiting_password)
        await message.answer("Введите пароль администратора:")
        return

    await message.answer("Админ-панель:", reply_markup=admin_menu_kb())


@router.message(AdminAuthState.waiting_password)
async def admin_password_check(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None or not is_admin(message.from_user.id, settings):
        await state.clear()
        await message.answer("Недостаточно прав.")
        return
    if not message.text:
        await message.answer("Введите пароль текстом.")
        return
    if message.text.strip() != settings.admin_password:
        await message.answer("Неверный пароль.")
        return

    AUTHORIZED_ADMINS.add(message.from_user.id)
    await state.clear()
    await message.answer("Пароль принят. Админ-панель:", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:back")
async def admin_back(callback: CallbackQuery, settings: Settings) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
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
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    await state.set_data(
        {
            "mode": "create",
            "edit_item_id": None,
            "title": None,
            "description": None,
            "price": None,
            "expires_at": None,
            "content": None,
            "current_field": None,
        }
    )
    await _show_form_callback(callback, state, mode="create")
    await callback.answer()


@router.callback_query(F.data.in_({"admin:create_field:title", "admin:create_field:description", "admin:create_field:price", "admin:create_field:expires_at", "admin:create_field:content"}))
@router.callback_query(F.data.in_({"admin:edit_field:title", "admin:edit_field:description", "admin:edit_field:price", "admin:edit_field:expires_at", "admin:edit_field:content"}))
async def admin_item_form_field(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    field = callback.data.split(":")[-1]
    labels = {
        "title": "Введите название товара:",
        "description": "Введите описание:",
        "price": "Введите цену в RUB (например 990 или 1290.50):",
        "expires_at": 'Введите дату окончания в формате "YYYY-MM-DD HH:MM" (UTC):',
        "content": "Введите контент, который получит покупатель:",
    }
    await state.update_data(current_field=field)
    await state.set_state(ItemFormState.waiting_value)
    await callback.message.answer(labels[field])
    await callback.answer()


@router.message(ItemFormState.waiting_value)
async def admin_item_form_value(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    if message.from_user is None or not is_admin(message.from_user.id, settings) or not is_authorized(message.from_user.id):
        await state.clear()
        await message.answer("Недостаточно прав.")
        return

    if not message.text:
        await message.answer("Нужно отправить текст.")
        return

    data = await state.get_data()
    field = data.get("current_field")
    mode = data.get("mode", "create")
    if field not in {"title", "description", "price", "expires_at", "content"}:
        await state.clear()
        await message.answer("Сессия формы сброшена. Откройте заново через /admin.")
        return

    value = message.text.strip()
    if field == "price":
        raw = value.replace(",", ".")
        try:
            price = Decimal(raw)
        except InvalidOperation:
            await message.answer("Неверная цена. Пример: 1290.50")
            return
        if price <= 0:
            await message.answer("Цена должна быть больше нуля.")
            return
        value = str(price.quantize(Decimal("0.01")))
    elif field == "expires_at":
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            await message.answer('Неверный формат. Используйте "YYYY-MM-DD HH:MM"')
            return
        if dt <= datetime.now(timezone.utc):
            await message.answer("Время окончания должно быть в будущем.")
            return
        value = dt.strftime("%Y-%m-%d %H:%M")

    await state.update_data(**{field: value, "current_field": None})
    await state.set_state(None)
    await _show_form(message, state, mode=str(mode))


@router.callback_query(F.data == "admin:create_save")
async def admin_create_item_save(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    data = await state.get_data()
    if not _all_fields_filled(data):
        await callback.answer("Заполните все поля перед сохранением.", show_alert=True)
        return

    expires_at = datetime.strptime(str(data["expires_at"]), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    item = await item_service.create_item(
        session,
        title=str(data["title"]),
        description=str(data["description"]),
        price=Decimal(str(data["price"])),
        expires_at=expires_at,
        content=str(data["content"]),
    )
    await state.clear()
    await callback.message.edit_text(
        f"Товар создан: #{item.id} {item.title}",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer("Сохранено")


@router.callback_query(F.data == "admin:edit_item_menu")
async def admin_edit_item_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    all_items = await item_service.get_all_items(session)
    if not all_items:
        await callback.message.edit_text("Нет товаров для редактирования.", reply_markup=admin_menu_kb())
        await callback.answer()
        return
    await callback.message.edit_text(
        "Выберите товар для редактирования:",
        reply_markup=edit_items_kb(all_items),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:edit_item:"))
async def admin_edit_item_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    item_id = int(callback.data.split(":")[-1])
    item = await item_service.get_item_by_id(session, item_id)
    if item is None:
        await callback.answer("Товар не найден.", show_alert=True)
        return
    await state.set_data(
        {
            "mode": "edit",
            "edit_item_id": item.id,
            "title": item.title,
            "description": item.description,
            "price": str(Decimal(item.price).quantize(Decimal("0.01"))),
            "expires_at": item.expires_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "content": item.content,
            "current_field": None,
        }
    )
    await _show_form_callback(callback, state, mode="edit")
    await callback.answer()


@router.callback_query(F.data == "admin:edit_save")
async def admin_edit_item_save(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    data = await state.get_data()
    if not _all_fields_filled(data):
        await callback.answer("Заполните все поля перед сохранением.", show_alert=True)
        return
    edit_item_id = data.get("edit_item_id")
    if edit_item_id is None:
        await callback.answer("Не выбран товар для редактирования.", show_alert=True)
        return
    item = await item_service.get_item_by_id(session, int(edit_item_id))
    if item is None:
        await callback.answer("Товар не найден.", show_alert=True)
        return
    expires_at = datetime.strptime(str(data["expires_at"]), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    updated = await item_service.update_item(
        session,
        item=item,
        title=str(data["title"]),
        description=str(data["description"]),
        price=Decimal(str(data["price"])),
        expires_at=expires_at,
        content=str(data["content"]),
    )
    await state.clear()
    await callback.message.edit_text(
        f"Товар обновлён: #{updated.id} {updated.title}",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer("Изменения сохранены")


@router.callback_query(F.data == "admin:form_cancel")
async def admin_form_cancel(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("Админ-панель:", reply_markup=admin_menu_kb())
    await callback.answer("Отменено")


@router.callback_query(F.data == "admin:list_items")
async def admin_list_items(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
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
            f"#{item.id} | {item.title} | {Decimal(item.price):.2f} RUB | {item.expires_at.strftime('%Y-%m-%d %H:%M')} UTC | {status}"
        )

    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:delete_item_menu")
async def admin_delete_item_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
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
    if (
        callback.message is None
        or not is_admin(callback.from_user.id, settings)
        or not is_authorized(callback.from_user.id)
    ):
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
