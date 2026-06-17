export function computeControlState({ isRunning, requestPending }) {
  return {
    startDisabled: requestPending || isRunning,
    stopDisabled: requestPending || !isRunning,
    refreshDisabled: false,
    statusText: isRunning ? 'Threat Monitoring Live' : 'Standby',
    statusClassName: isRunning ? 'status-pill status-live' : 'status-pill status-idle',
  };
}

export function shouldRunAction(action, { isRunning, requestPending }) {
  if (requestPending) {
    return false;
  }

  if (action === 'start') {
    return !isRunning;
  }

  if (action === 'stop') {
    return isRunning;
  }

  return true;
}

export function canManuallyAnalyze(message, reviewedTexts) {
  if (message.type !== 'chat' || !Boolean((message.text || '').trim())) {
    return false;
  }
  if (reviewedTexts && reviewedTexts.has(message.text.trim())) {
    return false;
  }
  return true;
}

export function shouldRunManualAnalyze(message, { analyzePending, reviewedTexts }) {
  return !analyzePending && canManuallyAnalyze(message, reviewedTexts);
}

export function canReviewManualAnalysis(message) {
  return message.type === 'manual-analysis' && Boolean((message.text || '').trim());
}

export function shouldSubmitReviewDecision(message, { decision, reviewer, reviewPending }) {
  const validDecisions = new Set(['scam', 'safe', 'needs_review']);
  return (
    !reviewPending
    && canReviewManualAnalysis(message)
    && validDecisions.has(decision)
    && Boolean((reviewer || '').trim())
  );
}

export function classifyRiskLevel(message) {
  if (message.type === 'system') {
    return 'system';
  }

  const risk = Number(message.risk || 0);
  if (risk > 0.7) {
    return 'critical';
  }
  if (risk > 0.4) {
    return 'warning';
  }
  return 'safe';
}

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function riskMeta(message) {
  const risk = Number(message.risk || 0);
  const level = classifyRiskLevel(message);

  if (level === 'system') {
    return { label: 'SYSTEM EVENT', level, score: 'N/A' };
  }
  if (level === 'critical') {
    return { label: 'CRITICAL', level, score: `${Math.round(risk * 100)}%` };
  }
  if (level === 'warning') {
    return { label: 'SUSPICIOUS', level, score: `${Math.round(risk * 100)}%` };
  }
  return { label: 'LOW RISK', level, score: `${Math.round(risk * 100)}%` };
}

function messageKicker(message) {
  if (message.type === 'system') {
    return 'System signal';
  }
  if (message.type === 'manual-analysis') {
    return 'Manual analysis';
  }
  if (message.type === 'review-decision') {
    return 'Analyst review';
  }
  return 'Intercepted message';
}

function reviewDecisionLabel(decision) {
  if (decision === 'needs_review') {
    return 'Needs Review';
  }
  if (decision === 'scam') {
    return 'Marked Scam';
  }
  if (decision === 'safe') {
    return 'Marked Safe';
  }
  return 'Review Decision';
}

function loadReviewedTexts() {
  try {
    const stored = localStorage.getItem('reviewedTexts');
    return stored ? new Set(JSON.parse(stored)) : new Set();
  } catch {
    return new Set();
  }
}

function saveReviewedTexts(texts) {
  try {
    localStorage.setItem('reviewedTexts', JSON.stringify([...texts]));
  } catch {
    // localStorage full or unavailable - ignore
  }
}

