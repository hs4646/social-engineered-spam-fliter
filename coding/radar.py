import time
from collections import deque
from pathlib import Path
from typing import Callable

import pyperclip
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

from learning_engine import setup_security_models


MessageCallback = Callable[[dict], None]
StatusCallback = Callable[[bool], None]
SESSION_DIR = Path(__file__).resolve().parent / ".whatsapp_session"


def _get_recent_message_texts(driver: webdriver.Chrome) -> list[str]:
    texts: list[str] = []
    elements = driver.find_elements(By.CSS_SELECTOR, "div[role='row'] span[dir='ltr']")

    for element in elements[-5:]:
        try:
            text = element.text.strip()
        except StaleElementReferenceException:
            continue

        if len(text) > 4:
            texts.append(text)

    return texts[-3:]


def whatsapp_monitor_worker(
    should_continue: Callable[[], bool],
    on_message: MessageCallback,
    on_status_change: StatusCallback,
) -> None:
    SESSION_DIR.mkdir(exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.add_argument("--profile-directory=Default")

    driver = None
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )

        driver.get("https://web.whatsapp.com")
        on_message(
            {
                "text": "System: Opening WhatsApp Web with the saved Chrome session. Scan the QR code only if WhatsApp asks for it.",
                "risk": 0.0,
                "type": "system",
            }
        )

        time.sleep(20)
        if not should_continue():
            return

        model_bundle = setup_security_models()
        vectorizer = model_bundle["vectorizer"]
        rf_model = model_bundle["rf_model"]
        svm_model = model_bundle["svm_model"]
        metrics = model_bundle["metrics"]

        on_message(
            {
                "text": (
                    "System: Radar activated. "
                    f"Dataset rows={metrics['dataset_rows']} "
                    f"(safe={metrics['safe_rows']}, threat={metrics['threat_rows']}). "
                    f"Holdout accuracy RF={metrics['rf_accuracy']:.0%}, "
                    f"SVM={metrics['svm_accuracy']:.0%}."
                ),
                "risk": 0.0,
                "type": "system",
            }
        )

        seen_messages = deque(maxlen=20)

        while should_continue():
            try:
                recent_messages = _get_recent_message_texts(driver)

                for latest_message in recent_messages:
                    if "[UTeM SOC Bot" in latest_message:
                        continue

                    if latest_message in seen_messages or not latest_message.strip():
                        continue

                    seen_messages.append(latest_message)

                    input_vector = vectorizer.transform([latest_message])
                    rf_score = rf_model.predict_proba(input_vector)[0][1]
                    svm_score = svm_model.predict_proba(input_vector)[0][1]
                    average_score = (rf_score + svm_score) / 2

                    on_message(
                        {
                            "text": latest_message,
                            "type": "chat",
                            "risk": float(average_score),
                        }
                    )

                    if average_score > 0.70:
                        _send_warning(driver, average_score, on_message)

            except Exception as exc:
                error_message = str(exc)
                if "no such window" in error_message or "chrome not reachable" in error_message:
                    on_message(
                        {
                            "text": "System: Monitoring browser closed. Radar deactivated.",
                            "risk": 0.0,
                            "type": "system",
                        }
                    )
                    break
                on_message(
                    {
                        "text": f"System: Monitor loop error: {error_message}",
                        "risk": 0.0,
                        "type": "system",
                    }
                )

            time.sleep(2.5)
    except Exception as exc:
        on_message(
            {
                "text": f"System: Monitoring failed to start: {exc}",
                "risk": 0.0,
                "type": "system",
            }
        )
    finally:
        on_status_change(False)
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def _send_warning(driver, risk_score: float, on_message: MessageCallback) -> None:
    try:
        time.sleep(0.5)
        input_box = driver.find_element(
            By.CSS_SELECTOR, "div[contenteditable='true'][data-tab='10']"
        )
        input_box.click()
        time.sleep(0.5)

        warning_lines = [
            "[UTeM SOC Bot Automated Warning]",
            f"High-risk phishing threat detected in the previous message (Risk: {risk_score:.2%}).",
            "Do not click any links or share personal information.",
        ]

        for index, line in enumerate(warning_lines):
            pyperclip.copy(line)
            input_box.send_keys(Keys.CONTROL, "v")
            time.sleep(0.2)

            if index < len(warning_lines) - 1:
                input_box.send_keys(Keys.SHIFT, Keys.ENTER)

        time.sleep(0.5)
        input_box.send_keys(Keys.ENTER)

        on_message(
            {
                "text": "System: Automated anti-scam warning broadcasted in the WhatsApp group.",
                "risk": 0.0,
                "type": "system",
            }
        )
    except Exception as exc:
        on_message(
            {
                "text": f"System: Auto-response failed: {exc}",
                "risk": 0.0,
                "type": "system",
            }
        )
