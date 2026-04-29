import assert from 'node:assert/strict';

import {
  classifyRiskLevel,
  computeControlState,
  shouldRunAction,
} from './dashboard.js';

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

assert.deepEqual(
  computeControlState({ isRunning: false, requestPending: true }),
  {
    startDisabled: true,
    stopDisabled: true,
    refreshDisabled: false,
    statusText: 'Standby',
    statusClassName: 'status-pill status-idle',
  },
);

assert.equal(classifyRiskLevel({ type: 'chat', risk: 0.82 }), 'critical');
assert.equal(classifyRiskLevel({ type: 'chat', risk: 0.52 }), 'warning');
assert.equal(classifyRiskLevel({ type: 'chat', risk: 0.15 }), 'safe');
assert.equal(classifyRiskLevel({ type: 'system', risk: 0.1 }), 'system');

assert.equal(
  shouldRunAction('start', { isRunning: true, requestPending: false }),
  false,
);
assert.equal(
  shouldRunAction('stop', { isRunning: false, requestPending: false }),
  false,
);
assert.equal(
  shouldRunAction('start', { isRunning: false, requestPending: true }),
  false,
);
assert.equal(
  shouldRunAction('start', { isRunning: false, requestPending: false }),
  true,
);
