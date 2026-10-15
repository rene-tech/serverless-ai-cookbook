// CPU-only: run against the exact installed SDK. No provider, MCP or model call.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { patchDiscoveries } = require('./scientific-tool-search-patch.cjs');
const graphPath = process.env.SCIENTIFIC_DISCOVERY_GRAPH || '/app/node_modules/@librechat/agents/dist/cjs/graphs/Graph.cjs';
if (!process.env.SCIENTIFIC_DISCOVERY_GRAPH && !fs.existsSync(graphPath)) {
  test('installed deferred-discovery regression', { skip: 'Requires exact installed @librechat/agents; set SCIENTIFIC_DISCOVERY_GRAPH' }, () => {});
} else {
const r = Module.createRequire(graphPath);
const modulePath = path.join(path.dirname(graphPath), '../messages/tools.cjs');
const original = r('../messages/tools.cjs');
const compiled = new Module(modulePath, module);
compiled.filename = modulePath;
compiled.paths = Module._nodeModulePaths(path.dirname(modulePath));
compiled._compile(patchDiscoveries(fs.readFileSync(modulePath, 'utf8')), modulePath);
const candidate = compiled.exports;
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

async function fixture() {
  const call = { type: 'tool_call', id: 'fixture-search', name: 'tool_search',
    args: { query: 'infer_admet_ai_native', max_results: 1 } };
  const registry = new Map([[toolName, definition]]);
  const result = await createToolSearch({ mode: 'local', toolRegistry: registry }).invoke(call);
  const request = new AIMessageChunk({ content: '', tool_calls: [call] });
  const hook = await createStepBudgetHook({ recursionLimit: 5 })({ entries: [{ toolName: 'tool_search', status: 'success' }] });
  const [notice] = convertInjectedMessages(hook.injectedMessages);
  assert.ok(isHostBudgetNotice(notice));
  return { request, result, notice, registry };
}

test('exact installed failure: trusted host notice hides the completed search', async () => {
  const { request, result, notice } = await fixture();
  assert.deepEqual(original.extractToolDiscoveries([request, result]), [toolName]);
  assert.deepEqual(original.extractToolDiscoveries([request, result, notice]), []);
  assert.equal(original.hasToolSearchInCurrentTurn([request, result, notice]), false);
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
  assert.deepEqual(original.extractToolDiscoveries(messages), []);
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
