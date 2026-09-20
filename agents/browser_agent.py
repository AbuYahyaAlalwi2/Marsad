"""
وكيل المتصفح — تشغيل Playwright/Selenium للتسجيل الفعلي
"""
import os
import time
import random
from db import log_event

# محاولة استيراد Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# محاولة استيراد Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium_stealth import stealth
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class BrowserAgent:
    """
    وكيل المتصفح للتسجيل الآلي الفعلي
    يدعم Playwright و Selenium
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.page = None
        self.driver = None

        log_event("browser_agent", {
            "status": "initialized",
            "playwright": PLAYWRIGHT_AVAILABLE,
            "selenium": SELENIUM_AVAILABLE
        })

    def launch(self, engine: str = "playwright"):
        """تشغيل المتصفح"""
        if engine == "playwright" and PLAYWRIGHT_AVAILABLE:
            return self._launch_playwright()
        elif engine == "selenium" and SELENIUM_AVAILABLE:
            return self._launch_selenium()
        else:
            log_event("browser_agent", {"error": "no_engine_available"})
            return False

    def _launch_playwright(self):
        """تشغيل Playwright مع stealth"""
        try:
            pw = sync_playwright().start()

            self.browser = pw.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-images',  # أسرع
                    '--disable-javascript',  # يمكن تفعيله عند الحاجة
                ]
            )

            context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                permissions=['geolocation'],
                color_scheme='dark',
            )

            # إخفاء علامات الأتمتة
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)

            self.page = context.new_page()

            log_event("browser_agent", {"engine": "playwright", "status": "launched"})
            return True

        except Exception as e:
            log_event("browser_agent_errors", {"error": str(e)})
            return False

    def _launch_selenium(self):
        """تشغيل Selenium مع stealth"""
        try:
            from selenium.webdriver.chrome.options import Options

            options = Options()
            if self.headless:
                options.add_argument('--headless=new')

            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-web-security')
            options.add_argument('--window-size=1920,1080')

            # User-Agent عشوائي
            from fake_useragent import UserAgent
            ua = UserAgent()
            options.add_argument(f'--user-agent={ua.random}')

            self.driver = webdriver.Chrome(options=options)

            # تطبيق stealth
            stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )

            log_event("browser_agent", {"engine": "selenium", "status": "launched"})
            return True

        except Exception as e:
            log_event("browser_agent_errors", {"error": str(e)})
            return False

    def navigate(self, url: str, wait_until: str = "networkidle"):
        """الانتقال لصفحة"""
        if self.page:
            self.page.goto(url, wait_until=wait_until, timeout=30000)
        elif self.driver:
            self.driver.get(url)
            time.sleep(3)

    def fill(self, selector: str, value: str):
        """ملء حقل"""
        if self.page:
            self.page.fill(selector, value)
        elif self.driver:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            element.clear()
            element.send_keys(value)

    def click(self, selector: str):
        """ضغط عنصر"""
        if self.page:
            self.page.click(selector)
        elif self.driver:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            element.click()

    def get_text(self, selector: str) -> str:
        """الحصول على نص"""
        if self.page:
            return self.page.text_content(selector) or ""
        elif self.driver:
            return self.driver.find_element(By.CSS_SELECTOR, selector).text
        return ""

    def wait_for_selector(self, selector: str, timeout: int = 10):
        """انتظار عنصر"""
        if self.page:
            self.page.wait_for_selector(selector, timeout=timeout * 1000)
        elif self.driver:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )

    def screenshot(self, path: str):
        """لقطة شاشة"""
        if self.page:
            self.page.screenshot(path=path)
        elif self.driver:
            self.driver.save_screenshot(path)

    def solve_captcha(self, site_key: str, url: str, api_key: str = None) -> str:
        """حل CAPTCHA باستخدام 2Captcha"""
        api_key = api_key or os.environ.get("TWOCAPTCHA_API_KEY")

        if not api_key:
            log_event("browser_agent", {"error": "no_captcha_api_key"})
            return ""

        try:
            from twocaptcha import TwoCaptcha

            solver = TwoCaptcha(api_key)

            # reCAPTCHA
            result = solver.recaptcha(
                sitekey=site_key,
                url=url
            )

            return result.get('code', '')

        except Exception as e:
            log_event("browser_agent_errors", {"captcha_error": str(e)})
            return ""

    def human_type(self, selector: str, text: str, delay: tuple = (50, 150)):
        """كتابة بشرية (حرف بحرف)"""
        if self.page:
            element = self.page.locator(selector)
            element.click()

            for char in text:
                element.type(char, delay=random.randint(*delay))
        elif self.driver:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            element.clear()

            for char in text:
                element.send_keys(char)
                time.sleep(random.uniform(*delay) / 1000)

    def human_click(self, selector: str):
        """ضغط بشري (مع تحريك عشوائي)"""
        if self.page:
            # تحريك الماوس قبل الضغط
            box = self.page.locator(selector).bounding_box()
            if box:
                self.page.mouse.move(
                    box['x'] + box['width'] / 2 + random.randint(-5, 5),
                    box['y'] + box['height'] / 2 + random.randint(-5, 5),
                    steps=10
                )
                time.sleep(random.uniform(0.1, 0.3))

            self.page.click(selector)

        elif self.driver:
            from selenium.webdriver.common.action_chains import ActionChains

            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            ActionChains(self.driver).move_to_element(element).pause(
                random.uniform(0.1, 0.3)
            ).click().perform()

    def scroll_randomly(self, times: int = 3):
        """تمرير عشوائي (سلوك بشري)"""
        if self.page:
            for _ in range(times):
                self.page.mouse.wheel(0, random.randint(100, 500))
                time.sleep(random.uniform(0.5, 1.5))

        elif self.driver:
            for _ in range(times):
                self.driver.execute_script(
                    f"window.scrollBy(0, {random.randint(100, 500)});"
                )
                time.sleep(random.uniform(0.5, 1.5))

    def close(self):
        """إغلاق المتصفح"""
        if self.browser:
            self.browser.close()
        if self.driver:
            self.driver.quit()

        log_event("browser_agent", {"status": "closed"})

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# نسخة عامة
browser_agent = BrowserAgent()
