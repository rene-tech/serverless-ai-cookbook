import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { transcriptEvent, wavBlob } from './speech-state.js';
test('partial revisions replace text and finalized segments do not regress', () => {
  const map = new Map();
  assert.equal(transcriptEvent(map, { type: 'transcript.partial', segment_id: 'a', revision: 1, text: 'meta' }), 'meta');
  assert.equal(transcriptEvent(map, { type: 'transcript.partial', segment_id: 'a', revision: 2, text: 'metformin' }), 'metformin');
  assert.equal(transcriptEvent(map, { type: 'transcript.final', segment_id: 'a', revision: 3, text: 'metformin 500 mg' }), 'metformin 500 mg');
  assert.equal(transcriptEvent(map, { type: 'transcript.partial', segment_id: 'a', revision: 4, text: 'wrong' }), 'metformin 500 mg');
  assert.equal(transcriptEvent(map, { type: 'transcript.final', segment_id: 'b', revision: 1, text: 'twice daily' }), 'metformin 500 mg twice daily');
});
test('WAV is mono PCM16 16k with exact captured bytes', async () => {
  const bytes = await wavBlob([new Uint8Array([1, 2, 3, 4]).buffer]).arrayBuffer();
  const view = new DataView(bytes);
  assert.equal(view.getUint32(24, true), 16000); assert.equal(view.getUint16(22, true), 1);
  assert.equal(view.getUint32(40, true), 4); assert.deepEqual([...new Uint8Array(bytes).slice(44)], [1, 2, 3, 4]);
});
test('48k AudioWorklet resamples exactly across render quanta and flushes PCM LE', async () => {
  const code = await readFile(new URL('./pcm-worklet.js', import.meta.url), 'utf8');
  const frames = []; let Processor;
  vm.runInNewContext(code, { AudioWorkletProcessor: class { constructor() { this.port = { postMessage: (value) => frames.push(value) }; } },
    sampleRate: 48000, registerProcessor: (_name, value) => { Processor = value; } });
  const processor = new Processor();
  for (let offset = 0; offset < 48000; offset += 128) processor.process([[new Float32Array(Math.min(128, 48000 - offset)).fill(0.5)]]);
  processor.flush();
  assert.equal(frames.reduce((total, frame) => total + frame.byteLength, 0), 32000);
  assert.equal(new DataView(frames[0]).getInt16(0, true), 16384);
});
