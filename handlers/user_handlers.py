from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta, timezone
import logging

from database import Database
from keyboards import user_keyboard
from config import settings

logger = logging.getLogger(__name__)
router = Router()
bot = Bot(token=settings.BOT_TOKEN)


async def check_subscription(user_id: int, db: Database) -> bool:
    """Проверяет подписку пользователя на канал."""
    try:
        # Проверяем подписку через Telegram API
        member = await bot.get_chat_member(settings.REQUIRED_CHANNEL_ID, user_id)
        is_subscribed = member.status in ["member", "administrator", "creator"]
        
        # Обновляем статус в базе данных
        await db.set_user_subscribed(user_id, is_subscribed)
        
        return is_subscribed
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        return False


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery, db: Database):
    """Обработчик кнопки проверки подписки."""
    user_id = callback.from_user.id
    
    is_subscribed = await check_subscription(user_id, db)
    
    if is_subscribed:
        await callback.message.edit_text("✅ Вы подписаны на канал! Теперь вы можете пользоваться ботом.")
        await callback.answer()
    else:
        await callback.message.edit_text(f"❌ Вы не подписаны на канал {settings.REQUIRED_CHANNEL_ID}. Пожалуйста, подпишитесь и нажмите кнопку снова.")
        await callback.answer()


class WithdrawalStates(StatesGroup):
    """Состояния для процесса вывода голдов."""
    waiting_amount = State()


class PromoInputStates(StatesGroup):
    """Состояния для ввода промокода."""
    waiting_code = State()


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


@router.message(CommandStart())
async def cmd_start(message: types.Message, db: Database):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Проверка реферальной ссылки
    args = message.text.split()
    referred_by = None
    if len(args) > 1:
        try:
            referred_by = int(args[1])
        except ValueError:
            pass
    
    # Добавление пользователя в БД
    await db.add_user(user_id, username, referred_by)
    
    # Формирование сообщения приветствия
    bot_info = await message.bot.get_me()
    welcome_text = f"""
👋 Привет, {message.from_user.first_name}!

Я бот для мониторинга игровых промокодов.

📌 Мои возможности:
• 🔔 Автоматическая рассылка новых промокодов
• 👥 Реферальная система с наградами
• 💰 Система профиля с балансом
• 🎁 Получение голдов за приглашения

🔗 Твоя реферальная ссылка:
https://t.me/{bot_info.username}?start={user_id}

За каждые {settings.REFERRAL_THRESHOLD} приглашений ты получишь {settings.REFERRAL_REWARD_GOLDS} голдов!
"""
    
    await message.answer(
        welcome_text,
        reply_markup=user_keyboard.get_main_keyboard()
    )
    
    logger.info(f"Пользователь {user_id} запустил бота")