function initDashboard() {
  const feedList = document.getElementById('feedList');
  const statusBadge = document.getElementById('statusBadge');
  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  const refreshBtn = document.getElementById('refreshBtn');
  const eventCount = document.getElementById('eventCount');
  const criticalCount = document.getElementById('criticalCount');
  const safeCount = document.getElementById('safeCount');

  if (!feedList || !statusBadge || !startBtn || !stopBtn || !refreshBtn) {
    return;
  }

  const state = {
    isRunning: false,
    requestPending: false,
    analyzePending: false,
    reviewPending: false,
    messages: [],
    reviewedTexts: loadReviewedTexts(),
  };

  function syncControls() {
    const controlState = computeControlState(state);
    statusBadge.textContent = controlState.statusText;
    statusBadge.className = controlState.statusClassName;
    startBtn.disabled = controlState.startDisabled;
    stopBtn.disabled = controlState.stopDisabled;
    refreshBtn.disabled = controlState.refreshDisabled;
  }

  function updateStats() {
    if (eventCount) {
      eventCount.textContent = String(state.messages.length);
    }
    if (criticalCount) {
      criticalCount.textContent = String(
        state.messages.filter((message) => classifyRiskLevel(message) === 'critical').length,
      );
    }
    if (safeCount) {
      safeCount.textContent = String(
        state.messages.filter((message) => classifyRiskLevel(message) === 'safe').length,
      );
    }
  }

  function renderMessage(message, prepend = true) {
    const meta = riskMeta(message);
    const wrapper = document.createElement('article');
    wrapper.className = `feed-entry risk-${meta.level}`;
    const showAnalyzeButton = canManuallyAnalyze(message, state.reviewedTexts);
    const showReviewControls = canReviewManualAnalysis(message);
    const title = message.type === 'review-decision' ? reviewDecisionLabel(message.decision) : meta.label;
    wrapper.innerHTML = `
      <div class="entry-header">
        <div>
          <p class="entry-kicker">${escapeHtml(messageKicker(message))}</p>
          <h3 class="entry-title">${escapeHtml(title)}</h3>
        </div>
        <div class="entry-score">${escapeHtml(meta.score)}</div>
      </div>
      <p class="entry-text">${escapeHtml(message.text || '')}</p>
      ${message.type === 'review-decision' ? `<p class="review-note">Reviewer: ${escapeHtml(message.reviewer || '')}</p>` : ''}
      ${showAnalyzeButton ? '<div class="entry-actions"><button type="button" class="analyze-btn">Analyze Message</button></div>' : ''}
      ${showReviewControls ? `
        <div class="review-panel">
          <label class="review-label">
            Reviewer
            <input type="text" class="reviewer-input" placeholder="Enter reviewer name" />
          </label>
          <div class="entry-actions review-actions">
            <button type="button" class="review-btn" data-decision="scam">Mark Scam</button>
            <button type="button" class="review-btn" data-decision="safe">Mark Safe</button>
            <button type="button" class="review-btn" data-decision="needs_review">Needs Review</button>
          </div>
        </div>
      ` : ''}
    `;

    if (showAnalyzeButton) {
      const analyzeBtn = wrapper.querySelector('.analyze-btn');
      if (analyzeBtn) {
        analyzeBtn.dataset.messageText = message.text || '';
        analyzeBtn.disabled = state.analyzePending;
      }
    }

    if (showReviewControls) {
      wrapper.querySelectorAll('.review-btn').forEach((button) => {
        button.disabled = state.reviewPending;
        button.dataset.messageText = message.text || '';
        button.dataset.risk = String(Number(message.risk || 0));
      });
      const reviewerInput = wrapper.querySelector('.reviewer-input');
      if (reviewerInput) {
        reviewerInput.disabled = state.reviewPending;
      }
    }

    if (prepend) {
      feedList.prepend(wrapper);
      state.messages.unshift(message);
      state.messages = state.messages.slice(0, 50);
      if (feedList.children.length > 50) {
        feedList.removeChild(feedList.lastElementChild);
      }
    } else {
      feedList.appendChild(wrapper);
    }
  }

  function renderSnapshot(snapshot) {
    state.isRunning = Boolean(snapshot.is_running);
    state.messages = [...snapshot.messages].reverse();
    syncControls();
    feedList.innerHTML = '';
    state.messages.forEach((message) => renderMessage(message, false));
    updateStats();
  }

  function syncAnalyzeButtons() {
    feedList.querySelectorAll('.analyze-btn').forEach((button) => {
      button.disabled = state.analyzePending;
    });
  }

  function syncReviewControls() {
    feedList.querySelectorAll('.review-btn').forEach((button) => {
      button.disabled = state.reviewPending;
    });
    feedList.querySelectorAll('.reviewer-input').forEach((input) => {
      input.disabled = state.reviewPending;
    });
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: 'POST',
      headers: payload ? { 'Content-Type': 'application/json' } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || 'Request failed');
    }
    return data;
  }

  async function refreshSnapshot() {
    const response = await fetch('/api/status');
    const data = await response.json();
    renderSnapshot(data);
  }

  async function runAction(action, url) {
    if (!shouldRunAction(action, state)) {
      return;
    }

    state.requestPending = true;
    syncControls();

    try {
      await postJson(url);
    } catch (error) {
      alert(error.message);
    } finally {
      state.requestPending = false;
      syncControls();
    }
  }

  startBtn.addEventListener('click', async () => {
    await runAction('start', '/api/monitor/start');
  });

  stopBtn.addEventListener('click', async () => {
    await runAction('stop', '/api/monitor/stop');
  });

  refreshBtn.addEventListener('click', refreshSnapshot);
  feedList.addEventListener('click', async (event) => {
    const button = event.target.closest('.analyze-btn');
    if (button) {
      const message = { type: 'chat', text: button.dataset.messageText || '' };
      if (!shouldRunManualAnalyze(message, state)) {
        return;
      }

      state.analyzePending = true;
      syncAnalyzeButtons();

      try {
        await postJson('/api/messages/analyze', { text: message.text });
      } catch (error) {
        alert(error.message);
      } finally {
        state.analyzePending = false;
        syncAnalyzeButtons();
      }
      return;
    }

    const reviewButton = event.target.closest('.review-btn');
    if (reviewButton) {
      const reviewPanel = reviewButton.closest('.review-panel');
      const reviewerInput = reviewPanel?.querySelector('.reviewer-input');
      const message = {
        type: 'manual-analysis',
        text: reviewButton.dataset.messageText || '',
        risk: Number(reviewButton.dataset.risk || 0),
      };
      const payload = {
        message_text: message.text,
        risk_score: Number(message.risk || 0),
        decision: reviewButton.dataset.decision || '',
        reviewer: reviewerInput?.value || '',
      };

      if (!shouldSubmitReviewDecision(message, { ...payload, reviewPending: state.reviewPending })) {
        alert('Reviewer name is required and decision must be valid.');
        return;
      }

      state.reviewPending = true;
      syncReviewControls();

      try {
        await postJson('/api/messages/review', payload);
        state.reviewedTexts.add(message.text.trim());
        saveReviewedTexts(state.reviewedTexts);
      } catch (error) {
        alert(error.message);
      } finally {
        state.reviewPending = false;
        syncReviewControls();
      }
    }
  });

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws/feed`);

  ws.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.event === 'snapshot') {
      renderSnapshot(payload.data);
    } else if (payload.event === 'message') {
      renderMessage(payload.data);
      updateStats();
    } else if (payload.event === 'status') {
      state.isRunning = Boolean(payload.data.is_running);
      syncControls();
    }
  };

  ws.onclose = () => {
    state.isRunning = false;
    state.requestPending = false;
    state.reviewPending = false;
    syncControls();
  };

  syncControls();
  updateStats();
}

if (typeof document !== 'undefined') {
  initDashboard();
}
