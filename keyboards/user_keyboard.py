from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает главное меню пользователя."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🔄 Обновить промокод")],
            [KeyboardButton(text="🎁 Ежедневный бонус")],
            [KeyboardButton(text="💰 Вывести голды")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для профиля."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Вывести голды", callback_data="profile_withdraw"),
            InlineKeyboardButton(text="🔗 Реферальная ссылка", callback_data="profile_referral")
        ],
        [
            InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="profile_promo")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return keyboard


def get_withdraw_keyboard() -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для вывода."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return keyboard
