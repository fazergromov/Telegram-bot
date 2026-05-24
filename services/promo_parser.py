from playwright.async_api import async_playwright, Browser, Page
import logging
from typing import List, Optional
import re

logger = logging.getLogger(__name__)


class PromoParser:
    """Класс для парсинга промокодов с использованием Playwright."""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
    
    async def start_browser(self) -> None:
        """Запускает браузер Playwright."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        if not self.browser:
            # Запуск браузера с настройками для обхода Cloudflare
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
        
        logger.info("Браузер Playwright запущен")
    
    async def close_browser(self) -> None:
        """Закрывает браузер Playwright."""
        if self.browser:
            await self.browser.close()
            self.browser = None
        
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        logger.info("Браузер Playwright закрыт")
    
    async def fetch_promocodes(self, url: str) -> List[str]:
        """
        Парсит промокоды с указанного URL.
        
        Args:
            url: URL сайта для парсинга
            
        Returns:
            Список найденных промокодов
        """
        promocodes = []
        
        try:
            await self.start_browser()
            
            # Создание контекста и страницы
            context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            # Настройка обработки Cloudflare
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            logger.info(f"Переход на страницу: {url}")
            
            # Переход на страницу с ожиданием загрузки
            await page.goto(url, wait_until='networkidle', timeout=60000)
            
            # Дополнительное ожидание для обхода Cloudflare
            await page.wait_for_timeout(5000)
            
            # Получение содержимого страницы
            content = await page.content()
            
            # Поиск промокодов с помощью CSS селекторов
            # Промокод разделен на два span: prefix и body
            try:
                prefix_element = await page.query_selector('.promocode-copy__prefix')
                body_element = await page.query_selector('.promocode-copy__body')
                activation_element = await page.query_selector('.promocode-meta__value')
                
                if prefix_element and body_element:
                    prefix = await prefix_element.inner_text()
                    body = await body_element.inner_text()
                    if prefix and body:
                        promocode = f"{prefix}{body}"
                        activation_count = None
                        if activation_element:
                            activation_text = await activation_element.inner_text()
                            # Парсим текст типа "943/1000"
                            if '/' in activation_text:
                                activation_count = activation_text.strip()
                        promocodes.append((promocode, activation_count))
                        logger.info(f"Найден промокод: {promocode}, активаций: {activation_count}")
            except Exception as e:
                logger.warning(f"Ошибка при поиске промокода через селекторы: {e}")
            
            # Удаление дубликатов
            promocodes = list(set(promocodes))
            
            logger.info(f"Найдено промокодов: {len(promocodes)}")
            
            # Закрытие контекста
            await context.close()
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге промокодов: {e}")
        
        finally:
            await self.close_browser()
        
        return promocodes
    
    async def fetch_promocodes_with_selectors(self, url: str, selectors: List[str]) -> List[str]:
        """
        Парсит промокоды с использованием CSS-селекторов.
        
        Args:
            url: URL сайта для парсинга
            selectors: Список CSS-селекторов для поиска промокодов
            
        Returns:
            Список найденных промокодов
        """
        promocodes = []
        
        try:
            await self.start_browser()
            
            context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            logger.info(f"Переход на страницу: {url}")
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(5000)
            
            # Поиск промокодов по селекторам
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        if text and text.strip():
                            promocodes.append(text.strip())
                except Exception as e:
                    logger.warning(f"Ошибка при поиске по селектору {selector}: {e}")
            
            # Удаление дубликатов
            promocodes = list(set(promocodes))
            
            logger.info(f"Найдено промокодов: {len(promocodes)}")
            
            await context.close()
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге промокодов: {e}")
        
        finally:
            await self.close_browser()
        
        return promocodes
