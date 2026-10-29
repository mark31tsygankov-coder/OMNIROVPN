from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Optional

def main_menu_kb(is_admin: bool=False) -> InlineKeyboardMarkup:
    buttons = []
    buttons += [[InlineKeyboardButton(text='◈ Подключить OMNIRO VPN', callback_data='buy_sub', style='success')], [InlineKeyboardButton(text='▣ Моя подписка', callback_data='my_sub', style='primary'), InlineKeyboardButton(text='＋ Пополнить баланс', callback_data='topup', style='success')], [InlineKeyboardButton(text='⌁ Мои подключения', callback_data='my_connections', style='primary'), InlineKeyboardButton(text='✉ Поддержка', callback_data='support', style='primary')], [InlineKeyboardButton(text='▤ Документы', callback_data='documents', style='primary'), InlineKeyboardButton(text='◉ Профиль', callback_data='profile', style='primary')]]
    if is_admin:
        buttons.append([InlineKeyboardButton(text='⚙️ Админ-панель', callback_data='admin_panel', style='primary')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_kb(callback: str='main_menu') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='◀️ Назад', callback_data=callback, style='primary')]])

def tariffs_kb(tariffs: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for t in tariffs:
        buttons.append([InlineKeyboardButton(text=f"{t['name']} — {t['price']:.0f} ₽", callback_data=f"tariff_{t['id']}", style='primary')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def tariff_confirm_kb(tariff_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💳 Оплатить', callback_data=f'pay_tariff_{tariff_id}', style='success')], [InlineKeyboardButton(text='◀️ Назад', callback_data='buy_sub', style='primary')]])

def test_pay_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить оплату (TEST)', callback_data=f'test_pay_{order_id}', style='success')], [InlineKeyboardButton(text='❌ Отмена', callback_data='buy_sub', style='danger')]])

def my_sub_kb(has_active: bool) -> InlineKeyboardMarkup:
    if has_active:
        buttons = [[InlineKeyboardButton(text='🔑 Получить подключение', callback_data='get_connection', style='success')], [InlineKeyboardButton(text='🔄 Продлить подписку', callback_data='buy_sub', style='success')], [InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')]]
    else:
        buttons = []
    buttons += [[InlineKeyboardButton(text='◈ Подключить OMNIRO VPN', callback_data='buy_sub', style='success')], [InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def topup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💰 Пополнить', callback_data='topup_request', style='success')], [InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')]])

def connections_kb(connections: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for c in connections:
        buttons.append([InlineKeyboardButton(text=f"🔑 Подключение #{c['id']}", callback_data=f"conn_{c['id']}", style='primary')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def connection_detail_kb(conn_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📥 Получить конфигурацию', callback_data=f'conn_config_{conn_id}', style='success')], [InlineKeyboardButton(text='📋 Скопировать данные', callback_data=f'conn_copy_{conn_id}', style='primary')], [InlineKeyboardButton(text='◀️ Назад', callback_data='my_connections', style='primary')]])

def documents_kb(privacy_url: str, terms_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📕 Политика конфиденциальности', url=privacy_url, style='primary')], [InlineKeyboardButton(text='📜 Пользовательское соглашение', url=terms_url, style='primary')], [InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')]])

def support_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✏️ Создать тикет', callback_data='create_ticket', style='success')], [InlineKeyboardButton(text='📋 Мои тикеты', callback_data='my_tickets', style='primary')], [InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')]])

def tickets_list_kb(tickets: List[Dict], prefix: str='ticket') -> InlineKeyboardMarkup:
    buttons = []
    status_emoji = {'open': '🟡', 'answered': '🟢', 'closed': '⚪️'}
    for t in tickets:
        emoji = status_emoji.get(t['status'], '⚪')
        buttons.append([InlineKeyboardButton(text=f"{emoji} Тикет #{t['id']} — {t.get('subject', '')[:30]}", callback_data=f"{prefix}_{t['id']}", style='primary')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='support', style='primary')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def ticket_actions_kb(ticket_id: int, is_admin: bool=False) -> InlineKeyboardMarkup:
    buttons = []
    if is_admin:
        buttons.append([InlineKeyboardButton(text='💬 Ответить', callback_data=f'admin_reply_ticket_{ticket_id}', style='success')])
        buttons.append([InlineKeyboardButton(text='🔒 Закрыть', callback_data=f'admin_close_ticket_{ticket_id}', style='danger'), InlineKeyboardButton(text='🗑 Удалить', callback_data=f'admin_delete_ticket_{ticket_id}', style='danger')])
        buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='admin_tickets', style='primary')])
    else:
        buttons.append([InlineKeyboardButton(text='💬 Написать', callback_data=f'reply_ticket_{ticket_id}', style='primary')])
        buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='my_tickets', style='primary')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_kb(confirm_data: str, cancel_data: str='main_menu') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить', callback_data=confirm_data, style='success'), InlineKeyboardButton(text='❌ Отмена', callback_data=cancel_data, style='danger')]])

def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')]])
