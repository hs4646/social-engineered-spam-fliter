import assert from 'node:assert/strict';

import {
  canReviewManualAnalysis,
  canManuallyAnalyze,
  shouldSubmitReviewDecision,
  classifyRiskLevel,
  computeControlState,
  shouldRunManualAnalyze,
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

// canManuallyAnalyze - basic tests
assert.equal(
  canManuallyAnalyze({ type: 'chat', text: 'Suspicious login link' }, new Set()),
  true,
);
assert.equal(
  canManuallyAnalyze({ type: 'system', text: 'System event' }, new Set()),
  false,
);

// canManuallyAnalyze - must be available on ALL chat risk levels, including
// high-risk messages above the 0.8 threshold (and above the 0.9 auto-send).
assert.equal(
  canManuallyAnalyze({ type: 'chat', text: 'High risk link', risk: 0.82 }, new Set()),
  true,
);
assert.equal(
  canManuallyAnalyze({ type: 'chat', text: 'Critical verify now', risk: 0.9 }, new Set()),
  true,
);
assert.equal(
  canManuallyAnalyze({ type: 'chat', text: 'Highest risk verify now', risk: 0.95 }, new Set()),
  true,
);

// canManuallyAnalyze - reviewedTexts tests
assert.equal(
  canManuallyAnalyze({ type: 'chat', text: 'test message' }, new Set(['test message'])),
  false,
);
assert.equal(
  canManuallyAnalyze({ type: 'chat', text: 'test message' }, new Set(['other message'])),
  true,
);
assert.equal(
  canManuallyAnalyze({ type: 'chat', text: 'test message' }, undefined),
  true,
);

// shouldRunManualAnalyze tests
assert.equal(
  shouldRunManualAnalyze(
    { type: 'chat', text: 'Suspicious login link' },
    { analyzePending: false, reviewedTexts: new Set() },
  ),
  true,
);
assert.equal(
  shouldRunManualAnalyze(
    { type: 'chat', text: 'Suspicious login link' },
    { analyzePending: true, reviewedTexts: new Set() },
  ),
  false,
);
assert.equal(
  shouldRunManualAnalyze(
    { type: 'chat', text: 'Already reviewed message' },
    { analyzePending: false, reviewedTexts: new Set(['Already reviewed message']) },
  ),
  false,
);

// canReviewManualAnalysis tests
assert.equal(
  canReviewManualAnalysis({ type: 'manual-analysis', text: 'Suspicious login link', risk: 0.88 }),
  true,
);
assert.equal(
  canReviewManualAnalysis({ type: 'chat', text: 'Suspicious login link', risk: 0.88 }),
  false,
);

// shouldSubmitReviewDecision tests
assert.equal(
  shouldSubmitReviewDecision(
    { type: 'manual-analysis', text: 'Suspicious login link', risk: 0.88 },
    { decision: 'scam', reviewer: 'Han Shen', reviewPending: false },
  ),
  true,
);
assert.equal(
  shouldSubmitReviewDecision(
    { type: 'manual-analysis', text: 'Suspicious login link', risk: 0.88 },
    { decision: 'safe', reviewer: '   ', reviewPending: false },
  ),
  false,
);
assert.equal(
  shouldSubmitReviewDecision(
    { type: 'manual-analysis', text: 'Suspicious login link', risk: 0.88 },
    { decision: 'allow', reviewer: 'Han Shen', reviewPending: false },
  ),
  false,
);
