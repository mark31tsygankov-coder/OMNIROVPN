from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📊 Статистика', callback_data='admin_stats', style='primary'), InlineKeyboardButton(text='👥 Пользователи', callback_data='admin_users', style='primary')], [InlineKeyboardButton(text='📦 Подписки', callback_data='admin_subs', style='primary'), InlineKeyboardButton(text='💳 Платежи', callback_data='admin_payments', style='primary')], [InlineKeyboardButton(text='💰 Балансы', callback_data='admin_balances', style='primary'), InlineKeyboardButton(text='🔑 Подключения', callback_data='admin_connections', style='primary')], [InlineKeyboardButton(text='🖥 H1Cloud', callback_data='admin_h1cloud', style='primary'), InlineKeyboardButton(text='💵 Тарифы', callback_data='admin_tariffs', style='primary')], [InlineKeyboardButton(text='🎟 Промокоды', callback_data='admin_promos', style='primary'), InlineKeyboardButton(text='🎫 Тикеты', callback_data='admin_tickets', style='primary')], [InlineKeyboardButton(text='📢 Рассылка', callback_data='admin_broadcast', style='primary'), InlineKeyboardButton(text='⚙️ Настройки', callback_data='admin_settings', style='primary')], [InlineKeyboardButton(text='◀️ Назад', callback_data='main_menu', style='primary')]])

def admin_tariffs_kb(tariffs: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for t in tariffs:
        status = '✅' if t['is_active'] else '❌'
        buttons.append([InlineKeyboardButton(text=f"{status} {t['name']} — {t['price']:.0f} ₽ / {t['duration_days']}д", callback_data=f"admin_tariff_{t['id']}", style='primary')])
    buttons.append([InlineKeyboardButton(text='➕ Создать тариф', callback_data='admin_create_tariff', style='primary')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='admin_panel', style='primary')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_tariff_detail_kb(tariff_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = '🔴 Выключить' if is_active else '🟢 Включить'
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✏️ Название', callback_data=f'admin_edit_tariff_name_{tariff_id}', style='primary'), InlineKeyboardButton(text='💰 Цена', callback_data=f'admin_edit_tariff_price_{tariff_id}', style='primary')], [InlineKeyboardButton(text='📅 Срок', callback_data=f'admin_edit_tariff_days_{tariff_id}', style='primary'), InlineKeyboardButton(text='📝 Описание', callback_data=f'admin_edit_tariff_desc_{tariff_id}', style='primary')], [InlineKeyboardButton(text=toggle_text, callback_data=f'admin_toggle_tariff_{tariff_id}', style='primary')], [InlineKeyboardButton(text='🗑 Удалить', callback_data=f'admin_delete_tariff_{tariff_id}', style='danger')], [InlineKeyboardButton(text='◀️ Назад', callback_data='admin_tariffs', style='primary')]])

def admin_users_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔍 Найти по ID', callback_data='admin_search_user', style='primary')], [InlineKeyboardButton(text='◀️ Назад', callback_data='admin_panel', style='primary')]])

def admin_user_detail_kb(user_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    block_text = '🟢 Разблокировать' if is_blocked else '🚫 Заблокировать'
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💰 Начислить баланс', callback_data=f'admin_add_balance_{user_id}', style='primary'), InlineKeyboardButton(text='💸 Списать баланс', callback_data=f'admin_sub_balance_{user_id}', style='primary')], [InlineKeyboardButton(text='🟢 Активировать подписку', callback_data=f'admin_activate_sub_{user_id}', style='primary'), InlineKeyboardButton(text='🔄 Продлить', callback_data=f'admin_extend_sub_{user_id}', style='success')], [InlineKeyboardButton(text='🔴 Отключить подписку', callback_data=f'admin_deactivate_sub_{user_id}', style='primary')], [InlineKeyboardButton(text=block_text, callback_data=f'admin_block_user_{user_id}', style='primary')], [InlineKeyboardButton(text='◀️ Назад', callback_data='admin_users', style='primary')]])

def admin_promos_kb(promos: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for p in promos:
        status = '✅' if p['is_active'] else '❌'
        buttons.append([InlineKeyboardButton(text=f"{status} {p['code']} ({p['discount_type']}: {p['discount_value']})", callback_data=f"admin_promo_{p['id']}", style='primary')])
    buttons.append([InlineKeyboardButton(text='➕ Создать промокод', callback_data='admin_create_promo', style='primary')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='admin_panel', style='primary')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_tickets_kb(tickets: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    status_emoji = {'open': '🟡', 'answered': '🟢', 'closed': '⚪️'}
    for t in tickets[:20]:
        emoji = status_emoji.get(t['status'], '⚪')
        buttons.append([InlineKeyboardButton(text=f"{emoji} #{t['id']} uid:{t['user_id']} — {t.get('subject', '')[:25]}", callback_data=f"admin_ticket_{t['id']}", style='primary')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='admin_panel', style='primary')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🟢 ОТПРАВИТЬ', callback_data='admin_broadcast_send', style='primary'), InlineKeyboardButton(text='🔴 ОТМЕНА', callback_data='admin_panel', style='danger')]])

def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='◀️ Назад', callback_data='admin_panel', style='primary')]])
