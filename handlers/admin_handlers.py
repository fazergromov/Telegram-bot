from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta, timezone
import logging

from database import Database
from keyboards import admin_keyboard
from config import settings

logger = logging.getLogger(__name__)
router = Router()


class BroadcastStates(StatesGroup):
    """Состояния для процесса рассылки."""
    waiting_message = State()


class RejectionStates(StatesGroup):
    """Состояния для ввода причины отказа."""
    waiting_reason = State()


class PromoCreationStates(StatesGroup):
    """Состояния для создания промокода бота."""
    waiting_code = State()
    waiting_gold = State()
    waiting_limit = State()


def get_next_promocode_time():
    """Вычисляет время следующего промокода (нечетные часы в минуту 36 по МСК)."""
    # Получаем текущее время и вычитаем 2 часа для МСК
    now = datetime.now() - timedelta(hours=2)
    minute = now.minute
    hour = now.hour
    
    # Нечетные часы: 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23
    odd_hours = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]
    
    # Если текущая минута < 36 и текущий час нечетный, следующий промокод в этом же часе в 36
    if minute < 36 and hour in odd_hours:
        next_time = now.replace(minute=36, second=0, microsecond=0)
    else:
        # Иначе находим следующий нечетный час
        found = False
        for odd_hour in odd_hours:
            if odd_hour > hour:
                next_time = now.replace(hour=odd_hour, minute=36, second=0, microsecond=0)
                found = True
                break
        if not found:
            # Если не нашли, переходим на следующий день
            next_time = now.replace(hour=1, minute=36, second=0, microsecond=0) + timedelta(days=1)
    
    return f"{next_time.strftime('%H:%M')}"


# Фильтр для админа
def is_admin(callback: types.CallbackQuery) -> bool:
    """Проверяет, является ли пользователь админом."""
    return callback.from_user.id == settings.ADMIN_ID


@router.message(Command("admin"))
async def cmd_admin(message: types.Message, db: Database):
    """Обработчик команды /admin."""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    admin_text = """
🔧 Панель администратора

Выберите действие:
"""
    
    await message.answer(
        admin_text,
        reply_markup=admin_keyboard.get_admin_keyboard()
    )


@router.callback_query(F.data == "admin_stats", is_admin)
async def admin_stats(callback: types.CallbackQuery, db: Database):
    """Показывает статистику бота."""
    users = await db.get_all_users()
    promocodes = await db.get_unsent_promocodes()
    withdrawals = await db.get_pending_withdrawals()
    
    stats_text = f"""
📊 Статистика бота

👥 Пользователей: {len(users)}
🎁 Неотправленных промокодов: {len(promocodes)}
💸 Ожидающих выводов: {len(withdrawals)}

📈 Активность:
• Всего пользователей: {len(users)}
• Новых за сегодня: 0
"""
    
    await callback.message.edit_text(stats_text, reply_markup=admin_keyboard.get_admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast", is_admin)
async def admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    """Запускает процесс рассылки."""
    await callback.message.edit_text(
        "📢 Рассылка сообщений\n\nВведите текст для рассылки всем пользователям:"
    )
    await state.set_state(BroadcastStates.waiting_message)
    await callback.answer()


@router.message(BroadcastStates.waiting_message)
async def process_broadcast_message(message: types.Message, state: FSMContext, db: Database):
    """Обработчик ввода текста для рассылки."""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    broadcast_text = message.text
    users = await db.get_all_users()
    
    success_count = 0
    for user in users:
        try:
            await message.bot.send_message(user['user_id'], broadcast_text)
            success_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user['user_id']}: {e}")
    
    await message.answer(f"✅ Рассылка отправлена {success_count} из {len(users)} пользователей")
    await state.clear()


