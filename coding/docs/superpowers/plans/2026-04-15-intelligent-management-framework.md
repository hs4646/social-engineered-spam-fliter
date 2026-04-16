# Intelligent Management Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a frontend/backend system for university WhatsApp group monitoring that logs in through WhatsApp Web QR, ingests group messages, assigns model-based risk scores, and routes high-risk content through a controlled cybersecurity review workflow.

**Architecture:** Keep the stack Python-first to match the current prototype, but split the monolith into a FastAPI backend, a service layer for WhatsApp/session/model orchestration, and a thin browser dashboard for QR login, live feed, and analyst review. Do not auto-send warnings directly from model output; the backend should persist detections, expose review APIs, and only allow operator-approved mitigation actions.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, vanilla JavaScript modules, Selenium, scikit-learn, pandas, SQLite, pytest, Playwright or Selenium-based browser checks, Pydantic.

---

## File Structure

- `app/main.py`: FastAPI app factory, startup/shutdown hooks, router registration, websocket registration.
- `app/core/config.py`: environment-backed settings for paths, thresholds, session directories, and database URL.
- `app/core/database.py`: SQLite connection/session bootstrap.
- `app/schemas/auth.py`: QR session and login state response models.
- `app/schemas/monitor.py`: message, risk event, queue, and dashboard response models.
- `app/repositories/risk_events.py`: persistence for captured messages, scores, analyst decisions, and action audit trail.
- `app/services/model_registry.py`: dataset loading, training, model metadata, and inference entry points.
- `app/services/risk_policy.py`: threshold bands and manual-review decision policy.
- `app/services/whatsapp_session.py`: browser startup, QR status detection, login lifecycle, and chat selection helpers.
- `app/services/whatsapp_monitor.py`: monitored message extraction loop and event publishing.
- `app/services/event_bus.py`: in-process pub/sub for websocket broadcasting.
- `app/api/routes/auth.py`: QR/login endpoints.
- `app/api/routes/monitor.py`: monitoring lifecycle, dashboard feed, review queue, and operator action endpoints.
- `templates/index.html`: dashboard shell.
- `static/dashboard.js`: dashboard state, websocket handling, QR flow, review queue UI.
- `static/styles.css`: dashboard styling.
- `scripts/train_model.py`: offline training entry point for dataset refresh.
- `tests/test_auth_routes.py`: QR/login API tests.
- `tests/test_monitor_routes.py`: monitor lifecycle and review flow tests.
- `tests/test_model_registry.py`: training and scoring tests.
- `tests/test_risk_policy.py`: threshold and review policy tests.
- `tests/test_whatsapp_monitor.py`: message extraction and deduplication tests.

### Task 1: Restructure the Backend Into Clear Units

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/core/config.py`
- Create: `app/core/database.py`
- Create: `app/api/__init__.py`
- Create: `app/api/routes/__init__.py`
- Modify: `app.py`
- Test: `tests/test_app_bootstrap.py`

- [ ] **Step 1: Write the failing bootstrap test**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_create_app_exposes_health_and_static_mount() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


def create_app() -> FastAPI:
    app = FastAPI(title="UTeM SOC Dashboard")
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/api/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    return app
```

```python
# app.py
from app.main import create_app

app = create_app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app_bootstrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py app/__init__.py app/main.py app/core/config.py app/core/database.py app/api/__init__.py app/api/routes/__init__.py tests/test_app_bootstrap.py
git commit -m "refactor: split backend bootstrap into app package"
```

### Task 2: Add Persistent Risk Event Storage

**Files:**
- Create: `app/repositories/risk_events.py`
- Create: `app/schemas/monitor.py`
- Modify: `app/core/database.py`
- Test: `tests/test_risk_events_repository.py`

- [ ] **Step 1: Write the failing repository test**

```python
from app.repositories.risk_events import RiskEventRepository


def test_repository_persists_message_and_decision(tmp_path) -> None:
    repository = RiskEventRepository(tmp_path / "soc.db")
    event_id = repository.create_event(
        message_text="Telegram class invite for CSM3023",
        source_group="CSM3023 Project",
        sender_name="Dr Megat",
        risk_score=0.41,
        model_version="tfidf-rf-svm-v1",
    )

    repository.record_decision(event_id, decision="allow", reviewer="analyst1")
    event = repository.get_event(event_id)

    assert event["decision"] == "allow"
    assert event["source_group"] == "CSM3023 Project"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_risk_events_repository.py -v`
