'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { createRoutingFetch, settings } = require('./scientific-provider-routing.cjs');
const config = { primary: 'https://primary.example/v1', model: 'dedicated/model', catalog: 'https://public.example/v1', firstTokenMs: 100,
  fallback: { base: 'https://public.example/v1', model: 'public/model' } };
const request = (overrides = {}) => ({ method: 'POST', headers: { authorization: 'Bearer test' },
  body: JSON.stringify({ model: config.model, messages: [{ role: 'tool', tool_call_id: 'accepted-tool', content: 'existing operation' }], stream: true }), ...overrides });
const json = (status = 200) => new Response('{}', { status, headers: { 'content-type': 'application/json' } });

test('defaults are disabled; incomplete routing config fails closed', () => {
  assert.equal(settings({}), null);
  assert.throws(() => settings({ SCIENTIFIC_CHAT_FALLBACK_MODEL: 'x' }));
  assert.throws(() => settings({ SCIENTIFIC_CHAT_BASE_URL: config.primary }));
});
test('primary success retains request and emits operator selection', async () => {
  const calls = [], events = [];
  const fetch = createRoutingFetch(async (...args) => { calls.push(args); return json(); }, config, (e) => events.push(e));
  const init = request(); await fetch(config.primary + '/chat/completions', init);
  assert.equal(calls.length, 1); assert.equal(calls[0][1].body, init.body);
  assert.equal(events[0].provider, 'primary'); assert.equal(events[0].status, 200);
  assert.ok(!JSON.stringify(events).includes('accepted-tool'));
});
test('availability errors fall back once, preserving tool history and auth; SDK retries disabled', async () => {
  for (const status of [408, 429, 500, 502, 503, 504]) {
    const calls = [];
    const fetch = createRoutingFetch(async (url, init) => { calls.push([url, init]); return json(calls.length === 1 ? status : 503); }, config);
    const response = await fetch(config.primary + '/chat/completions', request());
    assert.equal(calls.length, 2); assert.equal(response.headers.get('x-should-retry'), 'false');
    assert.equal(calls[1][0], config.fallback.base + '/chat/completions');
    const actual = JSON.parse(calls[1][1].body), expected = JSON.parse(request().body);
    expected.model = config.fallback.model; assert.deepEqual(actual, expected);
    assert.equal(calls[1][1].headers.authorization, 'Bearer test');
  }
});
test('authentication, invalid input and model-not-found errors never fall back', async () => {
  for (const status of [400, 401, 403, 404, 422]) {
    let calls = 0;
    await createRoutingFetch(async () => { calls++; return json(status); }, config)(config.primary + '/chat/completions', request());
    assert.equal(calls, 1);
  }
});
test('network failure falls back once; both failures become bounded non-retryable error', async () => {
  let calls = 0;
  const result = await createRoutingFetch(async () => { calls++; throw new TypeError('network'); }, config)(config.primary + '/chat/completions', request());
  assert.equal(calls, 2); assert.equal(result.status, 503); assert.equal(result.headers.get('x-should-retry'), 'false');
});
test('cancelled calls do not fall back', async () => {
  const controller = new AbortController(); let calls = 0;
  const fetch = createRoutingFetch(async () => { calls++; controller.abort(); throw controller.signal.reason; }, config);
  await assert.rejects(fetch(config.primary + '/chat/completions', request({ signal: controller.signal })), { name: 'AbortError' });
  assert.equal(calls, 1);
});
test('other models use public catalog origin; unrelated URLs pass through', async () => {
  const calls = [];
  const fetch = createRoutingFetch(async (url) => { calls.push(url); return json(); }, config);
  await fetch(config.primary + '/chat/completions', request({ body: JSON.stringify({ model: 'other' }) }));
  await fetch('https://science.example/mcp', request());
  assert.deepEqual(calls, [config.catalog + '/chat/completions', 'https://science.example/mcp']);
});
test('real HTTP SSE preamble stall falls back, while partial tool/text/reasoning streams never replay', async () => {
  const sockets = new Set(), calls = [];
  let mode = 'stall';
  const server = createServer((req, res) => {
    calls.push(req.url);
    req.resume();
    if (req.url.startsWith('/fallback')) { res.writeHead(200, { 'content-type': 'application/json' }); res.end('{}'); return; }
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const delta = mode === 'stall' ? { role: 'assistant' } : mode === 'tool' ? { tool_calls: [{ index: 0, id: 't', function: { name: 'scientific', arguments: '{' } }] } : { [mode]: 'started' };
    res.write('data: ' + JSON.stringify({ choices: [{ delta }] }) + '\n\n');
    if (mode !== 'stall') setTimeout(() => res.destroy(), 15);
  });
  server.on('connection', (socket) => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)); });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const local = { ...config, primary: origin + '/primary', firstTokenMs: 50, fallback: { base: origin + '/fallback', model: 'public/model' } };
  const fetch = createRoutingFetch(globalThis.fetch, local);
  try {
    assert.equal((await fetch(local.primary + '/chat/completions', request())).status, 200);
    assert.equal(calls.length, 2);
    for (mode of ['tool', 'content', 'reasoning_content']) {
      const before = calls.length;
      const response = await fetch(local.primary + '/chat/completions', request());
      await assert.rejects(response.text()); assert.equal(calls.length, before + 1);
    }
  } finally { for (const socket of sockets) socket.destroy(); await new Promise((resolve) => server.close(resolve)); }
});
