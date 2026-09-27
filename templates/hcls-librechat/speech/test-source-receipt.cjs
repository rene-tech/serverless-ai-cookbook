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
test('source receipt honors only explicit native separator hints and keeps raw segments', () => {
  const value = { schema: 'scientific-clinical/browser-asr-source/v1', raw_transcript: 'hi shall',
    segments: [{ id: '0', text: 'hi', final: true, revision: 1 }, { id: '1', text: 'shall', final: true, revision: 2, separator_before: ' ' }],
    timings: Object.fromEntries(['ready_at', 'audio_start_at', 'input_end_at', 'completed_at'].map(name => [name, '2026-09-27T11:23:00Z'])) };
  assert.equal(sourceReceipt(value), value);
  assert.equal(value.segments[1].text, 'shall');
  assert.throws(() => sourceReceipt({ ...value, raw_transcript: 'hishall' }), /do not match/);
  assert.throws(() => sourceReceipt({ ...value, segments: [value.segments[0], { ...value.segments[1], separator_before: 'x' }] }), /Invalid native separator/);
});
