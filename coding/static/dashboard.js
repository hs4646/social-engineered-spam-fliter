export function computeControlState({ isRunning, requestPending }) {
  return {
    startDisabled: requestPending || isRunning,
    stopDisabled: requestPending || !isRunning,
    refreshDisabled: false,
    statusText: isRunning ? 'Monitoring Active' : 'Inactive',
    statusClassName: isRunning
      ? 'badge text-bg-success fs-6 px-3 py-2'
      : 'badge text-bg-secondary fs-6 px-3 py-2',
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
  if (message.type === 'system') {
    return { label: 'SYSTEM', css: 'text-bg-info' };
  }
  if (risk > 0.7) {
    return { label: `CRITICAL ${Math.round(risk * 100)}%`, css: 'text-bg-danger' };
  }
  if (risk > 0.4) {
    return { label: `SUSPICIOUS ${Math.round(risk * 100)}%`, css: 'text-bg-warning' };
  }
  return { label: `SAFE ${Math.round(risk * 100)}%`, css: 'text-bg-success' };
}

function initDashboard() {
  const feedList = document.getElementById('feedList');
  const statusBadge = document.getElementById('statusBadge');
  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  const refreshBtn = document.getElementById('refreshBtn');

  if (!feedList || !statusBadge || !startBtn || !stopBtn || !refreshBtn) {
    return;
  }

  const state = {
    isRunning: false,
    requestPending: false,
  };

  function syncControls() {
    const controlState = computeControlState(state);
    statusBadge.textContent = controlState.statusText;
    statusBadge.className = controlState.statusClassName;
    startBtn.disabled = controlState.startDisabled;
    stopBtn.disabled = controlState.stopDisabled;
    refreshBtn.disabled = controlState.refreshDisabled;
  }

  function renderMessage(message, prepend = true) {
    const meta = riskMeta(message);
    const wrapper = document.createElement('div');
    wrapper.className = 'border rounded-4 bg-white p-3';
    wrapper.innerHTML = `
      <div class="d-flex justify-content-between align-items-start gap-3">
        <div>
          <div class="fw-semibold mb-2">${escapeHtml(message.type === 'system' ? 'System event' : 'Intercepted message')}</div>
          <div class="text-secondary">${escapeHtml(message.text || '')}</div>
        </div>
        <span class="badge ${meta.css} risk-badge">${meta.label}</span>
      </div>
    `;

    if (prepend) {
      feedList.prepend(wrapper);
    } else {
      feedList.appendChild(wrapper);
    }
  }

  function renderSnapshot(snapshot) {
    state.isRunning = Boolean(snapshot.is_running);
    syncControls();
    feedList.innerHTML = '';
    [...snapshot.messages].reverse().forEach((message) => renderMessage(message, false));
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
}

if (typeof document !== 'undefined') {
  initDashboard();
}
