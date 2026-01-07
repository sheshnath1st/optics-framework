import os
import yaml
import pytest

from optics_framework.common.async_utils import run_async
from optics_framework.optics import Optics


PLAYWRIGHT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../optics_framework/samples/playwright/config.yaml"
)


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def optics_instance():
    """
    Fixture to setup and teardown Optics with Playwright driver
    """
    config = load_config(PLAYWRIGHT_CONFIG_PATH)
    optics = Optics()
    optics.setup(config=config)
    yield optics
    optics.quit()


def test_youtube_search_and_play(optics_instance):
    optics = optics_instance

    # ---------------------------------------------------------
    # Step 1: Launch YouTube
    # ---------------------------------------------------------
    optics.launch_app("https://www.youtube.com")

    # ---------------------------------------------------------
    # Step 2: Register elements
    # ---------------------------------------------------------
    optics.add_element("search_box", 'input[name="search_query"]')
    optics.add_element("video_title", 'text=Wild Stone Edge')

    # ---------------------------------------------------------
    # Step 3: Assert search box
    # ---------------------------------------------------------
    optics.assert_presence('input[name="search_query"]')

    # ---------------------------------------------------------
    # Step 4: Search
    # ---------------------------------------------------------
    optics.press_element('input[name="search_query"]')
    optics.enter_text_using_keyboard(
        "Wild Stone Edge Perfume Revie"
    )
    optics.press_keycode("Enter")
    # optics.scroll("down")
    # optics.scroll("down")
    # optics.sleep(1)
    # optics.scroll("down")
    # optics.sleep(1)

    # ---------------------------------------------------------
    # Step 5: Scroll until video appears
    # ---------------------------------------------------------
    # optics.add_element("search_box", 'input[name="search_query"]')
    # optics.add_element("video_title", 'text=Wild Stone Edge')
    # optics.scroll_until_element_appears(
    #     "Wild Stone Edge Perfume Review",
    #     direction="down"
    # )
    # optics.sleep("10")
    # html = optics.capture_pagesource() # Tested not sure
    html = optics.capture_pagesource() # Working
    print("========== PAGE SOURCE (XML TREE) ==========")
    # print(html)
    # print(run_async(optics.app_management.driver.page.content()))
    # print("========================= XML Tree =========================")
    # print(html)
    # execution_logger.info("========================= XML Tree log =========================")
    # execution_logger.info(html)
    # print("========================= XML Tree =========================")
    optics.capture_screenshot() # Tested Working
    version = optics.get_app_version() # Tested Working
    print(version)
    # optics.press_by_percentage("50","50") # Tested and Working
    # optics.press_element_with_index()
    # optics.detect_and_press("Best Budget Perfume for Men") # Tested and Working
    # optics.swipe("1500","1500","up") # Tested and Working
    # optics.swipe_until_element_appears("Best Budget Perfume for Men")  # Tested and Working
    # optics.swipe_from_element("wild stone edge perfume","up","100") # Tested and Working
    # optics.swipe_from_element("wild stone edge perfume", "down","100")  # Tested and Working
    optics.scroll_until_element_appears("Better than")
    # optics.scroll_from_element()
    # optics.enter_text()
    # optics.enter_text_direct()
    # optics.enter_number()
    # optics.press_keycode()
    # optics.clear_element_text()
    # optics.get_text()
    # optics.validate_screen()



    # optics.validate_element("Best Budget Perfume for Men ₹356")
    # optics.press_element("Best Budget Perfume for Men ₹356")
    # optics.assert_presence("Wild stone Edge perfume review")

    optics.sleep("10")

if __name__ == "__main__":
    import pytest
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--log-cli-level=DEBUG"
    ])