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
    SESSION_DIR.mkdir(exist_ok=True, parents=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.add_argument("--profile-directory=Default")
    # Prevent automation detection which can cause WhatsApp to hang
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = None
    try:
        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options,
            )
        except Exception as startup_err:
            error_text = str(startup_err)
            if "user data directory is already in use" in error_text.lower():
                on_message({
                    "text": "System: Chrome profile is locked. Please close other Chrome windows using this session.",
                    "risk": 0.0,
                    "type": "system",
                })
            raise startup_err

        driver.get("https://web.whatsapp.com")
        on_message(
            {
                "text": "System: Opening WhatsApp Web. Please scan the QR code if prompted.",
                "risk": 0.0,
                "type": "system",
            }
        )

        # Wait for QR/Login - brittle but necessary without complex element polling
        for _ in range(20):
            if not should_continue():
                return
            time.sleep(1)

        model_bundle = setup_security_models()
        vectorizer = model_bundle["vectorizer"]
        rf_model = model_bundle["rf_model"]
        svm_model = model_bundle["svm_model"]
        metrics = model_bundle["metrics"]

        on_message(
            {
                "text": (
                    "System: Radar activated. "
                    f"Dataset={metrics['dataset_rows']} rows. "
                    f"Accuracy RF={metrics['rf_accuracy']:.1%}, SVM={metrics['svm_accuracy']:.1%}."
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
                    if not latest_message.strip() or "[UTeM SOC Bot" in latest_message:
                        continue

                    if latest_message in seen_messages:
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

                    if average_score > 0.75:
                        _send_warning(driver, average_score, on_message)

            except Exception as loop_exc:
                err_str = str(loop_exc)
                if "no such window" in err_str or "chrome not reachable" in err_str:
                    break
                time.sleep(2)

            time.sleep(2.0)

    except Exception as fatal_exc:
        on_message(
            {
                "text": f"System: Fatal error in monitoring thread: {fatal_exc}",
                "risk": 0.0,
                "type": "system",
            }
        )
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        on_status_change(False)
        on_message({
            "text": "System: Monitoring session terminated.",
            "risk": 0.0,
            "type": "system",
        })


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
