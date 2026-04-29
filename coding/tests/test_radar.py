from pathlib import Path
import sys

from selenium.common.exceptions import StaleElementReferenceException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import radar
from app.services.radar import _get_recent_message_texts


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

    def get(self, *_args, **_kwargs) -> None:
        return None

    def quit(self) -> None:
        return None


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


def test_get_recent_message_texts_keeps_short_messages_out_and_latest_three() -> None:
    driver = FakeDriver(
        [
            StableElement("ok"),
            StableElement("wei jom kelas"),
            StableElement("bit.ly/kelas"),
            StableElement("final urgent verify now"),
        ]
    )

    assert _get_recent_message_texts(driver) == [
        "wei jom kelas",
        "bit.ly/kelas",
        "final urgent verify now",
    ]


def test_whatsapp_monitor_worker_publishes_chat_messages_with_combined_features(
    monkeypatch,
) -> None:
    fake_driver = FakeDriver([StableElement("hello class this is the latest message")])

    monkeypatch.setattr(radar.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(radar.webdriver, "Chrome", lambda *args, **kwargs: fake_driver)
    monkeypatch.setattr(radar.ChromeDriverManager, "install", lambda self: "chromedriver")
    monkeypatch.setattr(
        radar,
        "setup_security_models",
        lambda: {
            "metrics": {
                "dataset_rows": 10,
                "rf_accuracy": 0.9,
                "svm_accuracy": 0.9,
                "model_version": "test-model",
            },
        },
    )
    monkeypatch.setattr(
        radar,
        "score_text",
        lambda text, _bundle: {"risk_score": 0.8 if "latest message" in text else 0.1},
    )

    calls = {"count": 0}

    def should_continue() -> bool:
        calls["count"] += 1
        return calls["count"] <= 21

    published_messages: list[dict] = []
    published_status: list[bool] = []

    radar.whatsapp_monitor_worker(
        should_continue=should_continue,
        on_message=published_messages.append,
        on_status_change=published_status.append,
    )

    assert any(message["type"] == "chat" for message in published_messages)
