const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const WebSocket = require('/app/node_modules/ws');
const { attach, issueTicket } = require('./relay.cjs');
// Loopback mock only: production attach() always instantiates TLS WebSockets.
class LocalWebSocket extends WebSocket {
  constructor(url, options) { super(url.replace('wss://', 'ws://'), options); }
}
test('authenticated relay forwards PCM and revised/final events, preserves upstream bearer only server-side', async () => {
  const origin = 'https://client.test';
  const backend = new WebSocket.WebSocketServer({ port: 0 }); await once(backend, 'listening');
  let authorization, start, audioBytes = 0;
  backend.on('connection', (ws, req) => {
    authorization = req.headers.authorization;
    ws.on('message', (data, binary) => {
      if (binary) { audioBytes += data.length; ws.send(JSON.stringify({ type: 'transcript.partial', segment_id: 0, revision: 1, text: 'metformin' })); return; }
      const event = JSON.parse(data);
      if (event.type === 'session.start') { start = event; ws.send('{"type":"session.ready"}'); }
      if (event.type === 'input.finish') {
        ws.send(JSON.stringify({ type: 'transcript.final', segment_id: 0, revision: 2, text: 'metformin 500 mg' }));
        ws.send('{"type":"session.completed","operation_id":"test-operation"}');
      }
    });
  });
  const server = http.createServer(); const relay = attach(server, LocalWebSocket);
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try {
    const { ticket, path } = issueTicket('integration', origin, { id: 'nemotron-clinical-en', url: `https://127.0.0.1:${backend.address().port}/v1/audio/stream` }, 'secret-mock-only');
    const client = new WebSocket(`ws://127.0.0.1:${server.address().port}${path}`, { origin });
    const received = [];
    const done = new Promise((resolve, reject) => {
      client.on('error', reject);
      client.on('message', (data) => {
        const event = JSON.parse(data); received.push(event);
        if (event.type === 'session.ready') { client.send(Buffer.alloc(6400)); client.send('{"type":"input.finish"}'); }
        if (event.type === 'session.error') reject(new Error(event.code));
      });
      client.on('close', resolve);
    });
    await once(client, 'open'); client.send(JSON.stringify({ type: 'relay.attach', ticket }));
    await done;
    assert.equal(authorization, 'Bearer secret-mock-only'); assert.equal(audioBytes, 6400);
    assert.deepEqual(start.audio, { encoding: 'pcm_s16le', sample_rate_hz: 16000, channels: 1 });
    assert.equal(start.options.model, 'nemotron-clinical-en');
    assert.deepEqual(received.map((value) => value.type), ['session.ready', 'transcript.partial', 'transcript.final', 'session.completed']);
    assert.ok(!JSON.stringify(received).includes('secret-mock-only'));
  } finally {
    for (const client of relay.clients) client.terminate();
    for (const client of backend.clients) client.terminate();
    relay.close(); backend.close(); await new Promise((resolve) => server.close(resolve));
  }
});
