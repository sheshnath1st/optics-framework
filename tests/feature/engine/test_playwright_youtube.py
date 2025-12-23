import os
import yaml
import pytest
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
    # Step 2: Add elements (selectors)
    # ---------------------------------------------------------
    optics.add_element("search_box", 'input[name="search_query"]')
    # ---------------------------------------------------------
    # Step 3: Assert elements are present
    # ---------------------------------------------------------
    # optics.assert_presence('search_box')
    optics.assert_presence('input[name="search_query"]')

    # ---------------------------------------------------------
    # Step 4: Search for video
    # ---------------------------------------------------------
    optics.press_element('input[name="search_query"]')
    optics.enter_text_using_keyboard(
        "Wild Stone Edge Perfume Review | Best Perfume For Men"
    )
    optics.press_element("search_button")

    optics.scroll("down", "1200")

    # ---------------------------------------------------------
    # Step 4: Click video
    # ---------------------------------------------------------
    optics.press_element("video_title", "1")

    # ---------------------------------------------------------
    # Step 5: Assert video page opened
    # ---------------------------------------------------------
    page_title = optics.get_text_element("h1.title")
    assert "Wild Stone Edge" in page_title, \
        f"Expected video title, got: {page_title}"
