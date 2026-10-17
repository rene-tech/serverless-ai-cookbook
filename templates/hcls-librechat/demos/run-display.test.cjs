const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.env.TYPESCRIPT_MODULE || 'typescript');
const source = ts.transpileModule(fs.readFileSync(`${__dirname}/run-display.ts`, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exported = {};
vm.runInNewContext(source, { exports: exported });
test('artifact reservations are not displayed or cancelled as model jobs', () => {
  const ui = fs.readFileSync(`${__dirname}/Demos.tsx`, 'utf8');
  assert.doesNotMatch(ui, /Cancel upload|display\.upload/);
  assert.doesNotMatch(source, /scientific-artifact-upload-v1/);
});
test('ordinary inference preserves status, preemption and result availability', () => {
  assert.equal(exported.runDisplay({ protocol: 'scientific-batch-v1', status: 'succeeded' }).showResult, true);
  assert.equal(exported.runDisplay({ status: 'preempted' }).terminal, true);
  assert.equal(exported.runDisplay({ status: 'queued' }).description, 'Accepted; execution has not started');
});
test('batch orchestration does not masquerade as admitted GPU execution', () => {
  for (const shape of [{ protocol: 'scientific-batch-v1' }, { operation: { protocol: 'scientific-batch-v1' } }]) {
    const active = exported.runDisplay({ ...shape, status: 'running' });
    assert.equal(active.status, 'Workflow active');
    assert.equal(active.showComputeTiming, false);
    assert.match(active.description, /queued, loading or computing/);
    assert.match(active.description, /Details/);
    for (const status of ['succeeded', 'failed', 'cancelled', 'preempted', 'expired']) {
      const terminal = exported.runDisplay({ ...shape, status });
      assert.equal(terminal.status, status);
      assert.equal(terminal.terminal, true);
      assert.equal(terminal.showComputeTiming, false);
      assert.equal(terminal.description, '');
    }
  }
});
test('accepted-to-ready includes queue instead of claiming activation time', () => {
  const display = exported.runDisplay({ protocol: 'openai-chat', status: 'succeeded' });
  assert.equal(display.showComputeTiming, true);
  assert.equal(display.readyTimingLabel, 'Accepted → ready (includes queue)');
  assert.match(fs.readFileSync(`${__dirname}/Demos.tsx`, 'utf8'), /display\.readyTimingLabel/);
});

test('a completed polling window does not imply study or model timeout', () => {
  const display = exported.studyDisplay('observation_expired');
  assert.equal(display.status, 'Waiting for an update');
  assert.match(display.description, /not the study/);
  assert.match(display.description, /while the study supervisor is available/);
  assert.doesNotMatch(display.status, /failed|expired|completed|succeeded/);
});
test('admission waiting and read reconnection do not imply new or repeated inference', () => {
  assert.equal(exported.studyDisplay('waiting_admission').status, 'Waiting to start');
  assert.match(exported.studyDisplay('waiting_admission').description, /has not been accepted/);
  assert.equal(exported.studyDisplay('observation_interrupted').status, 'Reconnecting to the existing operation');
  assert.match(exported.studyDisplay('observation_interrupted').description, /do not submit another copy/);
});
test('terminal and unknown study states remain explicit', () => {
  for (const state of ['completed', 'failed', 'cancelled', 'needs_attention', 'future_unknown_state']) {
    assert.equal(exported.studyDisplay(state).status, state);
    assert.equal(exported.studyDisplay(state).description, '');
  }
});
test('Runs uses the label while retaining the actual recorded state and cancellation policy', () => {
  const ui = fs.readFileSync(`${__dirname}/Demos.tsx`, 'utf8');
  assert.match(ui, /studyDisplay\(study\.state\)/);
  assert.match(ui, /Recorded state: \$\{study\.state\}/);
  assert.match(ui, /\['completed', 'failed', 'cancelled', 'needs_attention'\]\.includes\(study\.state\)/);
});

const scientificProgress = (patch = {}, rowPatch = {}) => ({ schema: 'scientific-ai/progress/v1', available: true,
  updated_at: '2026-10-16T12:00:00Z', stale: false, stale_after_seconds: 120,
  steps: [{ step_id: 'production', state: 'running', unit: 'ns', completed_units: 4.25,
    durable_completed_units: 4, target_units: 10, rate: 200.5, rate_unit: 'ns/day',
    observed_at: '2026-10-16T12:00:00Z', durable_at: '2026-10-16T11:59:00Z',
    rate_updated_at: '2026-10-16T12:00:00Z', ...rowPatch }], ...patch });
const clock = Date.parse('2026-10-16T12:01:00Z');
test('scientific progress separates observed, durable and requested quantities without hardware', () => {
  const value = exported.scientificProgressDisplay(scientificProgress({}, { gpu_count: 8, gpu_type: 'fixture-device' }), clock);
  assert.equal(value.rows[0].completed, '4.25 ns');
  assert.equal(value.rows[0].durable, '4 ns');
  assert.equal(value.rows[0].target, '10 ns');
  assert.equal(value.rows[0].rate, '200.5 ns/day');
  assert.equal(value.rows[0].freshness, 'Latest observation');
  assert.ok(!JSON.stringify(value).includes('fixture-device'));
  assert.ok(!JSON.stringify(value).includes('gpu'));
});
test('non-MD models retain their own scientific units and measured rate units', () => {
  const row = exported.scientificProgressDisplay(scientificProgress({}, { unit: 'structures', completed_units: 7,
    target_units: 20, durable_completed_units: 5, rate: 0.5, rate_unit: 'structures/s' }), clock).rows[0];
  assert.equal(row.completed, '7 structures');
  assert.equal(row.rate, '0.5 structures/s');
});
test('missing or invalid measurements remain unknown, while measured zero stays zero', () => {
  for (const missing of [null, NaN, -1, '25']) {
    const row = exported.scientificProgressDisplay(scientificProgress({}, { completed_units: missing,
      durable_completed_units: missing, rate: missing }), clock).rows[0];
    assert.equal(row.completed, 'Unknown'); assert.equal(row.durable, 'Unknown'); assert.equal(row.rate, 'Unknown');
  }
  assert.equal(exported.scientificProgressDisplay(scientificProgress({}, { completed_units: 0 }), clock).rows[0].completed, '0 ns');
  assert.equal(exported.scientificProgressDisplay(undefined), null);
  assert.equal(exported.scientificProgressDisplay({ schema: 'future/unrecognized' }), null);
});
test('a retained snapshot expires without pretending that the UI refresh measured new progress', () => {
  const row = exported.scientificProgressDisplay(scientificProgress(), clock + 120000).rows[0];
  assert.equal(row.stale, true); assert.equal(row.rateStale, true);
  assert.equal(row.freshness, 'Stale observation'); assert.equal(row.completed, '4.25 ns');
  const freshProgressOldRate = exported.scientificProgressDisplay(scientificProgress({}, {
    rate_updated_at: '2026-10-16T11:50:00Z' }), clock).rows[0];
  assert.equal(freshProgressOldRate.stale, false); assert.equal(freshProgressOldRate.rateStale, true);
  const missingTimestamp = exported.scientificProgressDisplay(scientificProgress({ updated_at: null }, {
    observed_at: null, rate_updated_at: null }), clock).rows[0];
  assert.equal(missingTimestamp.freshness, 'Observation freshness unknown');
});
test('resumed progress is the server measurement, never summed with the earlier attempt', () => {
  exported.scientificProgressDisplay(scientificProgress(), clock);
  const resumed = exported.scientificProgressDisplay(scientificProgress({}, {
    completed_units: 4.1, durable_completed_units: 4, rate: null }), clock).rows[0];
  assert.equal(resumed.completed, '4.1 ns'); assert.equal(resumed.durable, '4 ns'); assert.equal(resumed.rate, 'Unknown');
});
test('customer Apps have no GPU allocation badge and both run surfaces render progress', () => {
  const ui = fs.readFileSync(`${__dirname}/Demos.tsx`, 'utf8');
  assert.doesNotMatch(ui, /gpu_class|gpu_count/);
  assert.match(ui, /ScientificProgressView progress=\{run\.operation\?\.progress\}/);
  assert.match(ui, /ScientificProgressView progress=\{item\.progress\}/);
});
