from selenium.common.exceptions import StaleElementReferenceException

from radar import _get_recent_message_texts


class StableElement:
    def __init__(self, text: str) -> None:
        self.text = text


class StaleElement:
    @property
    def text(self) -> str:
        raise StaleElementReferenceException("stale")


class FakeDriver:
    def __init__(self, elements) -> None:
        self._elements = elements

    def find_elements(self, *_args, **_kwargs):
        return self._elements


def test_get_recent_message_texts_skips_stale_elements() -> None:
    driver = FakeDriver(
        [
            StableElement("ignore"),
            StaleElement(),
            StableElement("Legitimate message"),
            StableElement("ok"),
            StableElement("Another message"),
            StableElement("Final message"),
        ]
    )

    assert _get_recent_message_texts(driver) == [
        "Legitimate message",
        "Another message",
        "Final message",
    ]
