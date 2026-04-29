# Manglish Shortlink Detection and Cybersecurity Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the phishing engine with Manglish-aware preprocessing and explicit shortlink/domain features, refresh the dashboard with a cybersecurity-focused design, and clean noisy tracked transient project files.

**Architecture:** Extend `app/services/learning_engine.py` into a shared preprocessing and feature-extraction pipeline that combines normalized multilingual TF-IDF text with handcrafted URL/risk features for the existing Random Forest and SVM models. Keep runtime integration through `ModelRegistry` and the FastAPI dashboard unchanged at the API layer while restyling the frontend and removing tracked `.whatsapp_session` noise from git.

**Tech Stack:** Python, pandas, scikit-learn, scipy sparse matrices, FastAPI, HTML, JavaScript, pytest, Node test runner, git

---

### Task 1: Detection Regression Tests

**Files:**
- Modify: `tests/test_model_registry.py`
- Test: `tests/test_model_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_model_registry_scores_shortlink_manglish_scam_higher_than_normal_chat() -> None:
    dataset_path = _write_dataset(
        [
            ("wei bro kelas esok pindah bilik ya", 0),
            ("tolong semak nota kat https://bit.ly/kelas-notes", 0),
            ("urgent wei akaun bank u kena sekat verify now at https://bit.ly/kemaskini-sekarang", 1),
            ("pls update your payroll profile at https://secure-payroll-check.example", 1),
            ("jom mamak malam ni lepas class", 0),
            ("sy x sempat join meeting pagi tadi", 0),
            ("akaun anda akan ditamatkan sila klik https://rb.gy/abc123", 1),
            ("official portal is https://www.maybank2u.com.my", 0),
            ("ur parcel pending pay fee at http://tinyurl.com/claim-parcel", 1),
            ("presentation FYP start pukul 2 nanti", 0),
        ]
    )

    registry = ModelRegistry(dataset_path)
    registry.train()

    scam = registry.score("wei urgent akaun u kena block, klik https://bit.ly/verify-now")
    safe = registry.score("wei jom tengok nota class kat https://bit.ly/kelas-notes")

    assert scam["risk_score"] > safe["risk_score"]
    assert scam["risk_score"] >= 0.5
    assert safe["risk_score"] < 0.75


def test_model_registry_exposes_feature_details() -> None:
    dataset_path = _write_dataset(
        [
            ("class replacement tomorrow at BK3", 0),
            ("please verify your account at https://bit.ly/check-now", 1),
            ("boleh share slide lecture malam ni", 0),
            ("akaun anda disekat sila klik https://tinyurl.com/buka-akaun", 1),
            ("official info at https://www.hasil.gov.my", 0),
            ("urgent action required update TAC profile now", 1),
            ("jom print poster petang ni", 0),
            ("pembayaran gagal kemaskini bank di https://rb.gy/pay-now", 1),
            ("meeting FYP moved to 3pm", 0),
            ("pls verify shopee account immediately", 1),
        ]
    )

    registry = ModelRegistry(dataset_path)
    registry.train()
    result = registry.score("urgent akaun bank u kena sekat klik https://bit.ly/kemaskini")

    assert "feature_signals" in result
    assert result["feature_signals"]["has_shortlink"] == 1.0
    assert result["feature_signals"]["has_url"] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_model_registry.py -v`
Expected: FAIL because the current model output does not expose `feature_signals` and does not strongly separate the new shortlink/Manglish cases.

- [ ] **Step 3: Commit**

```bash
git add tests/test_model_registry.py
git commit -m "test: cover manglish and shortlink detection"
```

### Task 2: Feature Pipeline Implementation

**Files:**
- Modify: `app/services/learning_engine.py`
- Modify: `app/services/model_registry.py`
- Test: `tests/test_model_registry.py`

- [ ] **Step 1: Write minimal implementation**

```python
SHORTLINK_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "rb.gy", "shorturl.at",
}

MANGGLISH_MAP = {
    "u": "you",
    "ur": "your",
    "x": "tak",
    "sy": "saya",
    "sya": "saya",
    "aq": "saya",
    "pls": "please",
    "pls.": "please",
    "ni": "ini",
    "je": "sahaja",
    "jer": "sahaja",
    "blh": "boleh",
    "jgn": "jangan",
    "nnti": "nanti",
    "kene": "kena",
}

def score_text(text: str, bundle: dict[str, object]) -> dict[str, object]:
    features = _extract_feature_signals(text)
    vector = _vectorize_texts(bundle["vectorizer"], [text])
    dense = csr_matrix([[features[name] for name in FEATURE_COLUMNS]])
    combined = hstack([vector, dense], format="csr")
    rf_score = float(bundle["rf_model"].predict_proba(combined)[0][1])
    svm_score = float(bundle["svm_model"].predict_proba(combined)[0][1])
    base_score = (rf_score + svm_score) / 2
    final_score = _apply_shortlink_boost(base_score, features)
    return {
        "risk_score": final_score,
        "rf_score": rf_score,
        "svm_score": svm_score,
        "feature_signals": features,
        "model_version": bundle["metrics"]["model_version"],
    }
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_model_registry.py -v`
Expected: PASS