Expected: FAIL with `ImportError` or missing `RiskEventRepository`

- [ ] **Step 3: Write minimal implementation**

```python
import sqlite3
from pathlib import Path


class RiskEventRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                create table if not exists risk_events (
                    id integer primary key autoincrement,
                    message_text text not null,
                    source_group text not null,
                    sender_name text not null,
                    risk_score real not null,
                    model_version text not null,
                    decision text,
                    reviewer text
                )
                """
            )

    def create_event(self, **payload: object) -> int:
        with sqlite3.connect(self._db_path) as connection:
            cursor = connection.execute(
                """
                insert into risk_events(message_text, source_group, sender_name, risk_score, model_version)
                values (:message_text, :source_group, :sender_name, :risk_score, :model_version)
                """,
                payload,
            )
            return int(cursor.lastrowid)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_risk_events_repository.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/repositories/risk_events.py app/schemas/monitor.py app/core/database.py tests/test_risk_events_repository.py
git commit -m "feat: add persistent risk event repository"
```

### Task 3: Build the Model Training and Inference Service

**Files:**
- Create: `app/services/model_registry.py`
- Create: `scripts/train_model.py`
- Modify: `learning_engine.py`
- Test: `tests/test_model_registry.py`

- [ ] **Step 1: Write the failing model service test**

```python
from app.services.model_registry import ModelRegistry


def test_model_registry_returns_risk_breakdown(tmp_path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text(
        "content,label\n"
        "\"Please review the lecture notes in Google Classroom\",0\n"
        "\"URGENT: verify your student portal at fake-link\",1\n",
        encoding="utf-8",
    )

    registry = ModelRegistry(dataset_path)
    registry.train()
    result = registry.score("Telegram invite link for Software Security lecture")

    assert set(result) >= {"risk_score", "rf_score", "svm_score", "model_version"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_model_registry.py -v`
Expected: FAIL with missing `ModelRegistry`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path

from learning_engine import setup_security_models


@dataclass
class ScoreResult:
    risk_score: float
    rf_score: float
    svm_score: float
    model_version: str


