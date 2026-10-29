import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import config
from keyboards_main_menu import (
    support_kb,
    tickets_list_kb,
    ticket_actions_kb,
    back_kb,
)

logger = logging.getLogger(__name__)
router = Router()


class SupportStates(StatesGroup):
    waiting_subject = State()
    waiting_message = State()
    waiting_reply = State()


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🎫 <b>Поддержка</b>\n\n"
        "Создайте тикет, и администратор ответит вам."
    )
    await callback.message.edit_text(
        text,
        reply_markup=support_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "create_ticket")
async def cb_create_ticket(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_subject)
    await callback.message.edit_text(
        "✏️ Введите тему обращения (кратко):",
        reply_markup=back_kb("support"),
    )
    await callback.answer()


@router.message(SupportStates.waiting_subject)
async def process_subject(message: Message, state: FSMContext):
    subject = message.text.strip()[:100]
    if not subject:
        await message.answer("Тема не может быть пустой. Введите тему:")
        return
    await state.update_data(subject=subject)
    await state.set_state(SupportStates.waiting_message)
    await message.answer("📝 Опишите проблему подробнее:")


@router.message(SupportStates.waiting_message)
async def process_message(message: Message, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject", "Без темы")
    text = message.text.strip()
    if not text:
        await message.answer("Сообщение не может быть пустым.")
        return

    ticket_id = await db.create_ticket(
        user_id=message.from_user.id,
        subject=subject,
        message=text,
    )
    await state.clear()

    # Notify admin
    try:
        from aiogram import Bot
        bot: Bot = message.bot
        await bot.send_message(
            config.ADMIN_ID,
            f"🎫 Новый тикет #{ticket_id}\n"
            f"От: {message.from_user.full_name} (@{message.from_user.username})\n"
            f"ID: {message.from_user.id}\n"
            f"Тема: {subject}\n\n"
            f"{text[:500]}",
        )
    except Exception as e:
        logger.error("Failed to notify admin about ticket: %s", e)

    await message.answer(
        f"🎫 Тикет #{ticket_id}\n"
        f"Статус: 🟡 Ожидает ответа\n\n"
        f"Мы ответим как можно скорее.",
        reply_markup=support_kb(),
    )


@router.callback_query(F.data == "my_tickets")
async def cb_my_tickets(callback: CallbackQuery):
    tickets = await db.get_user_tickets(callback.from_user.id)
    if not tickets:
        text = "📋 У вас пока нет тикетов."
        await callback.message.edit_text(
            text,
            reply_markup=back_kb("support"),
        )
    else:
        text = "📋 <b>Мои тикеты</b>\n\nВыберите тикет:"
        await callback.message.edit_text(
            text,
            reply_markup=tickets_list_kb(tickets, prefix="ticket"),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("ticket_"))
async def cb_view_ticket(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != callback.from_user.id:
        await callback.answer("Тикет не найден", show_alert=True)
        return

    messages = await db.get_ticket_messages(ticket_id)
    status_map = {
        "open": "🟡 Ожидает ответа",
        "answered": "🟢 Есть ответ",
        "closed": "⚪️ Закрыт",
    }
    status = status_map.get(ticket["status"], ticket["status"])

    text = (
        f"🎫 <b>Тикет #{ticket_id}</b>\n"
        f"Статус: {status}\n"
        f"Тема: {ticket.get('subject', '—')}\n\n"
    )
    for m in messages[-10:]:
        who = "👨‍💼 Админ" if m["is_admin"] else "👤 Вы"
        text += f"{who}: {m['message'][:200]}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=ticket_actions_kb(ticket_id, is_admin=False),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reply_ticket_"))
async def cb_reply_ticket(callback: CallbackQuery, state: FSMContext):
    ticket_id = int(callback.data.split("_")[2])
    ticket = await db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != callback.from_user.id:
        await callback.answer("Тикет не найден", show_alert=True)
        return
    if ticket["status"] == "closed":
        await callback.answer("Тикет закрыт", show_alert=True)
        return

    await state.set_state(SupportStates.waiting_reply)
    await state.update_data(ticket_id=ticket_id)
    await callback.message.edit_text(
        "💬 Введите ваше сообщение:",
        reply_markup=back_kb(f"ticket_{ticket_id}"),
    )
    await callback.answer()


@router.message(SupportStates.waiting_reply)
async def process_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await state.clear()
        return

    text = message.text.strip()
    if not text:
        await message.answer("Сообщение не может быть пустым.")
        return

    await db.add_ticket_message(
        ticket_id=ticket_id,
        sender_id=message.from_user.id,
        message=text,
        is_admin=False,
    )
    await state.clear()

    # Notify admin
    try:
        await message.bot.send_message(
            config.ADMIN_ID,
            f"💬 Новое сообщение в тикете #{ticket_id}\n"
            f"От пользователя {message.from_user.id}:\n\n{text[:500]}",
        )
    except Exception as e:
        logger.error("Failed to notify admin: %s", e)

    await message.answer(
        f"✅ Сообщение отправлено в тикет #{ticket_id}",
        reply_markup=support_kb(),
    )
