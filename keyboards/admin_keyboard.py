from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру админ-панели."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin_promocodes"),
            InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_create_promo")
        ],
        [
            InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin_withdrawals")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return keyboard


def get_withdraw_action_keyboard(withdraw_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для действий с заявкой на вывод."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_withdraw_{withdraw_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_withdraw_{withdraw_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    return keyboard


def get_promo_action_keyboard(promo_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для действий с промокодом."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Отправить пользователям", callback_data=f"admin_send_promo_{promo_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    return keyboard
