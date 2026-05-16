import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext


class TTLCache:
      def __init__(self, ttl: int = 3600):
                self._cache = {}
                self._ttl = ttl

      def get(self, key: str):
                if key in self._cache:
                              val, ts = self._cache[key]
                              if time.time() - ts < self._ttl:
                                                return val
                                            del self._cache[key]
                          return None

    def set(self, key: str, val):
              self._cache[key] = (val, time.time())

    def clear(self):
              self._cache.clear()


USER_AGENTS = [
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class BaseScraper(ABC):
      RETRY_LIMIT = 3
      RETRY_MIN = 2
      RETRY_MAX = 6
      cache = TTLCache(ttl=3600)

    def __init__(self, headless: bool = True):
              self.headless = headless
              self.logger = logger.bind(scraper=self.__class__.__name__)

    def _random_ua(self) -> str:
              return random.choice(USER_AGENTS)

    async def get_page_html(
              self,
              url: str,
              wait_selector: Optional[str] = None,
              timeout: int = 30000,
              extra_headers: Optional[dict] = None
    ) -> str:
              cached = self.cache.get(url)
              if cached:
                            self.logger.debug(f"Cache hit: {url[:60]}")
                            return cached

              for attempt in range(1, self.RETRY_LIMIT + 1):
                            try:
                                              async with async_playwright() as p:
                                                                    browser: Browser = await p.chromium.launch(
                                                                                              headless=self.headless,
                                                                                              args=[
                                                                                                                            "--no-sandbox",
                                                                                                                            "--disable-blink-features=AutomationControlled",
                                                                                                                            "--disable-dev-shm-usage",
                                                                                                                            "--disable-setuid-sandbox",
                                                                                                ]
                                                                    )
                                                                    ctx: BrowserContext = await browser.new_context(
                                                                        user_agent=self._random_ua(),
                                                                        viewport={"width": 1366, "height": 768},
                                                                        locale="en-IN",
                                                                        timezone_id="Asia/Kolkata",
                                                                        extra_http_headers=extra_headers or {},
                                                                    )
                                                                    await ctx.add_init_script("""
                                                                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                                                                        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
                                                                    """)
                                                                    page = await ctx.new_page()
                                                                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                                                                    if wait_selector:
                                                                                              try:
                                                                                                                            await page.wait_for_selector(wait_selector, timeout=15000)
                                                                      except Exception:
                                                                            self.logger.warning(f"Selector not found: {wait_selector}")
                                                                                            await asyncio.sleep(random.uniform(1.0, 2.5))
                                                                                            html = await page.content()
                                                                                            await browser.close()
                                                                                            self.cache.set(url, html)
                                                                                            return html
except Exception as e:
                self.logger.warning(f"Attempt {attempt}/{self.RETRY_LIMIT} failed for {url[:60]}: {e}")
                if attempt < self.RETRY_LIMIT:
                                      await asyncio.sleep(random.uniform(self.RETRY_MIN, self.RETRY_MAX))
                          raise RuntimeError(f"All {self.RETRY_LIMIT} retries failed for {url}")

    @abstractmethod
    async def scrape(self, *args, **kwargs) -> dict:
              pass
