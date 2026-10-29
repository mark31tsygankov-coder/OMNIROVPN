import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import db
from config import config
from payment import payment_service
from keyboards_main_menu import (
    tariffs_kb,
    tariff_confirm_kb,
    test_pay_kb,
    my_sub_kb,
    connections_kb,
    connection_detail_kb,
    back_kb,
)

logger = logging.getLogger(__name__)
router = Router()


def format_date(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        return datetime.fromisoformat(iso_str).strftime("%d.%m.%Y")
    except Exception:
        return str(iso_str)[:10]


def days_left(end_date: str) -> int:
    if not end_date:
        return 0
    try:
        end = datetime.fromisoformat(end_date)
        return max(0, (end - datetime.utcnow()).days)
    except Exception:
        return 0



async def activate_paid_order(order_id: int, bot=None) -> str:
    """Fulfil a paid subscription order. Call only after trusted payment confirmation."""
    order = await db.get_order(order_id)
    if not order:
        return "Заказ не найден. Обратитесь в поддержку."
    tariff = await db.get_tariff(order["tariff_id"])
    if not tariff:
        return "Оплата получена, но тариф не найден. Обратитесь в поддержку."
    user_id = int(order["user_id"])
    existing = await db.get_active_subscription(user_id)
    sub = await db.activate_subscription(user_id=user_id, tariff=tariff, extend=existing is not None)
    config_data = ""
    try:
        from h1cloud import h1cloud_client
        if h1cloud_client.configured:
            days = int(tariff.get("duration_days", 30))
            if existing:
                await h1cloud_client.extend_client(user_id, days)
                remote = await h1cloud_client.get_client(user_id)
                client = remote.get("client") or remote
                config_data = client.get("subscription_url") or client.get("sub_url") or client.get("link") or ""
            else:
                config_data = await h1cloud_client.create_client(user_id, days)
    except Exception as exc:
        logger.exception("H1 client creation failed for Telegram user %s", user_id)
        config_data = ""
    if not config_data:
        config_data = f"H1_PENDING_USER_{user_id}"
    conn_id = await db.create_connection(user_id=user_id, subscription_id=sub["id"], expires_at=sub["end_date"], config_data=config_data)
    action = "продлена" if existing else "активирована"
    if config_data.startswith("H1_PENDING_"):
        connection_note = "Подключение создано, но VPN-ссылка пока не получена. Проверьте H1CLOUD_API_TOKEN и настройки панели в Render."
    else:
        connection_note = "Откройте «Мои подключения», чтобы получить ссылку подписки."
    msg = (f"◈ <b>OMNIRO VPN — подписка {action}!</b>\n\nТариф: {tariff['name']}\n"
           f"Действует до: {format_date(sub['end_date'])}\nПодключение #{conn_id} создано.\n\n{connection_note}")
    if bot:
        try:
            await bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=back_kb())
        except Exception:
            logger.exception("Could not notify user %s about paid order %s", user_id, order_id)
    return msg

@router.callback_query(F.data == "buy_sub")
async def cb_buy_sub(callback: CallbackQuery):
    tariffs = await db.get_active_tariffs()
    if not tariffs:
        await callback.message.edit_text(
            "Тарифы временно недоступны.",
            reply_markup=back_kb(),
        )
        await callback.answer()
        return

    text = "🛒 <b>Выберите тариф</b>\n\n"
    for t in tariffs:
        text += f"<b>{t['name']}</b> — {t['price']:.0f} ₽\n"
        if t.get("description"):
            text += f"  {t['description']}\n"
        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=tariffs_kb(tariffs),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tariff_"))
async def cb_tariff_detail(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[1])
    tariff = await db.get_tariff(tariff_id)
    if not tariff or not tariff["is_active"]:
        await callback.answer("Тариф недоступен", show_alert=True)
        return

    text = (
        f"<b>{tariff['name']}</b>\n\n"
        f"📅 Срок: {tariff['duration_days']} дней\n"
        f"💰 Стоимость: {tariff['price']:.0f} ₽\n"
    )
    if tariff.get("description"):
        text += f"\n{tariff['description']}"

    await callback.message.edit_text(
        text,
        reply_markup=tariff_confirm_kb(tariff_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_tariff_"))
async def cb_pay_tariff(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[2])
    tariff = await db.get_tariff(tariff_id)
    if not tariff or not tariff["is_active"]:
        await callback.answer("Тариф недоступен", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка пользователя", show_alert=True)
        return

    amount = tariff["price"]
    balance = user.get("balance", 0) or 0

    # Create order
    order_id = await db.create_order(
        user_id=callback.from_user.id,
        tariff_id=tariff_id,
        amount=amount,
    )

    if config.TEST_MODE:
        text = (
            f"🧪 <b>Тестовый режим</b>\n\n"
            f"Заказ #{order_id}\n"
            f"Тариф: {tariff['name']}\n"
            f"Сумма: {amount:.0f} ₽\n\n"
            f"Нажмите «Подтвердить оплату» для имитации платежа."
        )
        await callback.message.edit_text(
            text,
            reply_markup=test_pay_kb(order_id),
            parse_mode="HTML",
        )
    else:
        # Future: real payment flow via payment_service
        result = await payment_service.create_payment(
            amount=amount,
            description=f"Подписка: {tariff['name']}",
            user_id=callback.from_user.id,
            order_id=order_id,
        )
        if result.success and result.payment_url:
            await db.set_order_payment_id(order_id, result.payment_id or "")
            text = (
                f"Заказ #{order_id}\n"
                f"Тариф: {tariff['name']}\n"
                f"Сумма: {amount:.0f} ₽\n\n"
                f"Перейдите по ссылке для оплаты."
            )
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=result.payment_url,)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_sub",)],
            ])
            await callback.message.edit_text(text, reply_markup=kb)
        else:
            logger.error("Payment creation failed for order %s: %s", order_id, result.error)
            await callback.message.edit_text(
                "Не удалось создать платёж. Проверьте настройки RollyPay или попробуйте позже.",
                reply_markup=back_kb("buy_sub"),
            )
    await callback.answer()


