import assert from 'node:assert/strict';

import { computeControlState, shouldRunAction } from './dashboard.js';

assert.deepEqual(
  computeControlState({ isRunning: true, requestPending: false }),
  {
    startDisabled: true,
    stopDisabled: false,
    refreshDisabled: false,
    statusText: 'Monitoring Active',
    statusClassName: 'badge text-bg-success fs-6 px-3 py-2',
  },
);

assert.deepEqual(
  computeControlState({ isRunning: false, requestPending: true }),
  {
    startDisabled: true,
    stopDisabled: true,
    refreshDisabled: false,
    statusText: 'Inactive',
    statusClassName: 'badge text-bg-secondary fs-6 px-3 py-2',
  },
);

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
