# Telegram Promo Code Bot

Профессиональный Telegram-бот на aiogram 3.x для мониторинга и рассылки игровых промокодов с Clean Architecture.

## 🏗️ Архитектура проекта

```
bot tg/
├── main.py                 # Точка входа
├── config.py              # Конфигурация (pydantic-settings)
├── database.py            # Работа с БД (aiosqlite)
├── .env                   # Секретные данные
├── .env.example           # Пример конфигурации
├── requirements.txt       # Зависимости
├── services/              # Модуль парсинга
│   ├── __init__.py
│   └── promo_parser.py    # Playwright для обхода Cloudflare
├── handlers/              # Обработчики сообщений
│   ├── __init__.py
│   ├── user_handlers.py   # Команды пользователей
│   ├── admin_handlers.py  # Админ-команды
│   └── callback_handlers.py  # Callback-обработчики
└── keyboards/             # Инлайн-клавиатуры
    ├── __init__.py
    ├── user_keyboard.py  # Клавиатуры пользователей
    └── admin_keyboard.py  # Админ-клавиатуры
```

## 🚀 Установка и настройка

### 1. Клонирование и установка зависимостей

```bash
# Создайте виртуальное окружение
python -m venv venv

# Активируйте виртуальное окружение
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

### 2. Установка Playwright

```bash
# Установка браузеров Playwright
playwright install chromium
```

### 3. Настройка .env файла

Скопируйте `.env.example` в `.env` и заполните своими данными:

```bash
cp .env.example .env
```

Заполните переменные в `.env`:
- `BOT_TOKEN` - токен вашего Telegram-бота (от @BotFather)
- `CHANNEL_ID` - ID вашего канала (например, @channelname)
- `CHANNEL_URL` - ссылка на канал
- `SITE_URL` - URL сайта для парсинга промокодов
- `ADMIN_ID` - ваш Telegram ID (для админ-панели)
- `DATABASE_URL` - путь к базе данных (по умолчанию sqlite+aiosqlite:///bot.db)

### 4. Запуск бота

```bash
python main.py
```

## 📋 Функционал

### Автоматический мониторинг
- Проверка промокодов каждые 2 часа (cron: :26 минут)
- Обход Cloudflare с помощью Playwright
- Автоматическое сохранение новых промокодов в БД
- Уведомления админа о новых промокодах

### Админ-панель
- Команда `/admin` для доступа к панели
- Статистика бота
- Ручная рассылка сообщений
- Управление промокодами
- Обработка заявок на вывод

### Реферальная система
- Уникальная реферальная ссылка для каждого пользователя
- Начисление 10 голдов за каждые 10 приглашений
- Отслеживание статистики приглашений

### Система профиля
- Баланс пользователя
- Статистика приглашений
- Кнопка вывода голдов
- Заявки на вывод с обработкой админом

## 🔧 Playwright в асинхронном режиме

Для обхода Cloudflare используется Playwright с асинхронным режимом:

```python
from playwright.async_api import async_playwright

async def fetch_promocodes(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        context = await browser.new_context(
            user_agent='Mozilla/5.0 ...',
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)  # Ожидание Cloudflare
        
        content = await page.content()
        # Парсинг промокодов...
        
        await context.close()
        await browser.close()
```

**Ключевые моменты для обхода защиты:**
1. Использование реального User-Agent
2. Отключение флага webdriver
3. Ожидание полной загрузки страницы (`networkidle`)
4. Дополнительная задержка для Cloudflare (5 секунд)
5. Настройки браузера для избежания детекции

## 📝 Команды бота

### Пользовательские команды
- `/start` - Запуск бота / Регистрация
- `/profile` - Просмотр профиля
- `/help` - Справка

### Админ-команды
- `/admin` - Панель администратора
- `/broadcast <текст>` - Ручная рассылка

## 🔒 Безопасность

- Все секретные данные хранятся в `.env`
- Использование pydantic-settings для валидации конфигурации
- Проверка прав администратора для админ-команд
- `.env` добавлен в `.gitignore`

## 🛠️ Масштабирование

Проект построен по принципу Clean Architecture для легкого масштабирования:

### Добавление новых обработчиков
Создайте новый файл в `handlers/` и зарегистрируйте роутер в `main.py`:

```python
from handlers import new_handlers
dp.include_router(new_handlers.router)
```

### Добавление новых сервисов
Создайте новый файл в `services/` и импортируйте в нужных модулях.

### Расширение базы данных
Добавьте новые таблицы в метод `_create_tables()` в `database.py` и создайте соответствующие методы.

## 📦 Зависимости

- `aiogram==3.4.1` - Telegram Bot Framework
- `aiosqlite==0.19.0` - Асинхронная работа с SQLite
- `pydantic-settings==2.1.0` - Управление конфигурацией
- `python-dotenv==1.0.0` - Загрузка .env файлов
- `apscheduler==3.10.4` - Планировщик задач
- `playwright==1.40.0` - Браузерная автоматизация

## 🤝 Поддержка

Для вопросов и предложений обращайтесь к администратору бота.
