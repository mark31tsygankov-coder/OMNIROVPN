import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import db
from config import config
from keyboards_main_menu import topup_kb, back_kb

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "topup")
async def cb_topup(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    balance = (user.get("balance") or 0) if user else 0

    text = (
        f"💳 <b>Пополнить баланс</b>\n\n"
        f"💰 Текущий баланс: <b>{balance:.0f} ₽</b>\n\n"
    )
    if config.TEST_MODE:
        text += (
            "<i>Платёжная система ещё не подключена.\n"
            "В тестовом режиме пополнение доступно через администратора.</i>"
        )
    else:
        text += "Выберите способ пополнения:"

    await callback.message.edit_text(
        text,
        reply_markup=topup_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "topup_request")
async def cb_topup_request(callback: CallbackQuery):
    if config.TEST_MODE:
        text = (
            "🧪 <b>Тестовый режим</b>\n\n"
            "Реальное пополнение пока недоступно.\n"
            "Обратитесь к администратору для начисления баланса\n"
            "или используйте тестовую оплату подписки."
        )
        await callback.message.edit_text(
            text,
            reply_markup=back_kb("topup"),
            parse_mode="HTML",
        )
    else:
        # Future: real payment for balance top-up
        text = (
            "Пополнение баланса через платёжную систему\n"
            "будет доступно после подключения провайдера."
        )
        await callback.message.edit_text(
            text,
            reply_markup=back_kb("topup"),
        )
    await callback.answer()
