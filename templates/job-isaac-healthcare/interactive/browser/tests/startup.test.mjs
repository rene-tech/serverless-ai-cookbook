import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';
const source = await readFile(new URL('../src/startup.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext}}).outputText;
const {waitForStartup, StartupError, StartupUnavailable} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const descriptor = {session_id: 'session-a', startup_ready: false, terminal: false, deadline_at: 20, startup_timeout_s: 10};
const code = expected => error => error instanceof StartupError && error.code === expected;

function clock() {
  let now = 0;
  return {now: () => now, sleep: async ms => { now += ms; }};
}

test('cold startup polls the same session then returns without allocating or reattaching', async () => {
  const time = clock(); let reads = 0;
  const ready = await waitForStartup(descriptor, async () => ({...descriptor, startup_ready: ++reads === 4}),
    new AbortController().signal, time.now, time.sleep);
  assert.equal(reads, 4); assert.equal(ready.session_id, descriptor.session_id);
  assert.equal(ready.deadline_at, descriptor.deadline_at); assert.equal(time.now(), 4000);
});
test('already-ready runtime has no polling delay', async () => {
  let reads = 0;
  const ready = await waitForStartup({...descriptor, startup_ready: true}, async () => { reads++; }, new AbortController().signal, () => 0);
  assert.equal(reads, 0); assert.equal(ready.startup_ready, true);
});
for (const [field, value, expected] of [['session_id', 'other', 'identity_changed'], ['deadline_at', 21, 'identity_changed'],
  ['startup_ready', 'true', 'invalid_descriptor'], ['terminal', true, 'terminal']]) {
  test(`polling rejects ${field}=${value}`, async () => {
    const time = clock();
    await assert.rejects(waitForStartup(descriptor, async () => ({...descriptor, [field]: value}),
      new AbortController().signal, time.now, time.sleep), code(expected));
  });
}
test('terminal and expired initial descriptors never call the reader', async () => {
  const read = async () => { throw new Error('unexpected read'); };
  await assert.rejects(waitForStartup({...descriptor, terminal: true}, read, new AbortController().signal, () => 0), code('terminal'));
  await assert.rejects(waitForStartup(descriptor, read, new AbortController().signal, () => 20000), code('expired'));
});
test('startup timeout is bounded by the supplied runtime budget', async () => {
  const time = clock(); let reads = 0;
  await assert.rejects(waitForStartup({...descriptor, startup_timeout_s: 2}, async () => { reads++; return descriptor; },
    new AbortController().signal, time.now, time.sleep), code('startup_timeout'));
  assert.equal(time.now(), 2000); assert.equal(reads, 2);
});
test('original session deadline wins over a longer startup budget', async () => {
  const time = clock(); const initial = {...descriptor, deadline_at: 1};
  await assert.rejects(waitForStartup(initial, async () => initial, new AbortController().signal, time.now, time.sleep), code('expired'));
  assert.equal(time.now(), 1000);
});
test('explicit disconnect aborts pending polling without another read', async () => {
  const abort = new AbortController(); let reads = 0;
  await assert.rejects(waitForStartup(descriptor, async () => { reads++; return descriptor; }, abort.signal, () => 0,
    async () => abort.abort()), error => error.name === 'AbortError');
  assert.equal(reads, 0);
});
test('explicit disconnect aborts an in-flight descriptor request', async () => {
  const abort = new AbortController(); const time = clock();
  const waiting = waitForStartup(descriptor, signal => new Promise((_, reject) => {
    signal.addEventListener('abort', () => reject(signal.reason), {once: true});
    abort.abort();
  }), abort.signal, time.now, time.sleep);
  await assert.rejects(waiting, error => error.name === 'AbortError');
});
test('a stuck descriptor request cannot outlive the original deadline', async () => {
  const now = Date.now(); const initial = {...descriptor, deadline_at: (now + 30) / 1000};
  await assert.rejects(waitForStartup(initial, signal => new Promise((_, reject) => {
    signal.addEventListener('abort', () => reject(signal.reason), {once: true});
  }), new AbortController().signal, Date.now, async () => {}), code('expired'));
});

test('temporary descriptor transport failure retries only within the same startup budget', async () => {
  const time = clock(); let reads = 0;
  const ready = await waitForStartup(descriptor, async () => {
    if (++reads === 1) throw new StartupUnavailable();
    return {...descriptor, startup_ready: true};
  }, new AbortController().signal, time.now, time.sleep);
  assert.equal(reads, 2); assert.equal(ready.session_id, descriptor.session_id);
});
test('authorization and other descriptor errors never retry', async () => {
  const time = clock(); let reads = 0;
  await assert.rejects(waitForStartup(descriptor, async () => { reads++; throw new Error('authorization refused'); },
    new AbortController().signal, time.now, time.sleep), /authorization refused/);
  assert.equal(reads, 1);
});
