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
    messages: [],
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
    wrapper.innerHTML = `
      <div class="entry-header">
        <div>
          <p class="entry-kicker">${escapeHtml(message.type === 'system' ? 'System signal' : 'Intercepted message')}</p>
          <h3 class="entry-title">${escapeHtml(meta.label)}</h3>
        </div>
        <div class="entry-score">${escapeHtml(meta.score)}</div>
      </div>
      <p class="entry-text">${escapeHtml(message.text || '')}</p>
    `;

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

  async function postJson(url) {
    const response = await fetch(url, { method: 'POST' });
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
    syncControls();
  };

  syncControls();
  updateStats();
}

if (typeof document !== 'undefined') {
  initDashboard();
}
