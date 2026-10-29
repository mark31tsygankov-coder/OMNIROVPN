import logging
from datetime import datetime
from typing import Union

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import BaseFilter
from database import db
from config import config
from keyboards_admin import (
    admin_panel_kb,
    admin_tariffs_kb,
    admin_tariff_detail_kb,
    admin_users_kb,
    admin_user_detail_kb,
    admin_promos_kb,
    admin_tickets_kb,
    admin_broadcast_confirm_kb,
    admin_back_kb,
)
from keyboards_main_menu import ticket_actions_kb, confirm_kb

logger = logging.getLogger(__name__)
router = Router()


class IsAdmin(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return user_id == config.ADMIN_ID


class AdminStates(StatesGroup):
    search_user = State()
    add_balance = State()
    sub_balance = State()
    create_tariff_name = State()
    create_tariff_days = State()
    create_tariff_price = State()
    create_tariff_desc = State()
    edit_tariff_value = State()
    create_promo_code = State()
    create_promo_type = State()
    create_promo_value = State()
    create_promo_uses = State()
    reply_ticket = State()
    broadcast_text = State()
    activate_sub_tariff = State()


@router.callback_query(F.data == "admin_panel", IsAdmin())
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel_denied(callback: CallbackQuery):
    await callback.answer("Доступ запрещён", show_alert=True)


@router.callback_query(F.data == "admin_stats", IsAdmin())
async def cb_admin_stats(callback: CallbackQuery):
    users_cnt = await db.get_users_count()
    active_subs = await db.get_active_subscriptions_count()
    expired_subs = await db.get_expired_subscriptions_count()
    total_payments = await db.get_total_payments()
    total_balance = await db.get_total_user_balance()
    tickets_cnt = await db.get_tickets_count()
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {users_cnt}\n"
        f"🟢 Активных подписок: {active_subs}\n"
        f"🔴 Истёкших подписок: {expired_subs}\n"
        f"💳 Сумма платежей: {total_payments:.0f} ₽\n"
        f"💰 Баланс пользователей: {total_balance:.0f} ₽\n"
        f"🎫 Тикетов: {tickets_cnt}"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_users", IsAdmin())
async def cb_admin_users(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👥 <b>Пользователи</b>\n\nНайдите пользователя по Telegram ID:",
        reply_markup=admin_users_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_search_user", IsAdmin())
async def cb_admin_search_user(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.search_user)
    await callback.message.edit_text(
        "🔍 Введите Telegram ID пользователя:",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(AdminStates.search_user, IsAdmin())
async def process_search_user(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("Введите числовой Telegram ID:")
        return
    user = await db.get_user(uid)
    if not user:
        await message.answer("Пользователь не найден.", reply_markup=admin_users_kb())
        await state.clear()
        return
    await state.clear()
    await show_user_detail(message, user)


async def show_user_detail(target, user: dict):
    sub = await db.get_active_subscription(user["telegram_id"])
    sub_text = "нет"
    if sub:
        try:
            end = datetime.fromisoformat(sub["end_date"]).strftime("%d.%m.%Y")
        except Exception:
            end = sub["end_date"]
        sub_text = f"{sub.get('tariff_name', '—')} до {end}"
    blocked = "🚫 Да" if user.get("is_blocked") else "Нет"
    text = (
        f"👤 <b>Пользователь</b>\n\n"
        f"ID: <code>{user['telegram_id']}</code>\n"
        f"Имя: {user.get('full_name') or '—'}\n"
        f"Username: @{user.get('username') or '—'}\n"
        f"Баланс: {user.get('balance', 0):.0f} ₽\n"
        f"Подписка: {sub_text}\n"
        f"Заблокирован: {blocked}\n"
        f"Регистрация: {str(user.get('created_at', ''))[:16]}"
    )
    kb = admin_user_detail_kb(user["telegram_id"], bool(user.get("is_blocked")))
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_add_balance_"), IsAdmin())
async def cb_admin_add_balance(callback: CallbackQuery, state: FSMContext):
    uid = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.add_balance)
    await state.update_data(target_user=uid)
    await callback.message.edit_text(
        f"💰 Введите сумму для начисления пользователю {uid}:",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(AdminStates.add_balance, IsAdmin())
async def process_add_balance(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("Введите число:")
        return
    data = await state.get_data()
    uid = data["target_user"]
    await db.update_balance(uid, amount, reason="admin_credit", admin_id=message.from_user.id)
    await state.clear()
    user = await db.get_user(uid)
    await message.answer(f"✅ Начислено {amount:.0f} ₽ пользователю {uid}")
    if user:
        await show_user_detail(message, user)


@router.callback_query(F.data.startswith("admin_sub_balance_"), IsAdmin())
async def cb_admin_sub_balance(callback: CallbackQuery, state: FSMContext):
    uid = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.sub_balance)
    await state.update_data(target_user=uid)
    await callback.message.edit_text(
        f"💸 Введите сумму для списания у пользователя {uid}:",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(AdminStates.sub_balance, IsAdmin())
async def process_sub_balance(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("Введите число:")
        return
    data = await state.get_data()
    uid = data["target_user"]
    await db.update_balance(uid, -abs(amount), reason="admin_debit", admin_id=message.from_user.id)
    await state.clear()
    user = await db.get_user(uid)
    await message.answer(f"✅ Списано {amount:.0f} ₽ у пользователя {uid}")
    if user:
        await show_user_detail(message, user)


@router.callback_query(F.data.startswith("admin_activate_sub_"), IsAdmin())
async def cb_admin_activate_sub(callback: CallbackQuery, state: FSMContext):
    uid = int(callback.data.split("_")[3])
    tariffs = await db.get_active_tariffs()
    if not tariffs:
        await callback.answer("Нет активных тарифов", show_alert=True)
        return
    await state.set_state(AdminStates.activate_sub_tariff)
    await state.update_data(target_user=uid)
    buttons = [
        [InlineKeyboardButton(text=f"{t['name']} ({t['duration_days']}д)", callback_data=f"admin_do_activate_{t['id']}",)]
        for t in tariffs
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users",)])
    await callback.message.edit_text(
        f"Выберите тариф для активации пользователю {uid}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_do_activate_"), IsAdmin())
async def cb_admin_do_activate(callback: CallbackQuery, state: FSMContext):
    tariff_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    uid = data.get("target_user")
    if not uid:
        await callback.answer("Ошибка", show_alert=True)
        return
    tariff = await db.get_tariff(tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    sub = await db.activate_subscription(uid, tariff, extend=False)
    await db.create_connection(
        user_id=uid,
        subscription_id=sub["id"],
        expires_at=sub["end_date"],
        config_data=f"TEST_CONFIG_FOR_USER_{uid}",
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ Подписка «{tariff['name']}» активирована для {uid}",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_extend_sub_"), IsAdmin())
async def cb_admin_extend_sub(callback: CallbackQuery, state: FSMContext):
    uid = int(callback.data.split("_")[3])
    tariffs = await db.get_active_tariffs()
    if not tariffs:
        await callback.answer("Нет тарифов", show_alert=True)
        return
    await state.update_data(target_user=uid)
    buttons = [
        [InlineKeyboardButton(text=f"{t['name']} ({t['duration_days']}д)", callback_data=f"admin_do_extend_{t['id']}",)]
        for t in tariffs
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users",)])
    await callback.message.edit_text(
        f"Выберите тариф для продления пользователю {uid}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_do_extend_"), IsAdmin())
async def cb_admin_do_extend(callback: CallbackQuery, state: FSMContext):
    tariff_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    uid = data.get("target_user")
    tariff = await db.get_tariff(tariff_id)
    if not uid or not tariff:
        await callback.answer("Ошибка", show_alert=True)
        return
    sub = await db.activate_subscription(uid, tariff, extend=True)
    await state.clear()
    await callback.message.edit_text(
        f"✅ Подписка продлена для {uid} до {sub['end_date'][:10]}",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_deactivate_sub_"), IsAdmin())
async def cb_admin_deactivate_sub(callback: CallbackQuery):
    uid = int(callback.data.split("_")[3])
    await db.deactivate_subscription(uid)
    await callback.message.edit_text(
        f"🔴 Подписка пользователя {uid} отключена",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_block_user_"), IsAdmin())
async def cb_admin_block_user(callback: CallbackQuery):
    uid = int(callback.data.split("_")[3])
    user = await db.get_user(uid)
    if not user:
        await callback.answer("Не найден", show_alert=True)
        return
    new_blocked = not bool(user.get("is_blocked"))
    await db.block_user(uid, new_blocked)
    status = "заблокирован" if new_blocked else "разблокирован"
    await callback.message.edit_text(
        f"Пользователь {uid} {status}",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_tariffs", IsAdmin())
async def cb_admin_tariffs(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    tariffs = await db.get_all_tariffs()
    await callback.message.edit_text(
        "💵 <b>Тарифы</b>\n\nВыберите тариф для редактирования:",
        reply_markup=admin_tariffs_kb(tariffs),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin_tariff_\d+$"), IsAdmin())
async def cb_admin_tariff_detail(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[2])
    tariff = await db.get_tariff(tariff_id)
    if not tariff:
        await callback.answer("Не найден", show_alert=True)
        return
    status = "активен" if tariff["is_active"] else "выключен"
    text = (
        f"💵 <b>{tariff['name']}</b>\n\n"
        f"Срок: {tariff['duration_days']} дней\n"
        f"Цена: {tariff['price']:.0f} ₽\n"
        f"Описание: {tariff.get('description') or '—'}\n"
        f"Статус: {status}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_tariff_detail_kb(tariff_id, bool(tariff["is_active"])),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_create_tariff", IsAdmin())
async def cb_admin_create_tariff(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.create_tariff_name)
    await callback.message.edit_text("Введите название тарифа:", reply_markup=admin_back_kb())
    await callback.answer()


@router.message(AdminStates.create_tariff_name, IsAdmin())
async def process_tariff_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip()[:100])
    await state.set_state(AdminStates.create_tariff_days)
    await message.answer("Введите срок в днях (число):")


@router.message(AdminStates.create_tariff_days, IsAdmin())
async def process_tariff_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное целое число:")
        return
    await state.update_data(days=days)
    await state.set_state(AdminStates.create_tariff_price)
    await message.answer("Введите цену в рублях:")


@router.message(AdminStates.create_tariff_price, IsAdmin())
async def process_tariff_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректную цену:")
        return
    await state.update_data(price=price)
    await state.set_state(AdminStates.create_tariff_desc)
    await message.answer("Введите описание (или «-» чтобы пропустить):")


@router.message(AdminStates.create_tariff_desc, IsAdmin())
async def process_tariff_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    if desc == "-":
        desc = ""
    data = await state.get_data()
    tid = await db.create_tariff(
        name=data["name"],
        duration_days=data["days"],
        price=data["price"],
        description=desc[:500],
    )
    await state.clear()
    await message.answer(f"✅ Тариф создан (ID: {tid})", reply_markup=admin_back_kb())


@router.callback_query(F.data.startswith("admin_edit_tariff_"), IsAdmin())
async def cb_admin_edit_tariff(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    field = parts[3]
    tariff_id = int(parts[4])
    await state.set_state(AdminStates.edit_tariff_value)
    await state.update_data(tariff_id=tariff_id, field=field)
    prompts = {
        "name": "Введите новое название:",
        "price": "Введите новую цену:",
        "days": "Введите новый срок в днях:",
        "desc": "Введите новое описание:",
    }
    await callback.message.edit_text(prompts.get(field, "Введите значение:"), reply_markup=admin_back_kb())
    await callback.answer()


@router.message(AdminStates.edit_tariff_value, IsAdmin())
async def process_edit_tariff(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["field"]
    tariff_id = data["tariff_id"]
    value = message.text.strip()
    kwargs = {}
    try:
        if field == "name":
            kwargs["name"] = value[:100]
        elif field == "price":
            kwargs["price"] = float(value.replace(",", "."))
        elif field == "days":
            kwargs["duration_days"] = int(value)
        elif field == "desc":
            kwargs["description"] = value[:500]
    except ValueError:
        await message.answer("Некорректное значение. Попробуйте снова:")
        return
    await db.update_tariff(tariff_id, **kwargs)
    await state.clear()
    await message.answer("✅ Обновлено", reply_markup=admin_back_kb())


@router.callback_query(F.data.startswith("admin_toggle_tariff_"), IsAdmin())
async def cb_admin_toggle_tariff(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[3])
    tariff = await db.get_tariff(tariff_id)
    if not tariff:
        await callback.answer("Не найден", show_alert=True)
        return
    new_active = 0 if tariff["is_active"] else 1
    await db.update_tariff(tariff_id, is_active=new_active)
    status = "включён" if new_active else "выключен"
    await callback.answer(f"Тариф {status}")
    tariff = await db.get_tariff(tariff_id)
    status_text = "активен" if tariff["is_active"] else "выключен"
    text = (
        f"💵 <b>{tariff['name']}</b>\n\n"
        f"Срок: {tariff['duration_days']} дней\n"
        f"Цена: {tariff['price']:.0f} ₽\n"
        f"Описание: {tariff.get('description') or '—'}\n"
        f"Статус: {status_text}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_tariff_detail_kb(tariff_id, bool(tariff["is_active"])),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("admin_delete_tariff_"), IsAdmin())
async def cb_admin_delete_tariff(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[3])
    await callback.message.edit_text(
        f"Вы действительно хотите удалить тариф #{tariff_id}?",
        reply_markup=confirm_kb(f"admin_confirm_delete_tariff_{tariff_id}", "admin_tariffs"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_delete_tariff_"), IsAdmin())
async def cb_admin_confirm_delete_tariff(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[4])
    await db.delete_tariff(tariff_id)
    await callback.message.edit_text(f"🗑 Тариф #{tariff_id} удалён", reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_promos", IsAdmin())
async def cb_admin_promos(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    promos = await db.get_all_promos()
    await callback.message.edit_text(
        "🎟 <b>Промокоды</b>",
        reply_markup=admin_promos_kb(promos),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_create_promo", IsAdmin())
async def cb_admin_create_promo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.create_promo_code)
    await callback.message.edit_text(
        "Введите код промокода (латиница/цифры):",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(AdminStates.create_promo_code, IsAdmin())
async def process_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    if not code or len(code) > 32:
        await message.answer("Некорректный код. Попробуйте снова:")
        return
    await state.update_data(code=code)
    await state.set_state(AdminStates.create_promo_type)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Процент (%)", callback_data="promo_type_percent",)],
        [InlineKeyboardButton(text="Фикс. сумма (₽)", callback_data="promo_type_fixed",)],
        [InlineKeyboardButton(text="Доп. дни", callback_data="promo_type_days",)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_promos",)],
    ])
    await message.answer("Выберите тип скидки:", reply_markup=kb)


@router.callback_query(F.data.startswith("promo_type_"), IsAdmin())
async def cb_promo_type(callback: CallbackQuery, state: FSMContext):
    ptype = callback.data.replace("promo_type_", "")
    await state.update_data(discount_type=ptype)
    await state.set_state(AdminStates.create_promo_value)
    labels = {
        "percent": "процент скидки (например 10)",
        "fixed": "сумму скидки в ₽",
        "days": "количество доп. дней",
    }
    await callback.message.edit_text(f"Введите {labels.get(ptype, 'значение')}:")
    await callback.answer()


@router.message(AdminStates.create_promo_value, IsAdmin())
async def process_promo_value(message: Message, state: FSMContext):
    try:
        value = float(message.text.strip().replace(",", "."))
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число:")
        return
    await state.update_data(discount_value=value)
    await state.set_state(AdminStates.create_promo_uses)
    await message.answer("Макс. использований (0 = безлимит):")


@router.message(AdminStates.create_promo_uses, IsAdmin())
async def process_promo_uses(message: Message, state: FSMContext):
    try:
        uses = int(message.text.strip())
        if uses < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое число ≥ 0:")
        return
    data = await state.get_data()
    pid = await db.create_promo(
        code=data["code"],
        discount_type=data["discount_type"],
        discount_value=data["discount_value"],
        max_uses=uses,
    )
    await state.clear()
    await message.answer(
        f"✅ Промокод {data['code']} создан (ID: {pid})",
        reply_markup=admin_back_kb(),
    )


@router.callback_query(F.data.regexp(r"^admin_promo_\d+$"), IsAdmin())
async def cb_admin_promo_detail(callback: CallbackQuery):
    promo_id = int(callback.data.split("_")[2])
    promos = await db.get_all_promos()
    promo = next((p for p in promos if p["id"] == promo_id), None)
    if not promo:
        await callback.answer("Не найден", show_alert=True)
        return
    text = (
        f"🎟 <b>{promo['code']}</b>\n\n"
        f"Тип: {promo['discount_type']}\n"
        f"Значение: {promo['discount_value']}\n"
        f"Использовано: {promo['used_count']} / {promo['max_uses'] or '∞'}\n"
        f"Активен: {'да' if promo['is_active'] else 'нет'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 Деактивировать",
            callback_data=f"admin_deactivate_promo_{promo_id}",)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_promos",)],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_deactivate_promo_"), IsAdmin())
async def cb_admin_deactivate_promo(callback: CallbackQuery):
    promo_id = int(callback.data.split("_")[3])
    await db.deactivate_promo(promo_id)
    await callback.message.edit_text("Промокод деактивирован", reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_tickets", IsAdmin())
async def cb_admin_tickets(callback: CallbackQuery):
    tickets = await db.get_all_tickets()
    text = "🎫 <b>Тикеты</b>"
    if not tickets:
        text += "\n\nТикетов пока нет."
    await callback.message.edit_text(
        text,
        reply_markup=admin_tickets_kb(tickets),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin_ticket_\d+$"), IsAdmin())
async def cb_admin_view_ticket(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[2])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Не найден", show_alert=True)
        return
    messages = await db.get_ticket_messages(ticket_id)
    status_map = {"open": "🟡 Открыт", "answered": "🟢 Отвечен", "closed": "⚪️ Закрыт"}
    text = (
        f"🎫 <b>Тикет #{ticket_id}</b>\n"
        f"Пользователь: {ticket['user_id']}\n"
        f"Статус: {status_map.get(ticket['status'], ticket['status'])}\n"
        f"Тема: {ticket.get('subject', '—')}\n\n"
    )
    for m in messages[-15:]:
        who = "👨‍💼 Админ" if m["is_admin"] else "👤 User"
        text += f"{who}: {m['message'][:300]}\n\n"
    await callback.message.edit_text(
        text,
        reply_markup=ticket_actions_kb(ticket_id, is_admin=True),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_reply_ticket_"), IsAdmin())
async def cb_admin_reply_ticket(callback: CallbackQuery, state: FSMContext):
    ticket_id = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.reply_ticket)
    await state.update_data(ticket_id=ticket_id)
    await callback.message.edit_text(
        f"💬 Введите ответ на тикет #{ticket_id}:",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(AdminStates.reply_ticket, IsAdmin())
async def process_admin_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    text = message.text.strip()
    if not ticket_id or not text:
        await state.clear()
        return
    await db.add_ticket_message(
        ticket_id=ticket_id,
        sender_id=message.from_user.id,
        message=text,
        is_admin=True,
    )
    ticket = await db.get_ticket(ticket_id)
    await state.clear()
    if ticket:
        try:
            await message.bot.send_message(
                ticket["user_id"],
                f"💬 Ответ по тикету #{ticket_id}:\n\n{text}",
            )
        except Exception as e:
            logger.error("Failed to notify user about ticket reply: %s", e)
    await message.answer(
        f"✅ Ответ отправлен в тикет #{ticket_id}",
        reply_markup=admin_back_kb(),
    )


@router.callback_query(F.data.startswith("admin_close_ticket_"), IsAdmin())
async def cb_admin_close_ticket(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[3])
    await db.close_ticket(ticket_id)
    ticket = await db.get_ticket(ticket_id)
    if ticket:
        try:
            await callback.bot.send_message(
                ticket["user_id"],
                f"🔒 Тикет #{ticket_id} закрыт администратором.",
            )
        except Exception:
            pass
    await callback.message.edit_text(
        f"Тикет #{ticket_id} закрыт",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_ticket_"), IsAdmin())
async def cb_admin_delete_ticket(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[3])
    await callback.message.edit_text(
        f"Удалить тикет #{ticket_id}?",
        reply_markup=confirm_kb(f"admin_confirm_delete_ticket_{ticket_id}", "admin_tickets"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_delete_ticket_"), IsAdmin())
async def cb_admin_confirm_delete_ticket(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[4])
    await db.delete_ticket(ticket_id)
    await callback.message.edit_text(
        f"🗑 Тикет #{ticket_id} удалён",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast", IsAdmin())
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.edit_text(
        "📢 Введите текст рассылки:",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(AdminStates.broadcast_text, IsAdmin())
async def process_broadcast_text(message: Message, state: FSMContext):
    text = message.text
    if not text:
        await message.answer("Текст не может быть пустым.")
        return
    await state.update_data(broadcast_text=text)
    await message.answer(
        f"Вы уверены, что хотите отправить рассылку?\n\n{text[:500]}",
        reply_markup=admin_broadcast_confirm_kb(),
    )


@router.callback_query(F.data == "admin_broadcast_send", IsAdmin())
async def cb_admin_broadcast_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await callback.answer("Нет текста", show_alert=True)
        return
    users = await db.get_all_users()
    broadcast_id = await db.create_broadcast(callback.from_user.id, text)
    success = 0
    failed = 0
    for u in users:
        if u.get("is_blocked"):
            continue
        try:
            await callback.bot.send_message(u["telegram_id"], text)
            success += 1
        except Exception:
            failed += 1
    total = success + failed
    await db.update_broadcast_stats(broadcast_id, total, success, failed)
    await state.clear()
    await callback.message.edit_text(
        f"📢 Рассылка завершена\n\nВсего: {total}\nУспешно: {success}\nОшибки: {failed}",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_subs", IsAdmin())
async def cb_admin_subs(callback: CallbackQuery):
    active = await db.get_active_subscriptions_count()
    expired = await db.get_expired_subscriptions_count()
    text = (
        f"📦 <b>Подписки</b>\n\n"
        f"Активных: {active}\n"
        f"Истёкших: {expired}\n\n"
        f"Управление подписками — через раздел «Пользователи»."
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_payments", IsAdmin())
async def cb_admin_payments(callback: CallbackQuery):
    total = await db.get_total_payments()
    text = (
        f"💳 <b>Платежи</b>\n\n"
        f"Общая сумма оплаченных заказов: {total:.0f} ₽\n\n"
        f"<i>Детальная история будет доступна после подключения платёжной системы.</i>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_balances", IsAdmin())
async def cb_admin_balances(callback: CallbackQuery):
    total = await db.get_total_user_balance()
    text = (
        f"💰 <b>Балансы</b>\n\n"
        f"Суммарный баланс пользователей: {total:.0f} ₽\n\n"
        f"Начисление/списание — через раздел «Пользователи»."
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_connections", IsAdmin())
async def cb_admin_connections(callback: CallbackQuery):
    text = (
        "🔑 <b>Подключения</b>\n\n"
        "В тестовом режиме подключения создаются автоматически "
        "при активации подписки."
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_h1cloud", IsAdmin())
async def cb_admin_h1cloud(callback: CallbackQuery):
    from h1cloud import h1cloud_client
    resources = await h1cloud_client.get_resources()
    text = (
        "🖥 <b>H1Cloud</b>\n\n"
        "Адаптер готов. Реальный API ещё не подключён.\n"
        f"Токен: {'установлен' if config.H1CLOUD_API_TOKEN else 'не задан'}\n"
        f"Ресурсов (stub): {len(resources)}"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_settings", IsAdmin())
async def cb_admin_settings(callback: CallbackQuery):
    text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"TEST_MODE: {'✅ вкл' if config.TEST_MODE else '❌ выкл'}\n"
        f"ADMIN_ID: <code>{config.ADMIN_ID}</code>\n"
        f"H1Cloud token: {'задан' if config.H1CLOUD_API_TOKEN else 'не задан'}"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()
