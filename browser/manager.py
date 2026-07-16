import os
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from log.logger import LoggerUtil

logger = LoggerUtil.get_logger()


class BrowserManager:
    """Playwright 浏览器管理器（全局单例）"""

    _instance = None
    _playwright = None
    _browser = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._context = None
            self._page = None
            self._headless = False
            self._initialized = True

    def launch(self, headless=False, slow_mo=100):
        """启动浏览器"""
        if self._browser:
            return self._browser
        self._headless = headless
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=headless,
                slow_mo=slow_mo,
                args=['--start-maximized']
            )
            logger.info(f"浏览器已启动，headless={headless}")
            return self._browser
        except Exception as e:
            logger.error(f"浏览器启动失败: {str(e)}")
            raise

    def new_context(self, **kwargs):
        """创建新的浏览器上下文（类似隐身窗口）"""
        if not self._browser:
            self.launch()
        self._context = self._browser.new_context(
            no_viewport=True,
            **kwargs
        )
        return self._context

    def new_page(self):
        """创建新页面"""
        if not self._context:
            self.new_context()
        self._page = self._context.new_page()
        return self._page

    def get_page(self):
        """获取当前页面"""
        return self._page

    def close_page(self):
        """关闭当前页面"""
        if self._page:
            self._page.close()
            self._page = None

    def close_context(self):
        """关闭当前上下文"""
        if self._context:
            self._context.close()
            self._context = None
            self._page = None

    def close_browser(self):
        """关闭浏览器"""
        self.close_context()
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        logger.info("浏览器已关闭")

    def is_running(self):
        """检查浏览器是否运行中"""
        return self._page is not None and not self._page.is_closed()


# 全局实例
browser_manager = BrowserManager()
