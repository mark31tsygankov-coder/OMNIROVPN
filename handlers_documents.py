from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import config
from keyboards_main_menu import documents_kb

router = Router()


@router.callback_query(F.data == "documents")
async def cb_documents(callback: CallbackQuery):
    text = "📄 <b>Документы</b>\n\nВыберите документ для ознакомления:"
    await callback.message.edit_text(
        text,
        reply_markup=documents_kb(config.PRIVACY_POLICY_URL, config.TERMS_URL),
        parse_mode="HTML",
    )
    await callback.answer()
