import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from database import db
from config import config
from keyboards_main_menu import main_menu_kb

logger = logging.getLogger(__name__)
router = Router()


def format_date(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return iso_str[:10]


def days_left(end_date: str) -> int:
    if not end_date:
        return 0
    try:
        end = datetime.fromisoformat(end_date)
        delta = end - datetime.utcnow()
        return max(0, delta.days)
    except Exception:
        return 0


async def build_welcome_text(user: dict) -> str:
    sub = await db.get_active_subscription(user["telegram_id"])
    balance = user.get("balance", 0) or 0

    if sub:
        sub_status = f"🟢 Активна до {format_date(sub['end_date'])}"
    else:
        sub_status = "не активна"

    name = user.get("full_name") or user.get("username") or "друг"

    return (
        f"◈ <b>OMNIRO VPN</b>\nПриватное подключение без лишних сложностей.\n\nПривет, {name}!\n\n"
        f"Выберите действие ниже, чтобы подключить VPN, проверить подписку или получить помощь.\n\n"
        f"💰 Баланс: {balance:.0f} ₽\n"
        f"📅 Подписка: {sub_status}"
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    if user.get("is_blocked"):
        await message.answer("🚫 Ваш аккаунт заблокирован.")
        return

    text = await build_welcome_text(user)
    is_admin = message.from_user.id == config.ADMIN_ID
    await message.answer(text, reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    user = await db.get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    if user.get("is_blocked"):
        await callback.answer("Аккаунт заблокирован", show_alert=True)
        return

    text = await build_welcome_text(user)
    is_admin = callback.from_user.id == config.ADMIN_ID
    await callback.message.edit_text(text, reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")
    await callback.answer()