class ModelRegistry:
    def __init__(self, dataset_path: Path) -> None:
        self._dataset_path = Path(dataset_path)
        self._bundle: dict[str, object] | None = None

    def train(self) -> None:
        self._bundle = setup_security_models(dataset_path=self._dataset_path)

    def score(self, text: str) -> dict[str, object]:
        bundle = self._bundle or setup_security_models(dataset_path=self._dataset_path)
        vector = bundle["vectorizer"].transform([text])
        rf_score = float(bundle["rf_model"].predict_proba(vector)[0][1])
        svm_score = float(bundle["svm_model"].predict_proba(vector)[0][1])
        return {
            "risk_score": (rf_score + svm_score) / 2,
            "rf_score": rf_score,
            "svm_score": svm_score,
            "model_version": bundle["metrics"]["model_version"],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_model_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/model_registry.py scripts/train_model.py learning_engine.py tests/test_model_registry.py
git commit -m "feat: add trainable model registry service"
```

### Task 4: Add Risk Policy With Review Bands Instead of Blind Auto-Warn

**Files:**
- Create: `app/services/risk_policy.py`
- Modify: `app/schemas/monitor.py`
- Test: `tests/test_risk_policy.py`

- [ ] **Step 1: Write the failing policy test**

```python
from app.services.risk_policy import RiskPolicy


def test_policy_routes_borderline_messages_to_manual_review() -> None:
    policy = RiskPolicy(low_threshold=0.30, high_threshold=0.80)

    decision = policy.classify(0.52)

    assert decision["queue"] == "manual_review"
    assert decision["auto_action"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_risk_policy.py -v`
Expected: FAIL with missing `RiskPolicy`

- [ ] **Step 3: Write minimal implementation**

```python
class RiskPolicy:
    def __init__(self, low_threshold: float, high_threshold: float) -> None:
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold

    def classify(self, risk_score: float) -> dict[str, object]:
        if risk_score >= self.high_threshold:
            return {"queue": "manual_review", "auto_action": None, "severity": "high"}
        if risk_score >= self.low_threshold:
            return {"queue": "manual_review", "auto_action": None, "severity": "medium"}
        return {"queue": "allow", "auto_action": None, "severity": "low"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_risk_policy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/risk_policy.py app/schemas/monitor.py tests/test_risk_policy.py
git commit -m "feat: add manual-review risk policy"
```

### Task 5: Implement WhatsApp QR Login and Session Status APIs

**Files:**
- Create: `app/services/whatsapp_session.py`
- Create: `app/schemas/auth.py`
- Create: `app/api/routes/auth.py`
- Modify: `app/main.py`
- Test: `tests/test_auth_routes.py`

- [ ] **Step 1: Write the failing auth route test**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_login_status_reports_qr_required(monkeypatch) -> None:
    class FakeSessionService:
        def get_login_status(self) -> dict[str, object]:
            return {"state": "qr_required", "qr_image_url": "/api/auth/qr"}

    app = create_app(session_service=FakeSessionService())
    client = TestClient(app)

    response = client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json()["state"] == "qr_required"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth_routes.py -v`
Expected: FAIL with 404 on `/api/auth/status`

- [ ] **Step 3: Write minimal implementation**

```python
from fastapi import APIRouter, Depends


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
async def get_auth_status(session_service=Depends(get_session_service)) -> dict[str, object]:
    return session_service.get_login_status()
```

```python
# app/services/whatsapp_session.py
class WhatsAppSessionService:
    def get_login_status(self) -> dict[str, object]:
        return {"state": "qr_required", "qr_image_url": "/api/auth/qr"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_auth_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/whatsapp_session.py app/schemas/auth.py app/api/routes/auth.py app/main.py tests/test_auth_routes.py
git commit -m "feat: add whatsapp login status api"
```

### Task 6: Implement Group Monitoring With Source Metadata

**Files:**
- Create: `app/services/event_bus.py`
- Create: `app/services/whatsapp_monitor.py`
- Create: `app/api/routes/monitor.py`
- Modify: `app/main.py`
- Test: `tests/test_whatsapp_monitor.py`
- Test: `tests/test_monitor_routes.py`

- [ ] **Step 1: Write the failing monitor extraction test**

```python
from app.services.whatsapp_monitor import extract_recent_messages


def test_extract_recent_messages_returns_sender_group_and_text() -> None:
    html_rows = [
        {"group_name": "Cybersecurity FYP", "sender_name": "Dr Megat", "text": "Telegram invite for discussion"},
        {"group_name": "Cybersecurity FYP", "sender_name": "Han Shen", "text": "ok noted"},
    ]

    messages = extract_recent_messages(html_rows)

    assert messages[0]["group_name"] == "Cybersecurity FYP"
    assert messages[0]["sender_name"] == "Dr Megat"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_whatsapp_monitor.py -v`
Expected: FAIL with missing `extract_recent_messages`

- [ ] **Step 3: Write minimal implementation**

```python
def extract_recent_messages(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for row in rows:
        text = row.get("text", "").strip()
        if not text:
            continue
        messages.append(
            {
                "group_name": row.get("group_name", "Unknown"),
                "sender_name": row.get("sender_name", "Unknown"),
                "text": text,
            }
        )
    return messages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_whatsapp_monitor.py tests/test_monitor_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/event_bus.py app/services/whatsapp_monitor.py app/api/routes/monitor.py app/main.py tests/test_whatsapp_monitor.py tests/test_monitor_routes.py
git commit -m "feat: add monitored group ingestion pipeline"
```

### Task 7: Build the Dashboard for QR Login, Live Feed, and Review Queue

**Files:**
- Modify: `templates/index.html`
- Modify: `static/dashboard.js`
- Create: `static/styles.css`
- Test: `tests/test_dashboard_render.py`

- [ ] **Step 1: Write the failing dashboard state test**

```python
from pathlib import Path


def test_dashboard_contains_qr_and_review_sections() -> None:
    html = Path("templates/index.html").read_text(encoding="utf-8")

    assert 'id="qrPanel"' in html
    assert 'id="reviewQueue"' in html
    assert 'id="feedList"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dashboard_render.py -v`
Expected: FAIL because `qrPanel` and `reviewQueue` are missing

- [ ] **Step 3: Write minimal implementation**

```html
<section id="qrPanel" class="panel">
  <h2>WhatsApp Login</h2>
  <img id="qrImage" alt="WhatsApp QR code" />
  <p id="loginState">Waiting for QR session</p>
</section>

<section id="reviewQueue" class="panel">
  <h2>Analyst Review Queue</h2>
  <div id="queueList"></div>
</section>

<section id="feedPanel" class="panel">
  <h2>Live Threat Feed</h2>
  <div id="feedList"></div>
</section>
```

```javascript
export async function refreshAuthStatus(fetchImpl = fetch) {
  const response = await fetchImpl('/api/auth/status');
  return response.json();
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dashboard_render.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/index.html static/dashboard.js static/styles.css tests/test_dashboard_render.py
git commit -m "feat: add dashboard panels for qr feed and review queue"
```

### Task 8: Add End-to-End Review Workflow and Operator Actions

**Files:**
- Modify: `app/api/routes/monitor.py`
- Modify: `app/repositories/risk_events.py`
- Modify: `static/dashboard.js`
- Test: `tests/test_monitor_routes.py`

- [ ] **Step 1: Write the failing review action test**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_review_endpoint_records_allow_decision(fake_services) -> None:
    app = create_app(**fake_services)
    client = TestClient(app)

    response = client.post(
        "/api/monitor/events/1/review",
        json={"decision": "allow", "reviewer": "analyst1"},
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "allow"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_monitor_routes.py::test_review_endpoint_records_allow_decision -v`
Expected: FAIL with 404 on `/api/monitor/events/1/review`

- [ ] **Step 3: Write minimal implementation**

```python
@router.post("/events/{event_id}/review")
async def review_event(event_id: int, payload: ReviewDecision, repository=Depends(get_repository)) -> dict[str, object]:
    repository.record_decision(event_id, decision=payload.decision, reviewer=payload.reviewer)
    return repository.get_event(event_id)
```

```javascript
export async function submitReviewDecision(eventId, decision, reviewer, fetchImpl = fetch) {
  const response = await fetchImpl(`/api/monitor/events/${eventId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, reviewer }),
  });
  return response.json();
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_monitor_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/monitor.py app/repositories/risk_events.py static/dashboard.js tests/test_monitor_routes.py
git commit -m "feat: add analyst review action workflow"
```

### Task 9: Document Training, Evaluation, and Safe Demo Operation

**Files:**
- Create: `docs/model-evaluation.md`
- Create: `docs/demo-runbook.md`
- Modify: `README.md`
- Test: `tests/test_documentation_links.py`

- [ ] **Step 1: Write the failing docs linkage test**

```python
from pathlib import Path


def test_readme_links_to_model_eval_and_runbook() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docs/model-evaluation.md" in readme
    assert "docs/demo-runbook.md" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documentation_links.py -v`
Expected: FAIL because the docs links are absent

- [ ] **Step 3: Write minimal implementation**

```markdown
# Model Evaluation

- Dataset source and label policy
- Train/validation/test split strategy
- Precision, recall, F1, confusion matrix
- Known false positive categories: parcel pickup notices, lecturer invite links, class admin notices
- Safe deployment rule: model output is advisory until analyst review
```

```markdown
# Demo Runbook

1. Start backend.
2. Open dashboard.
3. Scan WhatsApp QR.
4. Select approved university group.
5. Observe risk queue.
6. Review alerts manually.
7. Do not auto-send warnings in live groups during evaluation demos.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_documentation_links.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/model-evaluation.md docs/demo-runbook.md tests/test_documentation_links.py
git commit -m "docs: add evaluation and demo safety documentation"
```

## Self-Review

- Spec coverage: the plan covers frontend QR login, backend APIs, persisted event history, model-based scoring, monitored group ingestion, analyst review workflow, and evaluation documentation. The intentionally excluded behavior is direct automatic warning messages inside live groups; that is replaced with manual review because it is the safer fit for the false-positive problem already observed.
- Placeholder scan: no `TODO`, `TBD`, or “implement later” markers remain. Each task names exact files, tests, commands, and minimal code.
- Type consistency: `RiskEventRepository`, `ModelRegistry`, `RiskPolicy`, `WhatsAppSessionService`, and the route naming are used consistently across the plan.

**Plan complete and saved to `docs/superpowers/plans/2026-04-15-intelligent-management-framework.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
