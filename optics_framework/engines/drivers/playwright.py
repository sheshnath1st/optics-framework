from typing import Optional
from playwright.async_api import async_playwright, Page
from optics_framework.common.driver_interface import DriverInterface
from optics_framework.common.error import OpticsError, Code
from optics_framework.common.eventSDK import EventSDK
from optics_framework.common.logging_config import internal_logger, execution_logger
from optics_framework.common.async_utils import run_async


class Playwright(DriverInterface):
    DEPENDENCY_TYPE = "driver_sources"
    NAME = "playwright"


    def __init__(self, config: dict, event_sdk: Optional[EventSDK] = None):
        self.config = config or {}
        self.event_sdk = event_sdk

        self._pw = None
        self._browser = None
        self._context = None
        self.page: Optional[Page] = None

        internal_logger.info("[Playwright] Driver initialized")

    # =====================================================
    # APP / SESSION
    # =====================================================

    def launch_app(self, app_identifier=None, app_activity=None, event_name=None):
        return run_async(self._launch_app_async(app_identifier, event_name))

    async def _launch_app_async(self, app_identifier, event_name):
        try:
            internal_logger.info("[Playwright] Launching browser")

            self._pw = await async_playwright().start()

            browser = self.config.get("browser", "chromium")
            headless = self.config.get("headless", False)
            viewport = self.config.get("viewport", {"width": 1280, "height": 800})

            self._browser = await getattr(self._pw, browser).launch(headless=headless)
            self._context = await self._browser.new_context(viewport=viewport)
            self.page = await self._context.new_page()

            if app_identifier:
                execution_logger.info("[Playwright] Navigating to %s", app_identifier)
                await self.page.goto(app_identifier, timeout=60000)

            if event_name and self.event_sdk:
                self.event_sdk.capture_event(event_name)

            internal_logger.info("[Playwright] Application launched")
            return "PLAYWRIGHT_SESSION"

        except Exception as e:
            internal_logger.error("[Playwright] Launch failed", exc_info=True)
            raise OpticsError(Code.E0102, str(e), cause=e)

    def launch_other_app(self, app_name: str, event_name=None):
        return run_async(self._launch_app_async(app_name, event_name))

    def get_app_version(self) -> str:
        return "get_app_version not supported for Playwright"

    # =====================================================
    # PRESS / CLICK
    # =====================================================

    def press_element(self, element: str, repeat: int = 1, event_name=None):
        run_async(self._press_element_async(element, repeat, event_name))

    async def _press_element_async(self, element, repeat, event_name):
        # Handle both string selectors and Playwright locator objects
        if isinstance(element, str):
            locator = self.page.locator(element)
        else:
            # element is already a Playwright locator object
            locator = element
        await locator.wait_for(state="visible", timeout=15000)

        for _ in range(repeat):
            await locator.click(force=True)

        if event_name and self.event_sdk:
            self.event_sdk.capture_event(event_name)

    def press_coordinates(self, x: int, y: int, event_name=None):
        run_async(self.page.mouse.click(x, y))

    def press_percentage_coordinates(self, px, py, repeat=1, event_name=None):
        run_async(self._press_percentage_async(px, py, repeat))

    async def _press_percentage_async(self, px, py, repeat):
        vp = self.page.viewport_size
        x = int(vp["width"] * px / 100)
        y = int(vp["height"] * py / 100)
        for _ in range(repeat):
            await self.page.mouse.click(x, y)

    def press_keycode(self, keycode: str, event_name=None):
        """
        Press a keycode/key. Supports common keys like "Enter", "Tab", "Escape", etc.
        For Playwright, we use keyboard.press() which accepts key names.
        """
        # Map common keycode names to Playwright key names
        key_map = {
            "Enter": "Enter",
            "Return": "Enter",
            "Tab": "Tab",
            "Escape": "Escape",
            "Backspace": "Backspace",
            "Delete": "Delete",
            "Space": " ",
            "ArrowUp": "ArrowUp",
            "ArrowDown": "ArrowDown",
            "ArrowLeft": "ArrowLeft",
            "ArrowRight": "ArrowRight",
        }

        # Use mapped key or the keycode string directly (Playwright accepts key names)
        key = key_map.get(keycode, keycode)
        run_async(self.page.keyboard.press(key))

        if event_name and self.event_sdk:
            self.event_sdk.capture_event(event_name)

    # =====================================================
    # TEXT INPUT
    # =====================================================

    def enter_text(self, text: str, event_name=None):
        run_async(self.page.keyboard.type(text))

    def enter_text_using_keyboard(self, text: str, event_name=None):
        run_async(self.page.keyboard.type(text))

    def enter_text_element(self, element: str, text: str, event_name=None):
        run_async(self.page.locator(element).fill(text))

    def clear_text(self, event_name=None):
        run_async(self.page.keyboard.press("Control+A"))
        run_async(self.page.keyboard.press("Backspace"))

    def clear_text_element(self, element: str, event_name=None):
        run_async(self.page.locator(element).fill(""))

    # =====================================================
    # SCROLL / SWIPE
    # =====================================================

    def swipe(self, x, y, direction, swipe_length, event_name=None):
        delta = swipe_length if direction == "down" else -swipe_length
        run_async(self.page.mouse.wheel(0, delta))

    def swipe_percentage(self, x_per, y_per, direction, swipe_per, event_name=None):
        run_async(self._swipe_percentage_async(direction, swipe_per))

    async def _swipe_percentage_async(self, direction, swipe_per):
        vp = self.page.viewport_size
        delta = int(vp["height"] * swipe_per / 100)
        if direction != "down":
            delta = -delta
        await self.page.mouse.wheel(0, delta)

    def swipe_element(self, element: str, direction: str, swipe_length: int, event_name=None):
        """
        Playwright-safe swipe_element:
        Translates swipe into scroll on the element's nearest scrollable container.
        """

        if not self.page:
            raise RuntimeError("Playwright page not initialized")

        # 🔒 Web rule: swipe == scroll
        try:
            run_async(
                self._swipe_element_async(
                    element=element,
                    direction=direction,
                    swipe_length=swipe_length
                )
            )
        except Exception as e:
            raise RuntimeError(
                f"swipe_element failed for Playwright. "
                f"Use scroll_from_element instead. Root cause: {e}"
            ) from e

    async def _swipe_element_async(self, element: str, direction: str, swipe_length: int):
        locator = self.page.locator(element)
        await locator.wait_for(state="visible", timeout=10000)

        # Calculate scroll delta
        delta = swipe_length if direction == "down" else -swipe_length

        # Scroll nearest scrollable parent
        await locator.evaluate(
            """(el, delta) => {
                let node = el;
                while (node) {
                    if (node.scrollHeight > node.clientHeight) {
                        node.scrollBy(0, delta);
                        return;
                    }
                    node = node.parentElement;
                }
                window.scrollBy(0, delta);
            }""",
            delta
        )

    # def scroll(self, direction: str, duration: int, event_name=None):
    #     delta = duration if direction == "down" else -duration
    #     execution_logger.debug(
    #             "[Playwright] scroll direction=%s pixels=%d",
    #             direction, delta
    #         )
    #     run_async(self.page.mouse.wheel(0, delta))

    def scroll(self, direction: str = "down", pixels: int = 120, event_name=None):
        for _ in range(2):
            run_async(self.page.mouse.wheel(0, pixels if direction == "down" else -pixels))
            run_async(self.page.wait_for_timeout(120))

    # def scroll(self, direction: str, pixels: int, event_name=None):
    #     execution_logger.debug(
    #         "[Playwright] scroll direction=%s pixels=%d",
    #         direction, pixels
    #     )
    #     run_async(self._scroll_async(direction, pixels))

    # async def _scroll_async(self, direction: str, pixels: int):
    #     if direction == "down":
    #         await self.page.evaluate(
    #             "(p) => window.scrollBy(0, p)", pixels
    #         )
    #     else:
    #         await self.page.evaluate(
    #             "(p) => window.scrollBy(0, -p)", pixels
    #         )

    # =====================================================
    # GETTERS / TERMINATION
    # =====================================================

    def get_text_element(self, element: str) -> str:
        return run_async(self.page.locator(element).inner_text())

    def force_terminate_app(self, app_name: str, event_name=None):
        raise NotImplementedError("force_terminate_app not supported")

    def terminate(self):
        run_async(self._terminate_async())

    async def _terminate_async(self):
        internal_logger.info("[Playwright] Terminating session")

        if self.page:
            await self.page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    def get_driver_session_id(self):
        return None
