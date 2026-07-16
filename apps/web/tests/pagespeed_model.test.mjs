import assert from 'node:assert/strict';
import test from 'node:test';
import { auditState, deviceOutcome, flattenAudits, latestByStrategy, normalizeClientUrl } from '../src/pagespeedModel.mjs';

test('client URL validation normalizes fragment/default port and rejects unsafe targets', () => {
  assert.equal(normalizeClientUrl('HTTPS://Example.com:443/path?q=1#x'), 'https://example.com/path?q=1');
  assert.throws(() => normalizeClientUrl('ftp://example.com'));
  assert.throws(() => normalizeClientUrl('https://user:pass@example.com'));
  assert.throws(() => normalizeClientUrl('http://127.0.0.1'));
});

test('audit states preserve null/manual/informative/not-applicable and passing evidence', () => {
  assert.equal(auditState({ scoreDisplayMode: 'manual', score: null }), 'manual');
  assert.equal(auditState({ scoreDisplayMode: 'informative', score: null }), 'informative');
  assert.equal(auditState({ scoreDisplayMode: 'notApplicable', score: null }), 'notApplicable');
  assert.equal(auditState({ scoreDisplayMode: 'numeric', score: null }), 'unscored');
  assert.equal(auditState({ scoreDisplayMode: 'binary', score: 1 }), 'passed');
  assert.equal(auditState({ scoreDisplayMode: 'numeric', score: 0 }), 'needsAttention');
});

test('audit model keeps category/group, source savings, and unknown detail fallback', () => {
  const rows = flattenAudits({
    categoryAuditRefs: { performance: [{ id: 'a', group: 'load-opportunities', weight: 3 }] },
    audits: {
      a: { title: 'Audit A', score: 0.4, scoreDisplayMode: 'metricSavings', details: { type: 'opportunity', overallSavingsMs: 250, overallSavingsBytes: 1024 } },
      b: { title: 'Audit B', score: null, scoreDisplayMode: 'informative', details: { type: 'future-shape', evidence: true } },
    },
  });
  assert.deepEqual(rows[0].categories, ['performance']);
  assert.deepEqual(rows[0].groups, ['load-opportunities']);
  assert.equal(rows[0].savingsMs, 250);
  assert.equal(rows[1].detailType, 'future-shape');
});

test('latest device and independent partial outcomes remain separate', () => {
  const map = latestByStrategy([{ status: 'success', strategy: 'desktop', savedAt: '2' }, { status: 'success', strategy: 'mobile', savedAt: '1' }]);
  assert.equal(map.mobile.savedAt, '1');
  assert.equal(map.desktop.savedAt, '2');
  assert.equal(deviceOutcome({ mobile: { ok: true }, desktop: { ok: false } }), 'partial');
  assert.equal(deviceOutcome({ mobile: { ok: true }, desktop: { ok: true } }), 'success');
});
