'use strict';
// Run in the pinned workbench to qualify the actual installed SDK transport.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { createRoutingFetch } = require('./scientific-provider-routing.cjs');
test('installed OpenAI SDK uses routing, streams tools, and does not retry both-provider failures', async () => {
  const OpenAI = require('/app/node_modules/openai');
  let mode = 'primary', calls = [];
  const sockets = new Set();
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw); calls.push({ path: req.url, body });
    const failed = mode === 'both-fail' || (mode === 'fallback' && req.url.startsWith('/primary'));
    if (failed) { res.writeHead(503, { 'content-type': 'application/json' }); res.end(JSON.stringify({ error: { message: 'Unavailable' } })); return; }
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    for (const [delta, finish_reason] of [
      [{ role: 'assistant' }, null],
      [{ tool_calls: [{ index: 0, id: 'tool-one', type: 'function', function: { name: 'observe', arguments: '{"id":"accepted-operation"}' } }] }, null],
      [{}, 'tool_calls'],
    ]) res.write('data: ' + JSON.stringify({ id: 'chat-one', object: 'chat.completion.chunk', model: body.model, choices: [{ index: 0, delta, finish_reason }] }) + '\n\n');
    res.end('data: [DONE]\n\n');
  });
  server.on('connection', (socket) => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)); });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const config = { primary: origin + '/primary', catalog: origin + '/public', model: 'primary-model', firstTokenMs: 1000, fallback: { base: origin + '/fallback', model: 'fallback-model' } };
  const client = new OpenAI({ apiKey: 'test', baseURL: config.primary, fetch: createRoutingFetch(globalThis.fetch, config) });
  try {
    for (mode of ['primary', 'fallback']) {
      calls = [];
      const result = await client.chat.completions.create({ model: config.model, messages: [{ role: 'user', content: 'Observe existing work' }], stream: true });
      const chunks = []; for await (const chunk of result) chunks.push(chunk);
      assert.equal(chunks[1].choices[0].delta.tool_calls[0].function.name, 'observe');
      assert.equal(calls.length, mode === 'primary' ? 1 : 2);
      assert.equal(calls.at(-1).body.model, mode === 'primary' ? config.model : config.fallback.model);
    }
    mode = 'both-fail'; calls = [];
    await assert.rejects(client.chat.completions.create({ model: config.model, messages: [], stream: true }), (error) => error.status === 503);
    assert.equal(calls.length, 2);
  } finally { for (const socket of sockets) socket.destroy(); await new Promise((resolve) => server.close(resolve)); }
});
