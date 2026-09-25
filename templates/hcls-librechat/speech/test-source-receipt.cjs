const test = require('node:test');
const assert = require('node:assert/strict');
const { sourceReceipt } = require('./diarization.cjs');
test('raw browser ASR source is finalized, consistent, and timing-bound before capture', () => {
  const value = { schema: 'scientific-clinical/browser-asr-source/v1', raw_transcript: 'No fever.',
    segments: [{ id: '0', text: 'No fever.', final: true, revision: 1 }],
    timings: Object.fromEntries(['ready_at', 'audio_start_at', 'input_end_at', 'completed_at'].map(name => [name, '2026-09-25T00:00:00Z'])) };
  assert.equal(sourceReceipt(value), value);
  assert.throws(() => sourceReceipt(null), /raw ASR/);
  assert.throws(() => sourceReceipt({ ...value, raw_transcript: 'edited' }), /do not match/);
  assert.throws(() => sourceReceipt({ ...value, segments: [{ ...value.segments[0], final: false }] }), /raw ASR/);
  assert.throws(() => sourceReceipt({ ...value, timings: {} }), /timing evidence/);
});
