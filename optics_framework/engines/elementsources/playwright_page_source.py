import time
from typing import Optional, Any, Tuple, List
from lxml import etree  # type: ignore

from optics_framework.common.logging_config import internal_logger
from optics_framework.common.elementsource_interface import ElementSourceInterface
from optics_framework.common.error import OpticsError, Code
from optics_framework.common import utils


PLAYWRIGHT_NOT_INITIALISED_MSG = (
    "Playwright driver is not initialized for PlaywrightPageSource."
)


class PlaywrightPageSource(ElementSourceInterface):
    """
    Playwright Page Source Element Source
    """
    REQUIRED_DRIVER_TYPE = "playwright"

    def __init__(self, driver: Optional[Any] = None):
        # 🔑 DO NOT validate here
        self.driver = driver
        self.page = None
        self.tree = None
        self.root = None

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------

    def _require_page(self):
        internal_logger.debug(
            "[PlaywrightPageSource] driver=%s, has_page=%s",
            self.driver,
            hasattr(self.driver, "page") if self.driver else False
        )

        if self.driver is None or not hasattr(self.driver, "page"):
            internal_logger.error(PLAYWRIGHT_NOT_INITIALISED_MSG)
            raise OpticsError(Code.E0101, message=PLAYWRIGHT_NOT_INITIALISED_MSG)

        self.page = self.driver.page
        return self.page

    # ---------------------------------------------------------
    # Required interface methods
    # ---------------------------------------------------------

    def capture(self):
        internal_logger.exception(
            "PlaywrightPageSource does not support screen capture."
        )
        raise NotImplementedError(
            "PlaywrightPageSource does not support screen capture."
        )

    def get_page_source(self) -> Tuple[str, str]:
        """
        Returns full DOM HTML and timestamp
        """
        page = self._require_page()
        timestamp = utils.get_timestamp()

        html = page.content()
        self.tree = etree.HTML(html)
        self.root = self.tree

        internal_logger.debug(
            "========== PLAYWRIGHT PAGE SOURCE FETCHED =========="
        )
        internal_logger.debug("Timestamp: %s", timestamp)

        return html, timestamp

    def get_interactive_elements(self) -> List[Any]:
        """
        Return clickable / interactive elements
        """
        page = self._require_page()
        return page.query_selector_all(
            "a, button, input, textarea, select, [role='button']"
        )

    # ---------------------------------------------------------
    # Element location
    # ---------------------------------------------------------

    def locate(self, element: str, index: Optional[int] = None) -> Any:
        page = self._require_page()

        # -------------------------------------------------
        # 🔑 Resolve Optics element name → selector
        # -------------------------------------------------
        original_element = element

        if hasattr(self.driver, "optics") and self.driver.optics:
            resolved = self.driver.optics.get_element_value(element)
            if resolved:
                element = resolved[0]
                internal_logger.debug(
                    "[PlaywrightLocate] Resolved element '%s' → '%s'",
                    original_element, element
                )
            else:
                internal_logger.debug(
                    "[PlaywrightLocate] Using raw selector '%s'",
                    element
                )

        element_type = utils.determine_element_type(element)

        try:
            # -------------------------------------------------
            # Selector strategy
            # -------------------------------------------------
            if element_type == "Text":
                locator = page.get_by_text(element, exact=False)
            elif element_type == "XPath":
                locator = page.locator(f"xpath={element}")
            else:
                locator = page.locator(element)  # CSS

            if index is not None:
                locator = locator.nth(index)

            count = locator.count()
            internal_logger.debug(
                "[PlaywrightLocate] Locator '%s' found %d elements",
                element, count
            )

            if count == 0:
                return None

            return locator.first

        except Exception as e:
            internal_logger.error(
                "[PlaywrightLocate] Error locating element '%s' (resolved='%s')",
                original_element,
                element,
                exc_info=True
            )
            raise OpticsError(
                Code.E0201,
                message=f"No elements found for: {original_element}",
                cause=e,
            ) from e

    # ---------------------------------------------------------
    # Assertions
    # ---------------------------------------------------------

    def assert_elements(self, elements, timeout=30, rule="any"):
        """
        Assert the presence of elements on the current page (Playwright).

        Args:
            elements (list | str): List of selectors or single selector
            timeout (int): Max wait time in seconds
            rule (str): "any" or "all"

        Returns:
            (bool, str): (status, timestamp)
        """
        if rule not in ("any", "all"):
            raise OpticsError(Code.E0403, message="Invalid rule. Use 'any' or 'all'.")

        if isinstance(elements, str):
            elements = [elements]

        page = self._require_page()
        start_time = time.time()

        internal_logger.info(
            "[PlaywrightPageSource] Asserting elements=%s rule=%s timeout=%ss",
            elements, rule, timeout
        )

        while time.time() - start_time < timeout:
            results = []

            for element in elements:
                try:
                    internal_logger.debug(
                        "testttttt [PlaywrightPageSource] Element '%s'",
                        element
                    )
                    element_type = utils.determine_element_type(element)
                    if element_type == "Text":
                        locator = page.get_by_text(element, exact=False)
                    elif element_type == "XPath":
                        locator = page.locator(f"xpath={element}")
                    else:
                        # CSS selector
                        locator = page.locator(element)

                    internal_logger.debug(
                        "[PlaywrightPageSource] Element '%s'",
                        element
                    )
                    found = locator.count() > 0
                    results.append(found)
                    html, _ = self.get_page_source()
                    found = element in html
                    results.append(found)

                    if rule == "any" and found:
                        return True, utils.get_timestamp()

                except Exception as e:
                    internal_logger.debug(
                        "[PlaywrightPageSource] Error checking '%s': %s",
                        element, str(e)
                    )
                    html, _ = self.get_page_source()
                    found = element in html
                    results.append(found)

                    if rule == "any" and found:
                        return True, utils.get_timestamp()
                    results.append(False)

            if rule == "all" and all(results):
                return True, utils.get_timestamp()

            time.sleep(0.3)

        internal_logger.warning(
            "[PlaywrightPageSource] Timeout reached. rule=%s elements=%s",
            rule, elements
        )
        return False, utils.get_timestamp()