@router.callback_query(F.data.startswith("test_pay_"))
async def cb_test_pay(callback: CallbackQuery):
    if not config.TEST_MODE:
        await callback.answer("Недоступно", show_alert=True)
        return

    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if order["status"] == "paid":
        await callback.answer("Уже оплачен", show_alert=True)
        return

    tariff = await db.get_tariff(order["tariff_id"])
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    changed = await db.complete_order(order_id)
    if not changed:
        await callback.answer("Заказ уже обработан", show_alert=True)
        return
    result_text = await activate_paid_order(order_id)
    await callback.message.edit_text(result_text, reply_markup=back_kb(), parse_mode="HTML")
    await callback.answer("Тестовая оплата подтверждена")


@router.callback_query(F.data == "my_sub")
async def cb_my_sub(callback: CallbackQuery):
    sub = await db.get_active_subscription(callback.from_user.id)
    if sub:
        left = days_left(sub["end_date"])
        text = (
            f"👤 <b>Моя подписка</b>\n\n"
            f"Статус: 🟢 АКТИВНА\n"
            f"Тариф: {sub.get('tariff_name', '—')}\n"
            f"Начало: {format_date(sub['start_date'])}\n"
            f"Окончание: {format_date(sub['end_date'])}\n"
            f"Осталось: {left} дн."
        )
        kb = my_sub_kb(has_active=True)
    else:
        # Check last expired
        last = await db.get_subscription(callback.from_user.id)
        if last:
            text = (
                f"👤 <b>Моя подписка</b>\n\n"
                f"Статус: 🔴 НЕ АКТИВНА\n"
                f"Последний тариф: {last.get('tariff_name', '—')}\n"
                f"Истекла: {format_date(last['end_date'])}"
            )
        else:
            text = (
                f"👤 <b>Моя подписка</b>\n\n"
                f"🔴 Подписка не активна"
            )
        kb = my_sub_kb(has_active=False)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "get_connection")
async def cb_get_connection(callback: CallbackQuery):
    connections = await db.get_user_connections(callback.from_user.id)
    if not connections:
        # Try to create one from active sub
        sub = await db.get_active_subscription(callback.from_user.id)
        if sub:
            conn_id = await db.create_connection(
                user_id=callback.from_user.id,
                subscription_id=sub["id"],
                expires_at=sub["end_date"],
                config_data=f"TEST_CONFIG_FOR_USER_{callback.from_user.id}",
            )
            connections = await db.get_user_connections(callback.from_user.id)

    if not connections:
        await callback.answer("Нет активных подключений", show_alert=True)
        return

    # Redirect to connections list
    await cb_my_connections(callback)


@router.callback_query(F.data == "my_connections")
async def cb_my_connections(callback: CallbackQuery):
    connections = await db.get_user_connections(callback.from_user.id)
    if not connections:
        text = "🔑 <b>Мои подключения</b>\n\nУ вас нет активных подключений."
        await callback.message.edit_text(
            text,
            reply_markup=back_kb(),
            parse_mode="HTML",
        )
    else:
        text = "🔑 <b>Мои подключения</b>\n\nВыберите подключение:"
        await callback.message.edit_text(
            text,
            reply_markup=connections_kb(connections),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("conn_") & ~F.data.startswith("conn_config_") & ~F.data.startswith("conn_copy_"))
async def cb_connection_detail(callback: CallbackQuery):
    conn_id = int(callback.data.split("_")[1])
    conn = await db.get_connection(conn_id)
    if not conn or conn["user_id"] != callback.from_user.id:
        await callback.answer("Подключение не найдено", show_alert=True)
        return

    status = "🟢 Активно" if conn["status"] == "active" else "🔴 Неактивно"
    text = (
        f"🔑 <b>Подключение #{conn['id']}</b>\n\n"
        f"Статус: {status}\n"
        f"До: {format_date(conn.get('expires_at'))}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=connection_detail_kb(conn_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("conn_config_"))
async def cb_conn_config(callback: CallbackQuery):
    conn_id = int(callback.data.split("_")[2])
    conn = await db.get_connection(conn_id)
    if not conn or conn["user_id"] != callback.from_user.id:
        await callback.answer("Подключение не найдено", show_alert=True)
        return

    config_data = conn.get("config_data") or "Конфигурация пока недоступна"
    if str(config_data).startswith(("H1_PENDING_", "CONFIG_PENDING_", "TEST_CONFIG_")):
        body = "<i>Ссылка ещё не готова. Обратитесь в поддержку, если она не появится после проверки настроек панели.</i>"
    else:
        from html import escape
        body = f"<code>{escape(str(config_data))}</code>"
    text = f"◈ <b>OMNIRO VPN · подключение #{conn_id}</b>\n\n{body}"
    await callback.message.edit_text(
        text,
        reply_markup=connection_detail_kb(conn_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("conn_copy_"))
async def cb_conn_copy(callback: CallbackQuery):
    conn_id = int(callback.data.split("_")[2])
    conn = await db.get_connection(conn_id)
    if not conn or conn["user_id"] != callback.from_user.id:
        await callback.answer("Подключение не найдено", show_alert=True)
        return

    config_data = conn.get("config_data") or "N/A"
    await callback.answer(f"Данные: {config_data[:50]}...", show_alert=True)
