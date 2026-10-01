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
for (const matching of [true, false]) test(`shared App post-stop relay attests checkpoint before PCM (${matching ? 'matching' : 'wrong checkpoint'})`, { timeout: 5000 }, async () => {
  const origin = 'https://client.test', checkpoint = '2a2b1cae8e96d62e83a82351f7d483df01fc28d1d64793ce45a5de514a6c3b5f';
  const backend = new WebSocket.WebSocketServer({ port: 0 }); await once(backend, 'listening');
  let connections = 0, audioBytes = 0, authorization, wireModel;
  backend.on('connection', (ws, req) => {
    connections++; authorization = req.headers.authorization;
    ws.on('message', (data, binary) => {
      if (binary) { audioBytes += data.length; return; }
      const event = JSON.parse(data);
      if (event.type === 'session.start') {
        wireModel = event.options.model;
        ws.send(JSON.stringify({ type: 'session.ready', runtime_identity: { checkpoint_sha256: matching ? checkpoint : 'a'.repeat(64), checkpoint_kind: 'fine_tuned' } }));
      }
      if (event.type === 'input.finish') ws.send('{"type":"session.completed"}');
    });
  });
  const server = http.createServer(), relay = attach(server, LocalWebSocket);
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try {
    const { ticket, path } = issueTicket('attest-' + matching, origin, { id: 'nemotron-speech-en-medical-0-6b',
      url: `https://127.0.0.1:${backend.address().port}/v1/audio/stream`, attestRuntime: true, expectedCheckpoint: checkpoint,
      diarization: { id: 'diar-streaming-sortformer-4spk-v2-1', timing: 'post-stop', url: 'https://must-not-connect.invalid/v1/voice/stream' } }, 'ordinary-fixture-key');
    const client = new WebSocket(`ws://127.0.0.1:${server.address().port}${path}`, { origin }), received = [];
    const closed = once(client, 'close');
    client.on('message', raw => { const event = JSON.parse(raw); received.push(event);
      if (event.type === 'session.ready') { client.send(Buffer.alloc(3200)); client.send('{"type":"input.finish"}'); }
    });
    await once(client, 'open'); client.send(JSON.stringify({ type: 'relay.attach', ticket })); await closed;
    assert.equal(connections, 1); assert.equal(authorization, 'Bearer ordinary-fixture-key');
    assert.equal(wireModel, 'nemotron-speech-en-medical-0-6b');
    assert.equal(audioBytes, matching ? 3200 : 0);
    assert.deepEqual(received.map(row => row.type), matching ? ['session.ready', 'session.completed'] : ['session.error']);
    if (matching) assert.equal(received[0].model_identity.checkpoint_sha256, checkpoint);
    else assert.equal(received[0].code, 'speech_checkpoint_mismatch');
  } finally {
    for (const client of relay.clients) client.terminate(); for (const client of backend.clients) client.terminate();
    relay.close(); backend.close(); await new Promise(resolve => server.close(resolve));
  }
});
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
test('cancel control reaches upstream before the closing frame', async () => {
  const origin='https://client.test';
  const backend=new WebSocket.WebSocketServer({port:0});await once(backend,'listening');
  const controls=[]; let upstreamModel;
  let observed;
  const cancelled=new Promise(resolve=>{observed=resolve;});
  backend.on('connection',ws=>{
    ws.on('message',raw=>{const event=JSON.parse(raw);controls.push(event.type);
      if(event.type==='session.start'){upstreamModel=event.options.model;ws.send('{"type":"session.ready"}');}
      if(event.type==='session.cancel')observed();
    });
  });
  const server=http.createServer(),relay=attach(server,LocalWebSocket);server.listen(0,'127.0.0.1');await once(server,'listening');
  try{
    const {ticket,path}=issueTicket('cancel-test',origin,{id:'nemotron-speech-en-0-6b',wireModel:'nemotron-speech-en-0.6b',url:`https://127.0.0.1:${backend.address().port}/v1/audio/stream`},'private-mock');
    const client=new WebSocket(`ws://127.0.0.1:${server.address().port}${path}`,{origin});
    const closed=once(client,'close');
    client.on('message',raw=>{if(JSON.parse(raw).type==='session.ready')client.send('{"type":"session.cancel"}');});
    await once(client,'open');client.send(JSON.stringify({type:'relay.attach',ticket}));
    await closed;await cancelled;
    assert.deepEqual(controls,['session.start','session.cancel']);
    assert.equal(upstreamModel,'nemotron-speech-en-0.6b');
  }finally{
    for(const client of relay.clients)client.terminate();for(const client of backend.clients)client.terminate();
    relay.close();backend.close();await new Promise(resolve=>server.close(resolve));
  }
});