@router.callback_query(F.data == "admin_promocodes", is_admin)
async def admin_promocodes(callback: types.CallbackQuery, db: Database):
    """Показывает список промокодов бота."""
    promocodes = await db.get_all_bot_promocodes()
    
    if not promocodes:
        await callback.message.edit_text("🎁 Промокодов бота пока нет. Создайте первый!", reply_markup=admin_keyboard.get_admin_keyboard())
        await callback.answer()
        return
    
    promo_text = "🎁 Промокоды бота:\n\n"
    for promo in promocodes[-5:]:  # Последние 5
        limit_text = f" (Лимит: {promo['usage_limit']})" if promo['usage_limit'] else " (Без лимита)"
        promo_text += f"• `{promo['code']}` - {promo['gold_reward']} голдов{limit_text}\n"
    
    await callback.message.edit_text(promo_text, reply_markup=admin_keyboard.get_admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_create_promo", is_admin)
async def admin_create_promo(callback: types.CallbackQuery, state: FSMContext):
    """Запускает процесс создания промокода."""
    await callback.message.edit_text("🎁 Создание промокода\n\nВведите код промокода:")
    await state.set_state(PromoCreationStates.waiting_code)
    await callback.answer()


@router.message(PromoCreationStates.waiting_code)
async def process_promo_code(message: types.Message, state: FSMContext):
    """Обрабатывает ввод кода промокода."""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    code = message.text.strip().upper()
    await state.update_data(code=code)
    
    await message.answer(f"Код: `{code}`\n\nВведите количество голдов для награды:")
    await state.set_state(PromoCreationStates.waiting_gold)


@router.message(PromoCreationStates.waiting_gold)
async def process_promo_gold(message: types.Message, state: FSMContext):
    """Обрабатывает ввод количества голдов."""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    try:
        gold = int(message.text.strip())
        if gold <= 0:
            await message.answer("❌ Количество голдов должно быть больше 0. Попробуйте снова:")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")
        return
    
    await state.update_data(gold=gold)
    
    await message.answer(f"Награда: {gold} голдов\n\nВведите лимит использований (число) или 0 для безлимитного:")
    await state.set_state(PromoCreationStates.waiting_limit)


@router.message(PromoCreationStates.waiting_limit)
async def process_promo_limit(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает ввод лимита и создает промокод."""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    try:
        limit = int(message.text.strip())
        if limit < 0:
            await message.answer("❌ Лимит не может быть отрицательным. Попробуйте снова:")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")
        return
    
    data = await state.get_data()
    code = data.get('code')
    gold = data.get('gold')
    
    usage_limit = None if limit == 0 else limit
    
    success = await db.add_bot_promocode(code, gold, usage_limit)
    
    if success:
        # Отправляем уведомление всем пользователям
        users = await db.get_all_users()
        success_count = 0
        
        for user in users:
            try:
                limit_text = f" (Лимит: {usage_limit})" if usage_limit else ""
                await message.bot.send_message(
                    user['user_id'],
                    f"🎉 НОВЫЙ ПРОМОКОД БОТА\n`{code}` - {gold} голдов{limit_text}\n\nДля активации: Профиль → Ввести промокод",
                    parse_mode="Markdown"
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user['user_id']}: {e}")
        
        await message.answer(
            f"✅ Промокод `{code}` создан и отправлен {success_count} пользователям!",
            reply_markup=admin_keyboard.get_admin_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Ошибка при создании промокода. Возможно, такой код уже существует.")
    
    await state.clear()


@router.callback_query(F.data == "admin_withdrawals", is_admin)
async def admin_withdrawals(callback: types.CallbackQuery, db: Database):
    """Показывает заявки на вывод."""
    withdrawals = await db.get_pending_withdrawals()
    
    if not withdrawals:
        await callback.message.edit_text("💸 Нет ожидающих заявок на вывод", reply_markup=admin_keyboard.get_admin_keyboard())
        await callback.answer()
        return
    
    # Показываем первую заявку с кнопками действий
    w = withdrawals[0]
    user = await db.get_user(w['user_id'])
    username = user['username'] if user and user['username'] else 'Не указан'
    
    withdraw_text = f"💸 Заявка на вывод #{w['id']}\n\n"
    withdraw_text += f"Username: @{username}\n"
    withdraw_text += f"Сумма: {w['amount']} голдов\n"
    withdraw_text += f"Статус: {w['status']}\n"
    
    await callback.message.edit_text(withdraw_text, reply_markup=admin_keyboard.get_withdraw_action_keyboard(w['id']))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_approve_withdraw_"), is_admin)
async def admin_approve_withdraw(callback: types.CallbackQuery, db: Database):
    """Одобряет заявку на вывод."""
    withdraw_id = int(callback.data.split("_")[-1])
    
    success = await db.update_withdrawal_status(withdraw_id, "approved")
    
    if success:
        await callback.message.edit_text(f"✅ Заявка #{withdraw_id} одобрена", reply_markup=admin_keyboard.get_admin_keyboard())
    else:
        await callback.message.edit_text(f"❌ Ошибка при одобрении заявки #{withdraw_id}", reply_markup=admin_keyboard.get_admin_keyboard())
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin_reject_withdraw_"), is_admin)
async def admin_reject_withdraw(callback: types.CallbackQuery, state: FSMContext, db: Database):
    """Запрашивает причину отказа от заявки на вывод."""
    withdraw_id = int(callback.data.split("_")[-1])
    
    # Сохраняем ID заявки в состоянии
    await state.update_data(withdraw_id=withdraw_id)
    
    await callback.message.edit_text(f"💸 Введите причину отказа для заявки #{withdraw_id}:")
    await state.set_state(RejectionStates.waiting_reason)
    await callback.answer()


@router.message(RejectionStates.waiting_reason)
async def process_rejection_reason(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает причину отказа и уведомляет пользователя."""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    reason = message.text.strip()
    data = await state.get_data()
    withdraw_id = data.get('withdraw_id')
    
    if not withdraw_id:
        await message.answer("❌ Ошибка: ID заявки не найден")
        await state.clear()
        return
    
    # Получаем информацию о заявке
    withdrawals = await db.get_pending_withdrawals()
    w = next((x for x in withdrawals if x['id'] == withdraw_id), None)
    
    if w:
        # Возвращаем голды на баланс пользователя
        await db.update_balance(w['user_id'], w['amount'])
        
        # Отправляем уведомление пользователю
        try:
            await message.bot.send_message(
                w['user_id'],
                f"❌ Ваша заявка на вывод {w['amount']} голдов отклонена.\n\nПричина: {reason}"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
    
    success = await db.update_withdrawal_status(withdraw_id, "rejected")
    
    if success:
        await message.answer(f"✅ Заявка #{withdraw_id} отклонена. Голды возвращены пользователю. Уведомление отправлено.", reply_markup=admin_keyboard.get_admin_keyboard())
    else:
        await message.answer(f"❌ Ошибка при отклонении заявки #{withdraw_id}", reply_markup=admin_keyboard.get_admin_keyboard())
    
    await state.clear()


@router.message(Command("broadcast"))
async def cmd_manual_broadcast(message: types.Message, db: Database):
    """Ручная рассылка сообщения."""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("Использование: /broadcast <текст сообщения>")
        return
    
    broadcast_text = args[1]
    users = await db.get_all_users()
    
    success_count = 0
    for user in users:
        try:
            await message.bot.send_message(user['user_id'], broadcast_text)
            success_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user['user_id']}: {e}")
    
    await message.answer(f"✅ Рассылка отправлена {success_count} из {len(users)} пользователей")
