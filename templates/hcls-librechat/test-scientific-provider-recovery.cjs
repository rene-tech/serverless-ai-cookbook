const test = require('node:test');
const assert = require('node:assert/strict');
const { isEmptyStoppedResponse, invokeWithRecovery } = require('./scientific-provider-recovery.cjs');
const response = (fields = {}) => ({ messages: [{ getType: () => 'ai', content: '',
  response_metadata: { finish_reason: 'stop' }, ...fields }] });

test('recognizes only empty or reasoning-only normal stops', () => {
  assert.equal(isEmptyStoppedResponse(response()), true);
  assert.equal(isEmptyStoppedResponse(response({ content: [{ type: 'reasoning', text: 'internal' }] })), true);
  for (const fields of [
    { content: 'An answer' }, { content: [{ type: 'text', text: 'An answer' }] },
    { content: [{ type: 'image_url', image_url: { url: 'fixture' } }] },
    { tool_calls: [{ id: 'tool', name: 'execute' }] },
    { invalid_tool_calls: [{ id: 'partial' }] },
    { additional_kwargs: { tool_calls: [{ id: 'tool' }] } },
    { additional_kwargs: { refusal: 'Unable to comply' } },
    { response_metadata: { finish_reason: 'length' } },
    { response_metadata: { finish_reason: 'content_filter' } },
    { response_metadata: { finish_reason: 'stop', preempted: true } },
    { response_metadata: {} }, { getType: () => 'tool' },
  ]) assert.equal(isEmptyStoppedResponse(response(fields)), false);
  assert.equal(isEmptyStoppedResponse({ messages: [] }), false);
});

test('retries the invocation once and retains failed-attempt evidence', async () => {
  let calls = 0; const observed = [];
  const good = response({ content: 'Measured result' });
  const result = await invokeWithRecovery({ invoke: async () => ++calls === 1 ? response() : good,
    canRetry: () => true, observeEmpty: (message) => observed.push(message) });
  assert.equal(result, good);
  assert.equal(calls, 2); assert.equal(observed.length, 1);
  assert.equal(result.messages[0].response_metadata.scientific_empty_response_retries, 1);
});

test('a second empty response stays incomplete, never loops indefinitely', async () => {
  let calls = 0;
  const result = await invokeWithRecovery({ invoke: async () => { calls++; return response(); },
    canRetry: () => true, observeEmpty: () => {} });
  assert.equal(calls, 2); assert.equal(isEmptyStoppedResponse(result), true);
});

test('cancellation, emitted content and pending tools prevent recovery', async () => {
  for (const configuration of [{ signal: { aborted: true }, canRetry: () => true },
    { canRetry: () => false }]) {
    let calls = 0;
    await invokeWithRecovery({ invoke: async () => { calls++; return response(); },
      observeEmpty: () => assert.fail('must not retry'), ...configuration });
    assert.equal(calls, 1);
  }
});

test('provider errors propagate to the existing error/fallback implementation', async () => {
  let calls = 0; const error = new Error('provider unavailable');
  await assert.rejects(invokeWithRecovery({ invoke: async () => { calls++; throw error; },
    canRetry: () => true, observeEmpty: () => {} }), (caught) => caught === error);
  assert.equal(calls, 1);
});

test('the pinned patch is exact and refuses duplicate installation', async () => {
  const { patchProviderRecovery } = await import('./patch-agent-reliability.mjs');
  const fixture = '\n\t\t\t\tresult = await require_langfuseRuntimeScope.withLangfuseRuntimeScope(\n' +
    '\t\t\t\t}, invokeConfig));\n\t\t\t} catch (primaryError) {\n' +
    '\t\t\t\t\tresult = await require_langfuseRuntimeScope.withLangfuseRuntimeScope(fallback);';
  const patched = patchProviderRecovery(fixture);
  assert.match(patched, /invokeWithRecovery/);
  assert.match(patched, /signal: invokeConfig.signal/);
  assert.match(patched, /withLangfuseRuntimeScope\(fallback\)/);
  assert.throws(() => patchProviderRecovery(patched));
  assert.throws(() => patchProviderRecovery('unrecognized source'));
});
