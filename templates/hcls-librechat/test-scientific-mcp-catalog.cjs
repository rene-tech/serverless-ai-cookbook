'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createReader, patchDefinitions, patchInstances } = require('./scientific-mcp-catalog.cjs');

const tool = (required) => ({
  submit: { function: { name: 'submit', parameters: { type: 'object', required } } },
});
function fixture(snapshot = { tools: tool(['target']) }) {
  const observed = { reads: [], warnings: [], cached: tool(['target_id']) };
  const read = createReader({
    getSnapshot: async (...args) => {
      observed.reads.push(args);
      if (snapshot instanceof Error) throw snapshot;
      return typeof snapshot === 'function' ? snapshot(...args) : snapshot;
    },
    configGeneration: (config) => config.revision,
    isEphemeral: (config) => config.requestScoped === true,
    warn: (message) => observed.warnings.push(message),
  });
  const context = {
    req: {}, userId: 'owner-a', serverName: 'science', serverConfig: { revision: 1 },
    getCached: async () => observed.cached,
  };
  return { read, context, observed };
}

test('same-name schema changes reach this request, sharing one read across consumers', async () => {
  const { read, context, observed } = fixture();
  const [definitions, instances] = await Promise.all([read(context), read({ ...context })]);
  assert.deepEqual(definitions.submit.function.parameters.required, ['target']);
  assert.strictEqual(definitions, instances);
  assert.equal(observed.reads.length, 1);
  assert.deepEqual(observed.cached.submit.function.parameters.required, ['target_id']);
  await read({ ...context, req: {} });
  assert.equal(observed.reads.length, 2);
});

test('complete snapshots replace removed tools and include additions; empty means empty', async () => {
  const { read, context, observed } = fixture({ tools: { added: tool(['sequence']).submit } });
  assert.deepEqual(Object.keys(await read(context)), ['added']);
  const empty = fixture({ tools: {} });
  assert.deepEqual(await empty.read(empty.context), {});
  assert.equal(observed.warnings.length, 0);
});

test('users, servers and config generations never share a request snapshot', async () => {
  const { read, context, observed } = fixture((user, server, config) => ({ tools: { user, server, revision: config.revision } }));
  const variants = [context, { ...context, userId: 'owner-b' },
    { ...context, serverName: 'other' }, { ...context, serverConfig: { revision: 2 } }];
  const outputs = await Promise.all(variants.map(read));
  assert.equal(observed.reads.length, 4);
  assert.equal(outputs[1].user, 'owner-b');
  assert.equal(outputs[2].server, 'other');
  assert.equal(outputs[3].revision, 2);
});

for (const error of [new Error('incomplete snapshot'), new Error('timeout'), null]) {
  test(`failed refresh (${error?.message ?? 'missing connection'}) preserves cache and retries next request`, async () => {
    const { read, context, observed } = fixture(error instanceof Error ? error : { tools: null });
    assert.strictEqual(await read(context), observed.cached);
    assert.strictEqual(await read(context), observed.cached);
    assert.equal(observed.reads.length, 1);
    assert.equal(observed.warnings.length, 1);
    assert.doesNotMatch(observed.warnings[0], /owner-a|target_id|science/);
    await read({ ...context, req: {} });
    assert.equal(observed.reads.length, 2);
    assert.equal(observed.warnings.length, 2);
  });
}

test('request-scoped credentials and absent connections keep their normal loader', async () => {
  const { read, context, observed } = fixture({ tools: null });
  observed.cached = null;
  assert.equal(await read({ ...context, serverConfig: { revision: 1, requestScoped: true } }), null);
  assert.equal(observed.reads.length, 0);
  assert.equal(await read(context), null);
  assert.equal(observed.reads.length, 1);
  assert.equal(observed.warnings.length, 0);
});

test('both pinned consumers use the same reader before creating definitions/instances', () => {
  const definitions = 'const cached = await getMCPServerTools(userId, serverName, serverConfig);';
  const instances = 'availableTools = await getMCPServerTools(safeUser.id, serverName, config.config);';
  assert.match(patchDefinitions(definitions), /req, userId, serverName, serverConfig/);
  assert.match(patchInstances(instances), /req: options.req, userId: safeUser.id/);
  for (const [patch, input] of [[patchDefinitions, definitions], [patchInstances, instances]]) {
    assert.throws(() => patch('unknown source'), /Unsupported pinned/);
    assert.throws(() => patch(input + input), /Unsupported pinned/);
    assert.throws(() => patch(patch(input)), /Unsupported pinned/);
    assert.doesNotMatch(patch(input), /reconnect|forceNew|tools\/call/);
  }
});
