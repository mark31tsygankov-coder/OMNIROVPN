from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import db
from keyboards_main_menu import profile_kb

router = Router()


def format_date(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        return datetime.fromisoformat(iso_str).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(iso_str)[:16]


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    sub = await db.get_active_subscription(callback.from_user.id)
    sub_text = "🟢 Активна" if sub else "🔴 Не активна"
    if sub:
        sub_text += f" до {format_date(sub['end_date'])[:10]}"

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{user['telegram_id']}</code>\n"
        f"Имя: {user.get('full_name') or '—'}\n"
        f"Username: @{user.get('username') or '—'}\n"
        f"Баланс: {user.get('balance', 0):.0f} ₽\n"
        f"Подписка: {sub_text}\n"
        f"Регистрация: {format_date(user.get('created_at'))}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=profile_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
