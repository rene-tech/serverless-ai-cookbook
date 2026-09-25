const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const crypto = require('node:crypto');
const { once } = require('node:events');
const WebSocket = require('/app/node_modules/ws');
const { attach, issueTicket, targets } = require('./relay.cjs');
class LocalWebSocket extends WebSocket { constructor(url, options) { super(url.replace('wss://', 'ws://'), options); } }
const operation = '243236ef-8af2-4dc6-85a4-c504b68c1b52';
test('three ordered modes bind the two medical choices to the exact same endpoint/model/credential', () => {
  const modes = targets({ SCIENTIFIC_MEDICAL_SPEECH_URL: 'https://medical.test/v1/audio/stream', SCIENTIFIC_MEDICAL_SPEECH_MODEL: 'qualified-round2', SCIENTIFIC_MEDICAL_SPEECH_API_KEY: 'dedicated' });
  assert.deepEqual(Object.keys(modes), ['english', 'medical', 'medical-speakers']);
  for (const field of ['id', 'url', 'credential', 'dedicated']) assert.equal(modes.medical[field], modes['medical-speakers'][field]);
  assert.equal(modes['medical-speakers'].diarization.id, 'diar-streaming-sortformer-4spk-v2-1');
  assert.equal(modes.medical.diarization, undefined);
});
async function scenario(mode) {
  const backend = new WebSocket.WebSocketServer({ port: 0 }); await once(backend, 'listening');
  const seen = { asr: [], diar: [] }, auth = {}, starts = {}, audio = { asr: [], diar: [] }, receipts = [], events = [];
  const sockets = {};
  backend.on('connection', (ws, req) => {
    const name = req.url === '/asr' ? 'asr' : 'diar'; sockets[name] = ws; auth[name] = req.headers.authorization;
    ws.on('message', (raw, binary) => {
      if (binary) {
        audio[name].push(Buffer.from(raw));
        ws.send(JSON.stringify(name === 'asr' ? { type: 'transcript.final', segment_id: 0, text: 'No fever.', items: [{ text: 'No', start_seconds: 0, end_seconds: .08 }, { text: 'fever.', start_seconds: .08, end_seconds: .16 }] }
          : { type: 'speaker.activity', start_seconds: 0, frame_duration_seconds: .08, probabilities: [[.9, 0, 0, 0], [.9, 0, 0, 0]] }));
        return;
      }
      const event = JSON.parse(raw); seen[name].push(event.type);
      if (event.type === 'session.start') {
        starts[name] = event;
        if (name === 'diar') ws.send(JSON.stringify({ type: 'operation.queued', operation_id: operation }));
        setTimeout(() => ws.send(JSON.stringify({ type: 'session.ready', ...(name === 'asr' ? { session_id: 'asr-native', model_revision: 'checkpoint-sha' } : { session_id: operation }) })), name === 'diar' ? 20 : 0);
      }
      if (name === 'asr' && event.type === 'input.finish') ws.send('{"type":"session.completed"}');
      if (name === 'diar' && event.type === 'session.finish') setTimeout(() => {
        if (mode === 'failure') ws.send('{"type":"error","code":"worker_lost","secret":"must-not-leak"}');
        else if (mode === 'cancel-after-asr') return;
        else ws.send(JSON.stringify({ type: 'session.done', operation_id: operation }));
      }, 10);
    });
  });
  const server = http.createServer();
  const relay = attach(server, LocalWebSocket, { saveStreamReceipt: async (owner, receipt) => { receipts.push({ owner, ...receipt }); return 'f513d0f9-ea73-4f04-9951-28be9a86b6b1'; } });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try {
    const origin = 'https://client.test';
    const { ticket, path } = issueTicket('paired-' + mode, origin, { id: 'same-medical', url: `https://127.0.0.1:${backend.address().port}/asr`,
      diarization: { id: 'diar-streaming-sortformer-4spk-v2-1', url: `https://127.0.0.1:${backend.address().port}/diar`, credential: 'ordinary-key' } }, 'medical-key');
    const client = new WebSocket(`ws://127.0.0.1:${server.address().port}${path}`, { origin });
    const closed = once(client, 'close');
    client.on('message', raw => {
      const e = JSON.parse(raw); events.push(e);
      if (e.type === 'session.ready') {
        assert.equal(starts.asr.options.model, 'same-medical'); assert.equal(starts.diar.model, 'diar-streaming-sortformer-4spk-v2-1');
        client.send(Buffer.alloc(5120, 7));
      }
      if (e.type === 'speaker.activity') client.send(JSON.stringify({ type: mode === 'cancel' ? 'session.cancel' : 'input.finish' }));
      if (e.type === 'asr.completed' && mode === 'cancel-after-asr') client.send('{"type":"session.cancel"}');
    });
    await once(client, 'open'); client.send(JSON.stringify({ type: 'relay.attach', ticket })); await closed;
    // Allow peer cancel controls to be consumed before closing test sockets.
    await new Promise(resolve => setTimeout(resolve, 25));
    assert.equal(auth.asr, 'Bearer medical-key'); assert.equal(auth.diar, 'Bearer ordinary-key');
    assert.deepEqual(Buffer.concat(audio.asr), Buffer.concat(audio.diar));
    assert.equal(Buffer.concat(audio.asr).length, 5120);
    assert.ok(!JSON.stringify(events).includes('must-not-leak'));
    assert.ok(!JSON.stringify(events).includes('ordinary-key'));
    if (mode === 'success') {
      assert.equal(receipts.length, 1); assert.equal(receipts[0].operation_id, operation);
      assert.equal(receipts[0].pcm_sha256, crypto.createHash('sha256').update(Buffer.alloc(5120, 7)).digest('hex'));
      assert.equal(events.filter(e => e.type === 'session.completed').length, 1);
      assert.ok(events.findIndex(e => e.type === 'diarization.completed') < events.findIndex(e => e.type === 'session.completed'));
      assert.equal(seen.diar.filter(type => type === 'session.start').length, 1);
      assert.equal(receipts[0].asr_model, 'same-medical');
    } else {
      assert.equal(receipts.length, 0); assert.ok(!events.some(e => e.type === 'session.completed'));
      assert.ok(events.some(e => e.type === (mode === 'failure' ? 'session.error' : 'session.cancelled')));
      assert.ok(seen.diar.includes('session.cancel'));
    }
  } finally {
    for (const client of relay.clients) client.terminate(); for (const client of backend.clients) client.terminate();
    relay.close(); backend.close(); await new Promise(resolve => server.close(resolve));
  }
}
for (const mode of ['success', 'cancel', 'failure', 'cancel-after-asr']) test(`paired live stream ${mode}: bounded same audio, one operation, no fallback`, { timeout: 5000 }, () => scenario(mode));
