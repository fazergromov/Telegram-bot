from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Конфигурация приложения с использованием pydantic-settings."""
    
    # Telegram Bot
    BOT_TOKEN: str
    CHANNEL_ID: str
    CHANNEL_URL: str
    ADMIN_ID: int
    REQUIRED_CHANNEL_ID: str = "@fazersk"
    
    # Target Site
    SITE_URL: str
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///bot.db"
    
    # Scheduler
    CHECK_INTERVAL_HOURS: int = 2
    CRON_MINUTE: str = "36"
    
    # Referral System
    REFERRAL_REWARD_GOLDS: int = 10
    REFERRAL_THRESHOLD: int = 10
    
    # Daily Bonus
    DAILY_BONUS_AMOUNT: int = 200
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


# Глобальный экземпляр настроек
settings = Settings()