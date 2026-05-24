import asyncio
import logging
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from database import Database
from services.promo_parser import PromoParser


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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


# Инициализация компонентов
bot = Bot(token=settings.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()
db = Database(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
promo_parser = PromoParser()


# Middleware для проверки подписки на канал
async def check_subscription_middleware(handler, event, data):
    """Проверяет подписку пользователя на канал перед выполнением команд."""
    # Пропускаем проверку для админа
    if event.from_user.id == settings.ADMIN_ID:
        return await handler(event, data)
    
    # Проверяем подписку через Telegram API
    try:
        member = await bot.get_chat_member(settings.REQUIRED_CHANNEL_ID, event.from_user.id)
        is_subscribed = member.status in ["member", "administrator", "creator"]
        
        # Обновляем статус в базе данных
        await db.set_user_subscribed(event.from_user.id, is_subscribed)
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        is_subscribed = False
    
    if not is_subscribed:
        # Показываем сообщение о подписке для всех команд
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")]
        ])
        
        if hasattr(event, 'message'):
            await bot.send_message(
                event.from_user.id,
                f"📢 Для использования бота необходимо подписаться на канал {settings.REQUIRED_CHANNEL_ID}",
                reply_markup=keyboard
            )
        else:
            await bot.send_message(
                event.from_user.id,
                f"📢 Для использования бота необходимо подписаться на канал {settings.REQUIRED_CHANNEL_ID}",
                reply_markup=keyboard
            )
        return
    
    return await handler(event, data)


dp.message.middleware(check_subscription_middleware)
dp.callback_query.middleware(check_subscription_middleware)


async def check_promocodes():
    """Фоновая задача для проверки новых промокодов."""
    try:
        logger.info("Запуск проверки промокодов...")
        promocodes = await promo_parser.fetch_promocodes(settings.SITE_URL)
        
        if promocodes:
            for promo_data in promocodes:
                if isinstance(promo_data, tuple):
                    code, activation_count = promo_data
                else:
                    code = promo_data
                    activation_count = None
                
                success = await db.add_promocode(
                    code=code,
                    description="Автоматически найденный промокод",
                    source_url=settings.SITE_URL,
                    activation_count=activation_count
                )
                if success:
                    logger.info(f"Добавлен новый промокод: {code}")
                    
                    # Отправка уведомления всем пользователям
                    users = await db.get_all_users()
                    next_promo = get_next_promocode_time()
                    activation_text = f"\nАктиваций: {activation_count}" if activation_count else ""
                    for user in users:
                        try:
                            await bot.send_message(
                                user['user_id'],
                                f"🎉 НОВЫЙ ПРОМОКОД\n`{code}`{activation_text}\n\nСледующий промокод в {next_promo} (МСК)",
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logger.warning(f"Не удалось отправить сообщение пользователю {user['user_id']}: {e}")
                    
                    # Отправка уведомления админу
                    await bot.send_message(
                        settings.ADMIN_ID,
                        f"🎉 НОВЫЙ ПРОМОКОД\n`{code}`{activation_text}\n\nОтправлено {len(users)} пользователям\n\nСледующий промокод в {next_promo} (МСК)",
                        parse_mode="Markdown"
                    )
        else:
            logger.info("Новых промокодов не найдено")
            
    except Exception as e:
        logger.error(f"Ошибка при проверке промокодов: {e}")


async def check_referral_rewards():
    """Проверяет и начисляет награды за рефералов."""
    try:
        users = await db.get_all_users()
        
        for user in users:
            if user['referral_count'] >= settings.REFERRAL_THRESHOLD:
                # Начисляем награду (можно добавить логику для предотвращения повторного начисления)
                await db.update_balance(user['user_id'], settings.REFERRAL_REWARD_GOLDS)
                logger.info(f"Начислено {settings.REFERRAL_REWARD_GOLDS} голдов пользователю {user['user_id']}")
                
    except Exception as e:
        logger.error(f"Ошибка при проверке реферальных наград: {e}")


async def on_startup():
    """Действия при запуске бота."""
    logger.info("Запуск бота...")
    
    # Подключение к базе данных
    await db.connect()
    
    # Настройка планировщика
    scheduler.add_job(
        check_promocodes,
        CronTrigger(minute='36-50', hour='1,3,5,7,9,11,13,15,17,19,21,23'),
        id='check_promocodes',
        replace_existing=True
    )
    
    scheduler.add_job(
        check_referral_rewards,
        CronTrigger(hour='*/1'),  # Каждые 1 часов
        id='check_referral_rewards',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Планировщик задач запущен")


async def on_shutdown():
    """Действия при остановке бота."""
    logger.info("Остановка бота...")
    
    # Остановка планировщика
    scheduler.shutdown()
    
    # Закрытие соединения с БД
    await db.close()
    
    # Закрытие сессии бота
    await bot.session.close()


async def main():
    """Главная функция запуска бота."""
    # Регистрация обработчиков
    from handlers import user_handlers, admin_handlers, callback_handlers
    
    # Middleware для внедрения зависимостей
    async def db_middleware(handler, event, data):
        data["db"] = db
        return await handler(event, data)
    
    dp.update.outer_middleware(db_middleware)
    
    # Регистрация роутеров
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(callback_handlers.router)
    
    # Запуск поллинга
    await dp.start_polling(
        bot,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