- [ ] **Step 3: Refactor into shared helpers**

```python
def prepare_training_frame(dataset_path: Path | None = None) -> pd.DataFrame: ...
def normalize_message_text(text: str) -> str: ...
def extract_feature_signals(text: str) -> dict[str, float]: ...
def vectorize_messages(vectorizer: TfidfVectorizer, texts: Sequence[str]): ...
def score_text(text: str, bundle: dict[str, object]) -> dict[str, object]: ...
```

- [ ] **Step 4: Run focused verification**

Run: `pytest tests/test_model_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/learning_engine.py app/services/model_registry.py tests/test_model_registry.py
git commit -m "feat: add manglish and shortlink phishing signals"
```

### Task 3: Runtime Compatibility and Radar Safety

**Files:**
- Modify: `app/services/radar.py`
- Modify: `tests/test_radar.py`
- Test: `tests/test_radar.py`

- [ ] **Step 1: Write the failing test**

```python
def test_get_recent_message_texts_keeps_short_messages_out_and_latest_three() -> None:
    driver = FakeDriver(
        [
            StableElement("ok"),
            StableElement("bit.ly/kelas"),
            StableElement("wei akaun kena block klik bit.ly/verify"),
            StableElement("jom mamak"),
            StableElement("final urgent verify now"),
        ]
    )

    assert _get_recent_message_texts(driver) == [
        "bit.ly/kelas",
        "wei akaun kena block klik bit.ly/verify",
        "final urgent verify now",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_radar.py -v`
Expected: FAIL because the current helper drops very short link-heavy messages such as `bit.ly/kelas`.

- [ ] **Step 3: Implement the minimal fix**

```python
        if text and (len(text) > 4 or "." in text or "/" in text):
            texts.append(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_radar.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/radar.py tests/test_radar.py
git commit -m "fix: preserve short link messages in radar feed"
```

### Task 4: Dashboard Cybersecurity Design

**Files:**
- Modify: `templates/index.html`
- Modify: `static/dashboard.js`
- Modify: `static/dashboard.test.mjs`
- Test: `static/dashboard.test.mjs`

- [ ] **Step 1: Write the failing tests**

```javascript
assert.deepEqual(
  computeControlState({ isRunning: true, requestPending: false }),
  {
    startDisabled: true,
    stopDisabled: false,
    refreshDisabled: false,
    statusText: 'Threat Monitoring Live',
    statusClassName: 'status-pill status-live',
  },
);

assert.equal(classifyRiskLevel({ type: 'chat', risk: 0.82 }), 'critical');
assert.equal(classifyRiskLevel({ type: 'system', risk: 0.1 }), 'system');
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node static/dashboard.test.mjs`
Expected: FAIL because the current UI helpers return Bootstrap badge classes and do not expose `classifyRiskLevel`.

- [ ] **Step 3: Implement the dashboard refresh**

```html
<body class="soc-shell">
  <div class="grid-overlay"></div>
  <main class="dashboard-frame">
    <section class="hero-panel">...</section>
    <section class="intel-strip">...</section>
    <section class="feed-panel">...</section>
  </main>
</body>
```

```javascript
export function classifyRiskLevel(message) {
  if (message.type === 'system') return 'system';
  if (Number(message.risk || 0) > 0.7) return 'critical';
  if (Number(message.risk || 0) > 0.4) return 'warning';
  return 'safe';
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node static/dashboard.test.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/index.html static/dashboard.js static/dashboard.test.mjs
git commit -m "feat: redesign dashboard for cybersecurity monitoring"
```

### Task 5: Project Cleanup and Full Verification

**Files:**
- Modify: `data/merged_dataset.csv`
- Delete or untrack: tracked `.whatsapp_session/**` files from git index
- Verify: `tests/test_app_bootstrap.py`, `tests/test_model_registry.py`, `tests/test_radar.py`, `static/dashboard.test.mjs`

- [ ] **Step 1: Consolidate the canonical dataset**

```bash
Use `data/merged_dataset.csv` as the canonical runtime dataset and keep `content,label` intact.
```

- [ ] **Step 2: Remove tracked transient WhatsApp session files from git index**

```bash
git rm -r --cached -- .whatsapp_session
```

- [ ] **Step 3: Run full backend verification**

Run: `pytest tests/test_app_bootstrap.py tests/test_model_registry.py tests/test_radar.py -v`
Expected: PASS

- [ ] **Step 4: Run frontend verification**

Run: `node static/dashboard.test.mjs`
Expected: PASS

- [ ] **Step 5: Review final repository state**

Run: `git status --short`
Expected: only intentional source, test, dataset, spec, and plan changes remain; `.whatsapp_session` should no longer appear as tracked noise.

- [ ] **Step 6: Commit**

```bash
git add data/merged_dataset.csv .gitignore docs/superpowers/plans/2026-04-30-manglish-shortlink-dashboard.md
git commit -m "chore: clean tracked transient files and finalize phishing upgrade"
```
