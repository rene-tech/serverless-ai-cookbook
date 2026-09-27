const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const WebSocket = require('ws');
const { transcribeFile } = require('./native-file.cjs');
async function fixture(t, behavior) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'native-file-test-'));
  const { wavBlob } = await import('./speech-state.js');
  const source = path.join(directory, 'source.wav');
  await fs.writeFile(source, Buffer.from(await wavBlob([new ArrayBuffer(32000)]).arrayBuffer()));
  const server = new WebSocket.Server({ port: 0, host: '127.0.0.1' });
  await new Promise(resolve => server.once('listening', resolve));
  let connections = 0;
  server.on('connection', ws => { connections++; behavior(ws); });
  t.after(async () => { for (const ws of server.clients) ws.terminate(); await new Promise(resolve => server.close(resolve)); });
  return { source, directory: path.join(directory, 'receipts'),
    backend: { url: 'https://pinned.invalid/v1/audio/stream', model: 'nemotron-speech-en-0.6b' },
    credential: 'synthetic-only', deadlineMs: 5000,
    connect: (_url, options) => new WebSocket(`ws://127.0.0.1:${server.address().port}`, options), connections: () => connections };
}
test('file batch preserves exact final text, duration, native identity and immutable cache', async t => {
  const options = await fixture(t, ws => {
    let count = 0;
    ws.on('message', (data, binary) => {
      if (binary) { count += data.length; return; }
      const event = JSON.parse(data);
      if (event.type === 'session.start') {
        assert.equal(event.options.output_granularity, 'word');
        ws.send(JSON.stringify({ type: 'session.ready', session_id: 'native-test' }));
      }
      if (event.type === 'input.finish') {
        ws.send(JSON.stringify({ type: 'transcript.partial', sequence: 1, text: 'wrong', revision: 1 }));
        ws.send(JSON.stringify({ type: 'transcript.final', sequence: 1, text: 'No fever.', revision: 2, items: [{ text: 'No', start_seconds: 0, end_seconds: .2 }, { text: 'fever.', start_seconds: .2, end_seconds: .8 }] }));
        ws.send(JSON.stringify({ type: 'session.completed', session_id: 'native-test', audio_seconds: count / 32000 }));
      }
    });
  });
  const result = await transcribeFile(options);
  assert.equal(result.receipt.audio_seconds, 1);
  const raw = JSON.parse(await fs.readFile(result.path));
  assert.equal(raw.text, 'No fever.'); assert.equal(raw.platform_operation_id, null);
  assert.equal(raw.runtime_session_id, 'native-test'); assert.equal(raw.words.length, 2);
  assert(!String(await fs.readFile(path.join(options.directory, 'request.json'))).includes('synthetic-only'));
  assert.equal((await transcribeFile(options)).cached, true); assert.equal(options.connections(), 1);
  await assert.rejects(transcribeFile({ ...options, backend: { ...options.backend, model: 'other' } }), /source_or_backend_changed/);
});
test('ambiguous disconnect is retained and never automatically replays audio', async t => {
  const options = await fixture(t, ws => ws.on('message', () => ws.close()));
  await assert.rejects(transcribeFile(options), /disconnect_admission_unknown/);
  await assert.rejects(transcribeFile(options), /admission_unknown_no_automatic_replay/);
  assert.equal(options.connections(), 1);
  assert.equal(JSON.parse(await fs.readFile(path.join(options.directory, 'failure.json'))).automatic_replay, false);
});
test('file batch honors explicit native separator while preserving raw event and word evidence', async t => {
  const options = await fixture(t, ws => {
    let count = 0;
    ws.on('message', (data, binary) => {
      if (binary) { count += data.length; return; }
      const event = JSON.parse(data);
      if (event.type === 'session.start') ws.send(JSON.stringify({ type: 'session.ready', session_id: 'native-hint' }));
      if (event.type === 'input.finish') {
        ws.send(JSON.stringify({ type: 'transcript.final', segment_id: 0, revision: 1, text: 'Hi', items: [{ text: 'Hi', start_seconds: 0, end_seconds: .2 }] }));
        ws.send(JSON.stringify({ type: 'transcript.final', segment_id: 1, revision: 1, text: 'shall', separator_before: ' ', items: [{ text: 'shall', start_seconds: .3, end_seconds: .5 }] }));
        ws.send(JSON.stringify({ type: 'session.completed', audio_seconds: count / 32000 }));
      }
    });
  });
  const result = await transcribeFile(options);
  const raw = JSON.parse(await fs.readFile(result.path));
  assert.equal(raw.text, 'Hi shall');
  assert.equal(raw.words[1].text, 'shall');
  assert.equal(raw.words[1].render_text, ' shall');
  const events = (await fs.readFile(path.join(options.directory, 'events.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  const final = events.find(row => row.event.segment_id === 1).event;
  assert.equal(final.text, 'shall'); assert.equal(final.separator_before, ' ');
});
test('unfinalized partial cannot become a cached successful transcript', async t => {
  const options = await fixture(t, ws => {
    let count = 0;
    ws.on('message', (data, binary) => {
      if (binary) { count += data.length; return; }
      const event = JSON.parse(data);
      if (event.type === 'session.start') ws.send(JSON.stringify({ type: 'session.ready' }));
      if (event.type === 'input.finish') {
        ws.send(JSON.stringify({ type: 'transcript.partial', sequence: 1, text: 'unverified' }));
        ws.send(JSON.stringify({ type: 'session.completed', audio_seconds: count / 32000 }));
      }
    });
  });
  await assert.rejects(transcribeFile(options), /unfinalized_partial/);
  await assert.rejects(fs.access(path.join(options.directory, 'receipt.json')));
});
test('abort sends explicit cancel and blocks transparent resume', async t => {
  const controller = new AbortController(); let cancelled;
  const observed = new Promise(resolve => { cancelled = resolve; });
  const options = await fixture(t, ws => ws.on('message', data => {
    let event; try { event = JSON.parse(data); } catch { return; }
    if (event.type === 'session.start') controller.abort();
    if (event.type === 'session.cancel') cancelled();
  }));
  await assert.rejects(transcribeFile({ ...options, signal: controller.signal }), /cancelled_admission_unknown/);
  await observed;
  await assert.rejects(transcribeFile(options), /admission_unknown_no_automatic_replay/);
});
