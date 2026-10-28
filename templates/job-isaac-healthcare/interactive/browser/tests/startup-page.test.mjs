import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
const compile = source => ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext}}).outputText;
const startup = await import('data:text/javascript;base64,' + Buffer.from(compile(await readFile(new URL('../src/startup.ts', import.meta.url), 'utf8'))).toString('base64'));
const main = compile((await readFile(new URL('../src/main.ts', import.meta.url), 'utf8'))
  .replace(/import \{ AppStreamer, EventStatus, StreamType \} from '[^']+';/, 'const {AppStreamer, EventStatus, StreamType} = globalThis.sdk;')
  .replace(/import \{ StartupError, StartupUnavailable, waitForStartup, type StartupDescriptor \} from '[^']+';/, 'const {StartupError, StartupUnavailable, waitForStartup} = globalThis.startup;')).replace(/export \{\};?\s*$/, '');
const tick = () => new Promise(resolve => setImmediate(resolve));

async function page() {
  const requests = [], connections = [], buttons = {}, events = {};
  const status = {textContent: ''}, video = {videoWidth: 0, readyState: 0, requestVideoFrameCallback() {}};
  const descriptor = {session_id: 'session-a', signaling_path: '/v1/isaac/sessions/session-a/signaling',
    ice_servers: [{urls: ['turns:turn.test:443?transport=tcp'], username: 'test', credential: 'test'}],
    startup_ready: false, terminal: false, deadline_at: 100, startup_timeout_s: 30};
  let ready, now = 0;
  const context = vm.createContext({URL, AbortController, console,
    location: {origin: 'https://viewer.test', pathname: '/v1/isaac/sessions/session-a/viewer/', hostname: 'viewer.test', port: '', protocol: 'https:'},
    window: {parent: null, opener: null, addEventListener: (name, callback) => { events[name] = callback; }},
    document: {querySelector: name => ({'#status': status, '#remote-video': video,
      '#attach-form': {hidden: true, addEventListener() {}}, '#disconnect': {addEventListener: (_, cb) => { buttons.disconnect = cb; }}}[name])},
    sdk: {AppStreamer: class { async connect(value) { connections.push(value); } async terminate() {} }, EventStatus: {}, StreamType: {DIRECT: 'direct'}},
    startup: {...startup, waitForStartup: (initial, read, signal) => startup.waitForStartup(initial, read, signal, () => now, async ms => { now += ms; })},
    fetch: async (path, options) => {
      requests.push({path, options});
      if (requests.length === 1) return {ok: true, json: async () => descriptor};
      return new Promise((resolve, reject) => {
        ready = () => resolve({ok: true, json: async () => ({...descriptor, startup_ready: true})});
        options.signal.addEventListener('abort', () => reject(options.signal.reason), {once: true});
      });
    },
  });
  vm.runInContext(main, context);
  await tick();
  assert.equal(requests.length, 2);
  return {requests, connections, buttons, status, ready};
}

test('actual page waits for startup, then opens SDK once with same session and no admission calls', async () => {
  const p = await page();
  assert.equal(p.connections.length, 0);
  p.ready(); await tick();
  assert.equal(p.connections.length, 1);
  assert.equal(p.connections[0].streamConfig.sessionId, 'session-a');
  assert.equal(p.connections[0].streamConfig.newSession, false);
  assert.equal(p.connections[0].streamConfig.maxReconnects, 0);
  assert.ok(p.requests.every(r => r.path === '/v1/isaac/sessions/session-a/descriptor' && !r.options.method && r.options.credentials === 'same-origin'));
});

test('actual disconnect stops a pending descriptor and cannot connect after readiness arrives', async () => {
  const p = await page();
  await p.buttons.disconnect(); p.ready(); await tick();
  assert.equal(p.connections.length, 0);
  assert.match(p.status.textContent, /^Disconnected/);
  assert.equal(p.requests.length, 2);
});
