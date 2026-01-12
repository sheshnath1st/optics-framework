import os
import yaml
import pytest

from optics_framework.common.async_utils import run_async
from optics_framework.optics import Optics


PLAYWRIGHT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../optics_framework/samples/youtube_web/config.yaml"
)


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def optics():
    """
    BEFORE all tests in the module
    """
    config = load_config(PLAYWRIGHT_CONFIG_PATH)

    optics = Optics()
    optics.setup(config=config)

    # Launch YouTube once
    optics.launch_app("https://www.youtube.com")

    yield optics

    # AFTER all tests
    optics.quit()


def test_youtube_launch(optics):
    """
    Smoke test: YouTube loads and search box is visible
    """
    optics.assert_presence('//input[@name="search_query"]')


if __name__ == "__main__":
    import pytest
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--log-cli-level=DEBUG"
    ])