from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
import logging

from database import Database
from keyboards import user_keyboard, admin_keyboard
from config import settings

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("profile_"))
async def callback_profile(callback: types.CallbackQuery, db: Database):
    """Обработчик callback кнопок профиля."""
    action = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    if action == "withdraw":
        await callback.message.edit_text(
            "💸 Вывод голдов\n\nВведите сумму для вывода:"
        )
        # Здесь можно добавить FSM для обработки вывода
    
    elif action == "referral":
        user = await db.get_user(user_id)
        bot_info = await callback.bot.get_me()
        referral_link = f"https://t.me/{bot_info.username}?start={user_id}"
        
        await callback.message.edit_text(
            f"🔗 Твоя реферальная ссылка:\n\n{referral_link}\n\n"
            f"Приглашено: {user['referral_count']} пользователей\n"
            f"До следующей награды: {settings.REFERRAL_THRESHOLD - (user['referral_count'] % settings.REFERRAL_THRESHOLD)}"
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin_"))
async def callback_admin(callback: types.CallbackQuery, db: Database):
    """Обработчик callback кнопок админки."""
    action = callback.data.split("_")[1]
    
    # Проверка прав админа
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    if action == "approve_withdraw":
        # Подтверждение вывода
        withdraw_id = int(callback.data.split("_")[2])
        success = await db.update_withdrawal_status(withdraw_id, "approved")
        
        if success:
            await callback.answer("✅ Заявка одобрена")
            await callback.message.edit_text("💸 Заявка на вывод одобрена")
        else:
            await callback.answer("❌ Ошибка при одобрении заявки")
    
    elif action == "reject_withdraw":
        # Отклонение вывода
        withdraw_id = int(callback.data.split("_")[2])
        success = await db.update_withdrawal_status(withdraw_id, "rejected")
        
        if success:
            await callback.answer("❌ Заявка отклонена")
            await callback.message.edit_text("💸 Заявка на вывод отклонена")
        else:
            await callback.answer("❌ Ошибка при отклонении заявки")
    
    elif action == "send_promo":
        # Отправка промокода пользователям
        # Здесь можно добавить логику массовой рассылки промокода
        await callback.answer("📤 Промокод отправлен пользователям")
    
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: types.CallbackQuery):
    """Возврат в главное меню."""
    await callback.message.delete()
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=user_keyboard.get_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_admin")
async def callback_back_to_admin(callback: types.CallbackQuery):
    """Возврат в админ-панель."""
    await callback.message.edit_text(
        "🔧 Панель администратора",
        reply_markup=admin_keyboard.get_admin_keyboard()
    )
    await callback.answer()
