// CPU-only: run against the exact installed SDK. No provider, MCP or model call.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { patchDiscoveries } = require('./scientific-tool-search-patch.cjs');
const graphPath = process.env.SCIENTIFIC_DISCOVERY_GRAPH || '/app/node_modules/@librechat/agents/dist/cjs/graphs/Graph.cjs';
const installed = process.env.SCIENTIFIC_DISCOVERY_INSTALLED === '1';
if (!installed && !process.env.SCIENTIFIC_DISCOVERY_GRAPH && !fs.existsSync(graphPath)) {
  test('installed deferred-discovery regression', { skip: 'Requires exact installed @librechat/agents; set SCIENTIFIC_DISCOVERY_GRAPH' }, () => {});
} else {
const r = Module.createRequire(graphPath);
const modulePath = path.join(path.dirname(graphPath), '../messages/tools.cjs');
const original = r('../messages/tools.cjs');
let candidate = original;
if (installed) {
  for (const sourcePath of [modulePath, modulePath.replace('/cjs/', '/esm/').replace(/\.cjs$/, '.mjs')]) {
    const source = fs.readFileSync(sourcePath, 'utf8');
    assert.equal(source.match(/scientificHostBudgetNotice\.isHostBudgetNotice\(messages\.at\(-1\)\)/g)?.length, 2,
      `Both discovery helpers must be patched in ${sourcePath}`);
  }
} else {
const compiled = new Module(modulePath, module);
compiled.filename = modulePath;
compiled.paths = Module._nodeModulePaths(path.dirname(modulePath));
compiled._compile(patchDiscoveries(fs.readFileSync(modulePath, 'utf8')), modulePath);
candidate = compiled.exports;
}
const { AIMessageChunk, HumanMessage, ToolMessage } = r('@langchain/core/messages');
const { AgentContext } = r('../agents/AgentContext.cjs');
const { createToolSearch } = r('../tools/ToolSearch.cjs');
const { convertInjectedMessages } = r('../messages/injected.cjs');
const { isHostBudgetNotice } = require('/opt/hcls-librechat/scientific-study-admission.cjs');
const api = fs.readFileSync(process.env.SCIENTIFIC_DISCOVERY_API || '/app/packages/api/dist/index.cjs', 'utf8');
const region = api.match(/\/\/#region src\/agents\/stepBudget\.ts\n([\s\S]*?)\/\/#endregion/);
assert.ok(region, 'Exact host budget-hook source is required');
const { createStepBudgetHook } = new Function('_librechat_data_schemas',
  region[1] + '; return { createStepBudgetHook };')({ logger: { debug() {} } });
const toolName = 'infer_admet_ai_native_mcp_scientific-ai-apps';
const definition = { name: toolName, description: 'CPU fixture; never executed', defer_loading: true,
  parameters: { type: 'object', properties: { smiles: { type: 'string' } }, required: ['smiles'] } };

async function fixture(sdk = { AIMessageChunk, createToolSearch, convertInjectedMessages }) {
  const call = { type: 'tool_call', id: 'fixture-search', name: 'tool_search',
    args: { query: 'infer_admet_ai_native', max_results: 1 } };
  const registry = new Map([[toolName, definition]]);
  const result = await sdk.createToolSearch({ mode: 'local', toolRegistry: registry }).invoke(call);
  const request = new sdk.AIMessageChunk({ content: '', tool_calls: [call] });
  const hook = await createStepBudgetHook({ recursionLimit: 5 })({ entries: [{ toolName: 'tool_search', status: 'success' }] });
  const [notice] = sdk.convertInjectedMessages(hook.injectedMessages);
  assert.ok(isHostBudgetNotice(notice));
  return { request, result, notice, registry };
}

test(installed ? 'installed SDK preserves discovery across the trusted host notice'
  : 'exact unpatched failure: trusted host notice hides the completed search', async () => {
  const { request, result, notice } = await fixture();
  assert.deepEqual(original.extractToolDiscoveries([request, result]), [toolName]);
  assert.deepEqual(original.extractToolDiscoveries([request, result, notice]), installed ? [toolName] : []);
  assert.equal(original.hasToolSearchInCurrentTurn([request, result, notice]), installed);
});

if (installed) test('installed ESM discovery matches the CJS behavior', async (t) => {
  const { pathToFileURL } = require('node:url');
  const esmRoot = path.resolve(path.dirname(graphPath), '../../esm');
  const load = (relative) => import(pathToFileURL(path.join(esmRoot, relative)));
  const esm = await load('messages/tools.mjs');
  // The pinned SDK uses instanceof: CJS and ESM have distinct LangChain
  // constructors. Use the package's actual import export, not CJS fixtures or
  // weaker duck-typing in production to make a cross-format test pass.
  const corePackage = r.resolve('@langchain/core/package.json');
  const coreImport = JSON.parse(fs.readFileSync(corePackage, 'utf8')).exports['./messages'].import.default;
  assert.equal(typeof coreImport, 'string');
  const core = await import(pathToFileURL(path.resolve(path.dirname(corePackage), coreImport)));
  const sdk = { ...core, ...await load('tools/ToolSearch.mjs'), ...await load('messages/injected.mjs') };

  await t.test('actual CJS and ESM message classes are distinct; preserve strict boundaries', async () => {
    assert.notEqual(core.ToolMessage, ToolMessage);
    const cjs = await fixture();
    assert.deepEqual(esm.extractToolDiscoveries([cjs.request, cjs.result]), []);
    const own = await fixture(sdk);
    assert.ok(own.request instanceof core.AIMessageChunk);
    assert.ok(own.result instanceof core.ToolMessage);
    assert.ok(own.notice instanceof core.HumanMessage);
    assert.deepEqual(esm.extractToolDiscoveries([own.request, own.result]), [toolName]);
    assert.equal(esm.hasToolSearchInCurrentTurn([own.request, own.result]), true);
  });

  await t.test('actual ESM ToolNode post-batch notice preserves discovery and schema activation', async () => {
    const { request, result, registry } = await fixture(sdk);
    const { ToolNode } = await load('tools/ToolNode.mjs');
    const { HookRegistry } = await load('hooks/HookRegistry.mjs');
    const { AgentContext } = await load('agents/AgentContext.mjs');
    const hooks = new HookRegistry();
    hooks.register('PostToolBatch', { internal: true, hooks: [createStepBudgetHook({ recursionLimit: 5 })] });
    const node = new ToolNode({ tools: [sdk.createToolSearch({ mode: 'local', toolRegistry: registry })],
      toolRegistry: registry, hookRegistry: hooks, toolCallStepIds: new Map() });
    const injected = [];
    await node.dispatchPostToolBatchAndInjectContext({ toolCalls: request.tool_calls,
      entriesByCallId: new Map([[request.tool_calls[0].id, {
        toolName: 'tool_search', toolUseId: request.tool_calls[0].id,
        toolInput: request.tool_calls[0].args, toolOutput: result.content, status: 'success' }]]),
      batchAdditionalContexts: [], injected, runId: 'esm-fixture' });
    assert.equal(injected.length, 1);
    assert.ok(isHostBudgetNotice(injected[0]));
    const messages = [request, result, ...injected];
    const before = JSON.stringify(messages);
    assert.deepEqual(esm.extractToolDiscoveries(messages), [toolName]);
    assert.equal(esm.hasToolSearchInCurrentTurn(messages), true);
    const context = new AgentContext({ agentId: 'esm-fixture', provider: 'openAI', clientOptions: {},
      tools: [], toolDefinitions: [definition], toolRegistry: registry });
    assert.deepEqual(context.getActiveToolDefinitions(), []);
    context.markToolsAsDiscovered(esm.extractToolDiscoveries(messages));
    const baseline = new AgentContext({ agentId: 'esm-baseline', provider: 'openAI', clientOptions: {},
      tools: [], toolDefinitions: [definition], toolRegistry: registry });
    baseline.markToolsAsDiscovered(esm.extractToolDiscoveries([request, result]));
    assert.deepEqual(context.getActiveToolDefinitions(), baseline.getActiveToolDefinitions());
    assert.equal(JSON.stringify(messages), before);
    assert.match(injected[0].content, /1 more tool-calling round/);
  });

  await t.test('ESM rejects unrelated tool-call lineage', async () => {
    const { request, result, notice } = await fixture(sdk);
    const wrong = new core.ToolMessage({ content: result.content, artifact: result.artifact,
      name: 'tool_search', tool_call_id: 'unrelated-call' });
    assert.deepEqual(esm.extractToolDiscoveries([request, wrong, notice]), []);
    assert.equal(esm.hasToolSearchInCurrentTurn([request, wrong, notice]), false);
  });

  for (const mutation of ['plain-user', 'steer', 'untrusted', 'wrong-role', 'wrong-provenance', 'source-message']) {
    await t.test(`ESM does not scan through ${mutation} messages`, async () => {
      const { request, result, notice } = await fixture(sdk);
      const metadata = structuredClone(notice.additional_kwargs);
      if (mutation === 'plain-user') for (const key of Object.keys(metadata)) delete metadata[key];
      if (mutation === 'steer') metadata.source = 'steer';
      if (mutation === 'untrusted') metadata.injected = false;
      if (mutation === 'wrong-role') metadata.role = 'user';
      if (mutation === 'wrong-provenance') metadata.provenance.parts[0].attribution = 'user';
      if (mutation === 'source-message') metadata.sourceMessageId = 'original-user';
      const other = new core.HumanMessage({ content: notice.content, additional_kwargs: metadata });
      assert.deepEqual(esm.extractToolDiscoveries([request, result, other]), []);
      assert.equal(esm.hasToolSearchInCurrentTurn([request, result, other]), false);
      assert.deepEqual(esm.extractToolDiscoveries([request, result, other, notice]), []);
      assert.equal(esm.hasToolSearchInCurrentTurn([request, result, other, notice]), false);
    });
  }
});

test('actual ToolNode post-batch path appends the trusted notice after local deferred search', async () => {
  const { ToolNode } = r('../tools/ToolNode.cjs');
  const { HookRegistry } = r('../hooks/HookRegistry.cjs');
  const { request, result, registry } = await fixture();
  const hooks = new HookRegistry();
  hooks.register('PostToolBatch', { internal: true, hooks: [createStepBudgetHook({ recursionLimit: 5 })] });
  const node = new ToolNode({ tools: [createToolSearch({ mode: 'local', toolRegistry: registry })],
    toolRegistry: registry, hookRegistry: hooks, toolCallStepIds: new Map() });
  const injected = [];
  await node.dispatchPostToolBatchAndInjectContext({ toolCalls: request.tool_calls,
    entriesByCallId: new Map([[request.tool_calls[0].id, {
      toolName: 'tool_search', toolUseId: request.tool_calls[0].id,
      toolInput: request.tool_calls[0].args, toolOutput: result.content, status: 'success' }]]),
    batchAdditionalContexts: [], injected, runId: 'fixture' });
  assert.equal(injected.length, 1);
  assert.ok(isHostBudgetNotice(injected[0]));
  const messages = [request, result, ...injected];
  const before = JSON.stringify(messages);
  assert.deepEqual(original.extractToolDiscoveries(messages), installed ? [toolName] : []);
  assert.deepEqual(candidate.extractToolDiscoveries(messages), [toolName]);
  assert.equal(candidate.hasToolSearchInCurrentTurn(messages), true);
  assert.equal(JSON.stringify(messages), before);
});

test('both helpers activate the same schema without mutating provider messages or budget', async () => {
  const { request, result, notice, registry } = await fixture();
  const messages = [request, result, notice];
  const before = JSON.stringify(messages);
  assert.deepEqual(candidate.extractToolDiscoveries(messages), [toolName]);
  assert.equal(candidate.hasToolSearchInCurrentTurn(messages), true);
  const context = new AgentContext({ agentId: 'fixture', provider: 'openAI', clientOptions: {},
    tools: [], toolDefinitions: [definition], toolRegistry: registry });
  assert.deepEqual(context.getActiveToolDefinitions(), []);
  context.markToolsAsDiscovered(candidate.extractToolDiscoveries(messages));
  const baseline = new AgentContext({ agentId: 'baseline', provider: 'openAI', clientOptions: {},
    tools: [], toolDefinitions: [definition], toolRegistry: registry });
  baseline.markToolsAsDiscovered(original.extractToolDiscoveries([request, result]));
  assert.deepEqual(context.getActiveToolDefinitions(), baseline.getActiveToolDefinitions());
  assert.equal(JSON.stringify(messages), before);
  assert.match(notice.content, /1 more tool-calling round/);
});

test('no-notice behavior and exact current tool-call lineage are preserved', async () => {
  const { request, result, notice } = await fixture();
  assert.deepEqual(candidate.extractToolDiscoveries([request, result]), original.extractToolDiscoveries([request, result]));
  const wrong = new ToolMessage({ content: result.content, artifact: result.artifact,
    name: 'tool_search', tool_call_id: 'unrelated-call' });
  assert.deepEqual(candidate.extractToolDiscoveries([request, wrong, notice]), []);
  assert.equal(candidate.hasToolSearchInCurrentTurn([request, wrong, notice]), false);
});

for (const mutation of ['plain-user', 'steer', 'untrusted', 'wrong-role', 'wrong-provenance', 'source-message']) {
  test(`does not scan through ${mutation} messages`, async () => {
    const { request, result, notice } = await fixture();
    const metadata = structuredClone(notice.additional_kwargs);
    if (mutation === 'plain-user') for (const key of Object.keys(metadata)) delete metadata[key];
    if (mutation === 'steer') metadata.source = 'steer';
    if (mutation === 'untrusted') metadata.injected = false;
    if (mutation === 'wrong-role') metadata.role = 'user';
    if (mutation === 'wrong-provenance') metadata.provenance.parts[0].attribution = 'user';
    if (mutation === 'source-message') metadata.sourceMessageId = 'original-user';
    const other = new HumanMessage({ content: notice.content, additional_kwargs: metadata });
    assert.deepEqual(candidate.extractToolDiscoveries([request, result, other]), []);
    assert.equal(candidate.hasToolSearchInCurrentTurn([request, result, other]), false);
    assert.deepEqual(candidate.extractToolDiscoveries([request, result, other, notice]), []);
    assert.equal(candidate.hasToolSearchInCurrentTurn([request, result, other, notice]), false);
  });
}
}
