import time
from typing import Optional, Any, Tuple, List, Dict
from lxml import etree  # type: ignore

from optics_framework.common.logging_config import internal_logger
from optics_framework.common.elementsource_interface import ElementSourceInterface
from optics_framework.common.error import OpticsError, Code
from optics_framework.common import utils
from optics_framework.common.async_utils import run_async


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
            "[PlaywrightPageSource] driver=%s | has_page_attr=%s | page=%s",
            self.driver,
            hasattr(self.driver, "page") if self.driver else False,
            getattr(self.driver, "page", None) if self.driver else None
        )

        # 🔴 Driver not injected
        if self.driver is None:
            raise OpticsError(
                Code.E0101,
                message=(
                    "Playwright driver is not injected into PlaywrightPageSource. "
                    "Session may not be initialized."
                )
            )

        # 🔴 Driver exists but page attribute missing
        if not hasattr(self.driver, "page"):
            raise OpticsError(
                Code.E0101,
                message=(
                    "Playwright driver does not expose 'page'. "
                    "Invalid driver implementation or setup."
                )
            )

        # 🔴 Page attribute exists but page not yet created
        if self.driver.page is None:
            raise OpticsError(
                Code.E0101,
                message=(
                    "Playwright page is not initialized yet. "
                    "Ensure launch_app() completed before using element sources."
                )
            )

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

    def get_page_source(self) -> str:
        """
        Returns full DOM HTML and timestamp
        """
        internal_logger.error("trying get_page_source ..............")
        page = self._require_page()
        internal_logger.error("trying get_page_source _require_page ..............")
        timestamp = utils.get_timestamp()

        # html = run_async(page.content()) # page.content()
        html: str = run_async(page.content())
        internal_logger.debug(
            "[PlaywrightPageSource] Page source fetched, length=%d",
            len(html)
        )
        self.tree = etree.HTML(html)
        self.root = self.tree

        internal_logger.debug(
            "========== PLAYWRIGHT PAGE SOURCE FETCHED =========="
        )
        internal_logger.debug(
            "========== XML tree ========== %s ",html
        )
        internal_logger.debug("Timestamp: %s", timestamp)

        return html

    def get_interactive_elements(self, filter_config: Optional[List[str]] = None) -> List[Dict]:
        """
        Cross-platform element extraction for web pages.

        Args:
            filter_config: Optional list of filter types. Valid values:
                - "all": Show all elements (default when None or empty)
                - "interactive": Only interactive elements
                - "buttons": Only button elements
                - "inputs": Only input/text field elements
                - "images": Only image elements
                - "text": Only text elements
                Can be combined: ["buttons", "inputs"]

        Returns:
            List of dictionaries with keys: text, bounds, xpath, extra
        """
        # Ensure page source is fetched and parsed
        self.get_page_source()

        if self.tree is None:
            internal_logger.error("[PlaywrightPageSource] Tree is None, cannot extract elements")
            return []

        page = self._require_page()
        elements = self.tree.xpath(".//*")
        results = []

        for node in elements:
            bounds = self._extract_bounds(node, page)
            if not bounds:
                continue

            # Check if element should be included based on filter_config
            if not self._should_include_element(node, filter_config):
                continue

            text, used_key = self._extract_display_text(node, page)
            if not text:
                # If no text-like attribute, use tag name
                text, used_key = node.tag, None

            xpath = self.get_xpath(node)
            extra = self._build_extra_metadata(node.attrib, used_key, node.tag)

            results.append(
                {"text": text, "bounds": bounds, "xpath": xpath, "extra": extra}
            )

        return results

    # ---------------------------------------------------------
    # Helper methods for get_interactive_elements
    # ---------------------------------------------------------

    def _extract_bounds(self, node: etree.Element, page: Any) -> Optional[Dict[str, int]]:
        """
        Extract bounding box coordinates for a web element using Playwright.

        Args:
            node: The lxml element node
            page: Playwright page object

        Returns:
            Dict with x1, y1, x2, y2 or None if cannot get bounds
        """
        try:
            # Build a selector from the element
            xpath = self._build_simple_xpath(node)
            if not xpath:
                return None

            # Try to locate the element using XPath
            locator = page.locator(f"xpath={xpath}")
            count = run_async(locator.count())

            if count == 0:
                return None

            # Get bounding box from the first matching element
            bbox = run_async(locator.first.bounding_box())

            if bbox is None:
                return None

            x1 = int(bbox["x"])
            y1 = int(bbox["y"])
            x2 = int(bbox["x"] + bbox["width"])
            y2 = int(bbox["y"] + bbox["height"])

            return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

        except Exception as e:
            internal_logger.debug(
                f"[PlaywrightPageSource] Could not extract bounds for element: {e}"
            )
            return None

    def _build_simple_xpath(self, node: etree.Element) -> Optional[str]:
        """
        Build a simple XPath for locating an element in Playwright.
        This is a fallback method for getting bounds.
        """
        if node is None or not hasattr(node, "tag"):
            return None

        tag = node.tag or "*"
        attrs = node.attrib or {}

        # Helper to escape single quotes in XPath
        def escape_xpath_value(val: str) -> str:
            if "'" not in val:
                return f"'{val}'"
            # Use concat for values with single quotes
            parts = val.split("'")
            return "concat('" + "', \"'\", '".join(parts) + "')"

        # Try id first (most unique)
        if "id" in attrs and attrs["id"]:
            escaped_id = escape_xpath_value(attrs["id"])
            return f"//{tag}[@id={escaped_id}]"

        # Try data-testid
        if "data-testid" in attrs and attrs["data-testid"]:
            escaped_testid = escape_xpath_value(attrs["data-testid"])
            return f"//{tag}[@data-testid={escaped_testid}]"

        # Try name
        if "name" in attrs and attrs["name"]:
            escaped_name = escape_xpath_value(attrs["name"])
            return f"//{tag}[@name={escaped_name}]"

        # Fallback to hierarchical path with index
        path = []
        current = node
        while current is not None and hasattr(current, "tag"):
            parent = current.getparent()
            if parent is None:
                path.insert(0, current.tag or "*")
                break

            siblings = [sib for sib in parent if sib.tag == current.tag]
            if len(siblings) > 1:
                idx = siblings.index(current) + 1
                path.insert(0, f"{current.tag}[{idx}]")
            else:
                path.insert(0, current.tag or "*")

            current = parent

        return "/" + "/".join(path) if path else None

    def _extract_display_text(self, node: etree.Element, page: Any) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract display text from a web element.

        Priority order:
        1. Text content from lxml element (fastest)
        2. aria-label
        3. title
        4. alt (for images)
        5. placeholder (for inputs)
        6. innerText (via Playwright, slower)
        7. id
        8. class (last resort)

        Returns:
            Tuple of (text_value, attribute_used)
        """
        attrs = node.attrib or {}

        # Try text content from lxml element first (fastest)
        text_content = node.text
        if text_content and text_content.strip():
            return text_content.strip(), "text"

        # Try tail text (text after the element)
        if node.tail and node.tail.strip():
            return node.tail.strip(), "tail"

        # Try aria-label
        aria_label = attrs.get("aria-label", "").strip()
        if aria_label:
            return aria_label, "aria-label"

        # Try title
        title = attrs.get("title", "").strip()
        if title:
            return title, "title"

        # Try alt (for images)
        alt = attrs.get("alt", "").strip()
        if alt:
            return alt, "alt"

        # Try placeholder (for inputs)
        placeholder = attrs.get("placeholder", "").strip()
        if placeholder:
            return placeholder, "placeholder"

        # Try to get innerText via Playwright (slower, but more accurate)
        try:
            xpath = self._build_simple_xpath(node)
            if xpath:
                locator = page.locator(f"xpath={xpath}")
                count = run_async(locator.count())
                if count > 0:
                    inner_text = run_async(locator.first.inner_text())
                    if inner_text and inner_text.strip():
                        return inner_text.strip(), "innerText"
        except Exception as e:
            internal_logger.debug(f"Failed to get innerText via Playwright: {e}")

        # Try id
        element_id = attrs.get("id", "").strip()
        if element_id:
            return element_id, "id"

        # Try class (last resort, but usually not meaningful)
        class_name = attrs.get("class", "").strip()
        if class_name:
            # Take first class if multiple
            first_class = class_name.split()[0] if class_name else None
            if first_class:
                return first_class, "class"

        return None, None

    def _should_include_element(self, node: etree.Element, filter_config: Optional[List[str]]) -> bool:
        """
        Determine if an element should be included based on filter_config.

        Args:
            node: The XML element node
            filter_config: Optional list of filter types

        Returns:
            True if element should be included, False otherwise
        """
        # Default behavior: show all elements when filter_config is None or empty
        if not filter_config or len(filter_config) == 0:
            return True

        # If "all" is in filter_config, show all elements
        if "all" in filter_config:
            return True

        # Check each filter type
        matches_any = False

        if "interactive" in filter_config:
            if self._is_probably_interactive(node):
                matches_any = True

        if "buttons" in filter_config:
            if self._is_button(node):
                matches_any = True

        if "inputs" in filter_config:
            if self._is_input(node):
                matches_any = True

        if "images" in filter_config:
            if self._is_image(node):
                matches_any = True

        if "text" in filter_config:
            if self._is_text(node):
                matches_any = True

        return matches_any

    def _is_button(self, node: etree.Element) -> bool:
        """Check if element is a button."""
        tag = node.tag or ""
        attrs = node.attrib or {}

        # HTML button tag
        if tag.lower() == "button":
            return True

        # Elements with role="button"
        if attrs.get("role", "").lower() == "button":
            return True

        # Links that act as buttons (common pattern)
        if tag.lower() == "a" and (
            attrs.get("role", "").lower() == "button" or
            "button" in attrs.get("class", "").lower()
        ):
            return True

        return False

    def _is_input(self, node: etree.Element) -> bool:
        """Check if element is an input/text field."""
        tag = node.tag or ""

        # HTML input elements
        input_tags = ["input", "textarea", "select"]
        return tag.lower() in input_tags

    def _is_image(self, node: etree.Element) -> bool:
        """Check if element is an image."""
        tag = node.tag or ""
        attrs = node.attrib or {}

        # HTML img tag
        if tag.lower() == "img":
            return True

        # Elements with role="img"
        if attrs.get("role", "").lower() == "img":
            return True

        return False

    def _is_text(self, node: etree.Element) -> bool:
        """Check if element is a text element (non-input)."""
        tag = node.tag or ""
        attrs = node.attrib or {}

        # Exclude inputs
        if self._is_input(node):
            return False

        # Text-containing tags
        text_tags = ["p", "span", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                     "label", "li", "td", "th", "a", "strong", "em", "b", "i"]

        if tag.lower() in text_tags:
            # Check if it has text content or aria-label
            text_content = attrs.get("aria-label", "").strip()
            if text_content:
                return True
            # If it's a text tag, assume it might have text (will be checked via innerText)
            return True

        return False

    def _is_probably_interactive(self, node: etree.Element) -> bool:
        """
        Check if element is probably interactive (clickable, enabled, etc.).
        """
        tag = node.tag or ""
        attrs = node.attrib or {}

        # Buttons are interactive
        if self._is_button(node):
            return True

        # Links are interactive
        if tag.lower() == "a" and attrs.get("href"):
            return True

        # Inputs are interactive
        if self._is_input(node):
            return True

        # Elements with onclick handlers
        if "onclick" in attrs or attrs.get("onclick"):
            return True

        # Elements with role="button" or role="link"
        role = attrs.get("role", "").lower()
        if role in ["button", "link", "menuitem", "tab"]:
            return True

        # Elements with tabindex (usually interactive)
        if "tabindex" in attrs:
            try:
                tabindex = int(attrs.get("tabindex", "0"))
                if tabindex >= 0:  # Non-negative tabindex means focusable
                    return True
            except ValueError as e:
                internal_logger.debug(f"Invalid tabindex value: {e}")

        return False

    def get_xpath(self, node: etree.Element) -> str:
        """
        Generate an optimal XPath for a given HTML element.

        Prioritizes:
        1. id attribute
        2. data-testid attribute
        3. name attribute
        4. class attribute (if unique)
        5. aria-label attribute
        6. Hierarchical path with tag names
        """
        if node is None or not hasattr(node, "tag"):
            return ""

        tag = node.tag or "*"
        attrs = node.attrib or {}
        doc_tree = node.getroottree()

        # Utility: safely escape values for XPath literals
        def lit(val: str) -> str:
            return self._escape_for_xpath_literal(val)

        # Evaluate XPath against this node's document and determine uniqueness
        def determine_xpath_uniqueness(xpath: str):
            try:
                matches = doc_tree.xpath(xpath)
            except (etree.XPathError, ValueError, TypeError):
                return False, None

            if not matches:
                return False, None

            if len(matches) > 1:
                try:
                    idx = matches.index(node)
                except ValueError:
                    idx = 0
                return False, idx

            return True, None

        # Build XPath from a single attribute
        def build_xpath_from_attribute(attr_name: str):
            val = attrs.get(attr_name)
            if not val:
                return None
            return f"//{tag}[@{attr_name}={lit(val)}]"

        # Try unique attributes first
        unique_attrs = ["id", "data-testid", "name"]
        for attr in unique_attrs:
            xpath = build_xpath_from_attribute(attr)
            if xpath:
                is_unique, idx = determine_xpath_uniqueness(xpath)
                if is_unique:
                    return xpath
                if idx is not None:
                    return f"({xpath})[{idx + 1}]"

        # Try maybe-unique attributes
        maybe_unique_attrs = ["class", "aria-label", "title"]
        for attr in maybe_unique_attrs:
            xpath = build_xpath_from_attribute(attr)
            if xpath:
                is_unique, idx = determine_xpath_uniqueness(xpath)
                if is_unique:
                    return xpath
                if idx is not None:
                    return f"({xpath})[{idx + 1}]"

        # Fallback to hierarchical path
        return self._build_hierarchical_xpath(node)

    def _build_hierarchical_xpath(self, node: etree.Element) -> str:
        """
        Build hierarchical XPath based on element structure.
        """
        tag = node.tag
        if not tag:
            return ""

        parent = node.getparent()
        segment = f"/{tag}"

        if parent is not None:
            siblings_same_tag = [c for c in parent if c.tag == tag]
            if len(siblings_same_tag) > 1:
                idx = siblings_same_tag.index(node) + 1
                segment += f"[{idx}]"

        if parent is not None and hasattr(parent, "tag"):
            parent_xpath = self._build_hierarchical_xpath(parent)
            return f"{parent_xpath}{segment}"

        return segment

    def _escape_for_xpath_literal(self, s: str) -> str:
        """
        Safely escape a string for inclusion in an XPath string literal.
        Uses the concat() trick if both single and double quotes are present.
        """
        if '"' not in s:
            return f'"{s}"'
        if "'" not in s:
            return f"'{s}'"
        # If it contains both, break on double quotes and concat with '\"'
        parts = s.split('"')
        escaped_parts = []
        for i, p in enumerate(parts):
            if i == len(parts) - 1:
                escaped_parts.append(f'"{p}"')
            else:
                escaped_parts.extend([f'"{p}"', "'\"'"])
        return 'concat(' + ', '.join(escaped_parts) + ')'

    def _build_extra_metadata(self, attrs: dict, used_key: Optional[str], tag: str) -> dict:
        """
        Build metadata dictionary with element attributes.

        Args:
            attrs: Element attributes dictionary
            used_key: The attribute key used for text extraction (to exclude from extra)
            tag: Element tag name

        Returns:
            Dictionary with metadata
        """
        extra = {
            k: v
            for k, v in attrs.items()
            if k != used_key and v and (isinstance(v, str) and v.lower() != "false" or not isinstance(v, str))
        }

        # Keep common fields explicitly
        extra["tag"] = tag
        extra["class"] = attrs.get("class")
        extra["id"] = attrs.get("id")
        extra["role"] = attrs.get("role")
        extra["type"] = attrs.get("type")  # For input elements
        extra["href"] = attrs.get("href")  # For links

        return extra

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

            count = run_async(locator.count())
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

        # Check if driver is initialized before entering the loop
        try:
            page = self._require_page()
        except OpticsError:
            # If driver is not initialized, return False immediately instead of looping
            return False, utils.get_timestamp()

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
                    # Use run_async to await async Playwright methods
                    count = run_async(locator.count())
                    found = count > 0
                    results.append(found)

                    if rule == "any" and found:
                        return True, utils.get_timestamp()

                except Exception as e:
                    internal_logger.debug(
                        "[PlaywrightPageSource] Error checking '%s': %s",
                        element, str(e)
                    )
                    # Don't call get_page_source() in exception handler as it may also fail
                    # Just mark as not found
                    results.append(False)

            if rule == "all" and all(results):
                return True, utils.get_timestamp()

            time.sleep(0.3)

        internal_logger.warning(
            "[PlaywrightPageSource] Timeout reached. rule=%s elements=%s",
            rule, elements
        )
        return  False, utils.get_timestamp()