@router.message(Command("profile"))
async def cmd_profile(message: types.Message, db: Database):
    """Обработчик команды /profile."""
    user_id = message.from_user.id
    
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Профиль не найден. Нажмите /start для регистрации.")
        return
    
    profile_text = f"""
👤 Твой профиль

🆔 ID: {user['user_id']}
👤 Username: @{user['username'] or 'Не указан'}
💰 Баланс: {user['balance']} голдов
👥 Приглашено: {user['referral_count']} пользователей
📅 Регистрация: {user['created_at']}

🎁 До следующей награды: {settings.REFERRAL_THRESHOLD - (user['referral_count'] % settings.REFERRAL_THRESHOLD)} приглашений
"""
    
    await message.answer(
        profile_text,
        reply_markup=user_keyboard.get_profile_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help."""
    help_text = """
📖 Справка

Доступные команды:
/start - Запуск бота / Регистрация
/profile - Просмотр профиля
/promo <код> - Активировать промокод бота
/help - Эта справка

Реферальная система:
• Поделись своей реферальной ссылкой
• За каждые 10 приглашений получи 10 голдов
• Голды можно использовать для вывода

Промокоды:
• Бот автоматически проверяет новые промокоды с сайта каждые 2 часа
• Новые промокоды приходят в канал и уведомлениям
• Используйте /promo <код> для активации промокодов бота

Поддержка:
Если у вас есть вопросы, обращайтесь к админу: @admin
"""
    
    await message.answer(help_text)


@router.message(Command("promo"))
async def cmd_promo(message: types.Message, db: Database):
    """Обработчик команды /promo для активации промокода бота."""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("Использование: /promo <код>")
        return
    
    code = args[1].strip().upper()
    user_id = message.from_user.id
    
    # Получаем промокод
    promo = await db.get_bot_promocode(code)
    
    if not promo:
        await message.answer("❌ Промокод не найден или неактивен")
        return
    
    # Проверяем, использовал ли пользователь этот промокод
    if await db.has_user_used_promo(user_id, promo['id']):
        await message.answer("❌ Вы уже использовали этот промокод")
        return
    
    # Проверяем лимит использований
    usage_count = await db.get_promo_usage_count(promo['id'])
    if promo['usage_limit'] and usage_count >= promo['usage_limit']:
        await message.answer("❌ Промокод достиг лимита использований")
        return
    
    # Начисляем награду
    await db.update_balance(user_id, promo['gold_reward'])
    await db.use_bot_promocode(user_id, promo['id'])
    
    await message.answer(f"🎉 Промокод активирован! Вы получили {promo['gold_reward']} голдов!")


@router.callback_query(F.data == "profile_promo")
async def button_profile_promo(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки Ввести промокод в профиле."""
    await callback.message.edit_text("🎁 Введите код промокода:")
    await state.set_state(PromoInputStates.waiting_code)
    await callback.answer()


@router.message(PromoInputStates.waiting_code)
async def process_promo_code_input(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает ввод кода промокода из профиля."""
    code = message.text.strip().upper()
    user_id = message.from_user.id
    
    # Получаем промокод
    promo = await db.get_bot_promocode(code)
    
    if not promo:
        await message.answer("❌ Промокод не найден или неактивен")
        await state.clear()
        return
    
    # Проверяем, использовал ли пользователь этот промокод
    if await db.has_user_used_promo(user_id, promo['id']):
        await message.answer("❌ Вы уже использовали этот промокод")
        await state.clear()
        return
    
    # Проверяем лимит использований
    usage_count = await db.get_promo_usage_count(promo['id'])
    if promo['usage_limit'] and usage_count >= promo['usage_limit']:
        await message.answer("❌ Промокод достиг лимита использований")
        await state.clear()
        return
    
    # Начисляем награду
    await db.update_balance(user_id, promo['gold_reward'])
    await db.use_bot_promocode(user_id, promo['id'])
    
    await message.answer(f"🎉 Промокод активирован! Вы получили {promo['gold_reward']} голдов!")
    await state.clear()


@router.message(F.text == "👤 Профиль")
async def button_profile(message: types.Message, db: Database):
    """Обработчик кнопки Профиль."""
    await cmd_profile(message, db)


@router.message(F.text == "🔄 Обновить промокод")
async def button_update_promo(message: types.Message, db: Database):
    """Обработчик кнопки Обновить промокод - проверяет сайт в реальном времени."""
    from services.promo_parser import PromoParser
    
    await message.answer("🔄 Проверяю промокоды на сайте...")
    
    try:
        promo_parser = PromoParser()
        promocodes = await promo_parser.fetch_promocodes(settings.SITE_URL)
        
        if promocodes:
            # Получаем последний промокод из базы для сравнения
            all_promos = await db.get_all_promocodes()
            last_db_code = all_promos[-1]['code'] if all_promos else None
            
            # Добавляем новые промокоды в БД (только если они отличаются от последнего)
            new_count = 0
            latest_code = None
            latest_activation = None
            for promo_data in promocodes:
                if isinstance(promo_data, tuple):
                    code, activation_count = promo_data
                else:
                    code = promo_data
                    activation_count = None
                
                # Добавляем только если код отличается от последнего в базе
                if code != last_db_code:
                    success = await db.add_promocode(
                        code=code,
                        description="Автоматически найденный промокод",
                        source_url=settings.SITE_URL,
                        activation_count=activation_count
                    )
                    if success:
                        new_count += 1
                        latest_code = code
                        latest_activation = activation_count
                else:
                    # Если код совпадает, обновляем количество активаций
                    if activation_count:
                        await db.update_promocode_activation_count(code, activation_count)
                    latest_code = code
                    latest_activation = activation_count
            
            # Показываем промокод с реальным количеством активаций с сайта
            next_promo = get_next_promocode_time()
            activation_text = f"\nАктиваций: {latest_activation}" if latest_activation else ""
            promo_text = f"🎁 Последний промокод:\n\n`{latest_code}`{activation_text}\n\nСледующий промокод в {next_promo} (МСК)"
            
            if new_count > 0:
                promo_text = f"✅ Найден новый промокод!\n\n" + promo_text
            
            await message.answer(promo_text, parse_mode="Markdown")
        else:
            next_promo = get_next_promocode_time()
            await message.answer(f"🎁 Промокодов на сайте не найдено.\n\nСледующий промокод в {next_promo} (МСК)")
    except Exception as e:
        logger.error(f"Ошибка при проверке промокодов: {e}")
        next_promo = get_next_promocode_time()
        await message.answer(f"❌ Ошибка при проверке сайта. Попробуйте позже.\n\nСледующий промокод в {next_promo} (МСК)")


@router.message(F.text == "🎁 Ежедневный бонус")
async def button_daily_bonus(message: types.Message, db: Database):
    """Обработчик кнопки Ежедневный бонус."""
    user_id = message.from_user.id
    
    # Проверяем, получал ли пользователь сегодня бонус
    can_get_bonus = await db.can_get_daily_bonus(user_id)
    
    if not can_get_bonus:
        await message.answer("🎁 Вы уже получили ежедневный бонус сегодня. Приходите завтра!")
        return
    
    # Начисляем бонус
    await db.update_balance(user_id, settings.DAILY_BONUS_AMOUNT)
    await db.record_daily_bonus(user_id)
    
    await message.answer(f"🎉 Вы получили {settings.DAILY_BONUS_AMOUNT} голдов в качестве ежедневного бонуса!")


@router.message(F.text == "💰 Вывести голды")
async def button_withdraw(message: types.Message, state: FSMContext, db: Database):
    """Обработчик кнопки Вывести голды."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Профиль не найден. Нажмите /start для регистрации.")
        return
    
    if user['balance'] <= 0:
        await message.answer("❌ У вас недостаточно голдов для вывода.")
        return
    
    await message.answer(
        "💸 Вывод голдов\n\nВведите сумму для вывода:"
    )
    await state.set_state(WithdrawalStates.waiting_amount)


@router.message(WithdrawalStates.waiting_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext, db: Database):
    """Обработчик ввода суммы для вывода."""
    try:
        amount = int(message.text)
        if amount < 1000:
            await message.answer("❌ Минимальная сумма вывода: 1000 голдов. Попробуйте снова:")
            return
        
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        
        if amount > user['balance']:
            await message.answer(f"❌ У вас недостаточно голдов. Ваш баланс: {user['balance']}. Попробуйте снова:")
            return
        
        # Создаем заявку на вывод без кошелька
        success = await db.create_withdrawal_request(user_id, amount)
        
        if success:
            # Списываем голды с баланса
            await db.update_balance(user_id, -amount)
            
            await message.answer("✅ Запрос отправлен администрации")
            await state.clear()
        else:
            await message.answer("❌ Ошибка при создании заявки. Попробуйте позже.")
            await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число:")
