// Run inside the exact candidate image with this directory mounted read-only.
// Local scripted models/HTTP faults test the real graph; no alternative hosted
// inference provider is used or enabled. No GPU or customer credentials needed.
const test = require('node:test');
const assert = require('node:assert/strict');
const { setTimeout: sleep } = require('node:timers/promises');
const { createRequire } = require('node:module');
const { readFileSync } = require('node:fs');
const http = require('node:http');
const { randomUUID } = require('node:crypto');
const graphPath = '/app/node_modules/@librechat/agents/dist/cjs/graphs/Graph.cjs';
const r = createRequire(graphPath);
const { Run } = r('../run.cjs');
const { HumanMessage } = r('@langchain/core/messages');
const { AgentBudgetStop, forRun } = require('/opt/hcls-librechat/scientific-agent-budget.cjs');
const toolName = 'observe_fixture';

async function fixture(stream, { callMs = 120, turnMs = 1000, tool = false, name = toolName } = {}) {
  // Each graph resolves configuration once; no mutation of a running graph.
  const oldCall = process.env.SCIENTIFIC_AGENT_MODEL_DEADLINE_MS;
  const oldTurn = process.env.SCIENTIFIC_AGENT_MODEL_TIME_MS;
  process.env.SCIENTIFIC_AGENT_MODEL_DEADLINE_MS = String(callMs);
  process.env.SCIENTIFIC_AGENT_MODEL_TIME_MS = String(turnMs);
  let run;
  try {
    run = await Run.create({ runId: randomUUID(), graphConfig: { type: 'standard', agents: [{
      agentId: 'default', provider: 'openAI', clientOptions: {}, tools: [],
      toolDefinitions: tool ? [{ name, parameters: { type: 'object', properties: {} } }] : [],
    }] } });
    forRun(run.Graph);
  } finally {
    for (const [key, value] of [['SCIENTIFIC_AGENT_MODEL_DEADLINE_MS', oldCall], ['SCIENTIFIC_AGENT_MODEL_TIME_MS', oldTurn]]) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
  run.Graph.overrideTestModel(['fixture'], 0);
  if (stream) run.Graph.overrideModel._streamResponseChunks = stream;
  return run;
}

async function execute(run, onTool = () => 'unchanged result') {
  const events = [];
  let tools = 0;
  for await (const event of run.graphRunnable.streamEvents({ messages: [new HumanMessage('Controlled fixture, no actual scientific submissions.')] }, {
    version: 'v2', recursionLimit: 40, callbacks: [{ handleCustomEvent: run.createCustomEventCallback() }],
  })) {
    events.push(event);
    if (event.event === 'on_custom_event' && event.name === 'on_tool_execute') {
      const output = [];
      for (const call of event.data.toolCalls) {
        tools++;
        output.push({ toolCallId: call.id, status: 'success', content: await onTool(call) });
      }
      event.data.resolve(output);
    }
  }
  return { events, tools, reply: run.Graph.messages.at(-1), graph: run.Graph };
}

function assertPause(result, reason) {
  assert.equal(result.reply.response_metadata.scientific_agent_incomplete, true);
  assert.equal(result.reply.response_metadata.scientific_agent_stop, reason);
  assert.match(result.reply.content, /incomplete/);
  assert.equal(result.events.at(-1).event, 'on_chain_end');
  const text = result.events.filter((e) => e.name === 'on_message_delta')
    .flatMap((e) => e.data.delta.content ?? []).filter((part) => part.text === result.reply.content);
  assert.equal(text.length, 1, 'One actual UI message, not only a server exception');
  assert.equal(result.graph.runProducedAiMessageIds.has(result.reply.id), true);
  assert.equal(result.reply.tool_calls.length, 0, 'A pause cannot replay a tool');
}

async function* endless(_messages, options) {
  while (true) {
    await sleep(5, undefined, { signal: options.signal });
    const chunk = this._createResponseChunk('');
    chunk.message.additional_kwargs.reasoning_content = 'Still thinking. ';
    yield chunk;
  }
}

test('installed patch fails closed on duplicate installation or upstream drift', async () => {
  const { patchGraph, patchInvoke } = await import('./patch-bounded-reasoning.mjs');
  assert.throws(() => patchGraph(readFileSync(graphPath, 'utf8')), /already patched/);
  assert.throws(() => patchInvoke(readFileSync('/app/node_modules/@librechat/agents/dist/cjs/llm/invoke.cjs', 'utf8')), /already patched/);
  assert.throws(() => patchGraph('upstream changed'), /Unsupported/);
  assert.throws(() => patchInvoke('upstream changed'), /Unsupported/);
});

test('actual compiled graph stops a continuously streaming reasoning turn visibly', async () => {
  const run = await fixture(endless);
  const started = Date.now();
  const result = await execute(run);
  assertPause(result, 'model_deadline');
  assert.ok(Date.now() - started < 2000);
  assert.equal(result.tools, 0);
  assert.notEqual(run.Graph.signal?.aborted, true);
});

test('actual ToolNode loop stops after original read plus two unchanged rounds', async () => {
  let generations = 0;
  const run = await fixture(async function* () {
    generations++;
    yield this._createResponseChunk('', [{ name: toolName, id: `call-${generations}`, args: '{}', index: 0 }]);
  }, { tool: true, callMs: 1000 });
  const result = await execute(run);
  assertPause(result, 'repeated_tools');
  assert.equal(generations, 3); assert.equal(result.tools, 3);
  assert.equal([...run.Graph.pendingToolCallsByStep.values()].some((set) => set.size > 0), false);
});

test('changing results continue normally rather than being mistaken for a tool loop', async () => {
  let generations = 0;
  const run = await fixture(async function* () {
    generations++;
    if (generations < 5) yield this._createResponseChunk('', [{ name: toolName, id: `call-${generations}`, args: '{}', index: 0 }]);
    else yield this._createResponseChunk('Completed fixture result', undefined, { finish_reason: 'stop' });
  }, { tool: true, callMs: 1000 });
  const result = await execute(run, () => `new state ${generations}`);
  assert.equal(result.reply.content, 'Completed fixture result');
  assert.equal(result.tools, 4);
  assert.equal(result.reply.response_metadata.scientific_agent_incomplete, undefined);
});

test('real graph follows five unchanged bounded job observations to completion', async () => {
  const name = 'read_execution_mcp_environment-execution';
  const job_id = randomUUID();
  let generations = 0;
  const run = await fixture(async function* () {
    generations++;
    if (generations <= 6) yield this._createResponseChunk('', [{ name,
      id: `poll-${generations}`, args: JSON.stringify({ job_id, wait_seconds: 30 }), index: 0 }]);
    else yield this._createResponseChunk('The existing operation finished', undefined, { finish_reason: 'stop' });
  }, { tool: true, name, callMs: 1000, turnMs: 2000 });
  const result = await execute(run, () => JSON.stringify({ job_id,
    status: generations < 6 ? 'running' : 'completed',
    requested_wait_seconds: 30, effective_wait_seconds: 25 }));
  assert.equal(result.tools, 6);
  assert.equal(result.reply.content, 'The existing operation finished');
  assert.equal(result.reply.response_metadata.scientific_agent_incomplete, undefined);
});

test('actual graph accumulates model time across changing tool rounds', async () => {
  let generations = 0;
  const run = await fixture(async function* (_messages, options) {
    generations++;
    await sleep(120, undefined, { signal: options.signal });
    yield this._createResponseChunk('', [{ name: toolName, id: `call-${generations}`, args: '{}', index: 0 }]);
  }, { tool: true, callMs: 250, turnMs: 350 });
  const result = await execute(run, () => `new evidence ${generations}`);
  assertPause(result, 'turn_model_time');
  assert.equal(result.tools, 2);
});

test('a late tool chunk from a provider ignoring abort is never executed', async () => {
  let generatedLate = false;
  const run = await fixture(async function* () {
    yield this._createResponseChunk('');
    await sleep(250); // Deliberately ignore the provider signal.
    generatedLate = true;
    yield this._createResponseChunk('', [{ name: toolName, id: 'late-submit', args: '{}', index: 0 }]);
  }, { tool: true });
  const result = await execute(run, () => assert.fail('Late work must not be submitted'));
  assertPause(result, 'model_deadline');
  await sleep(300);
  assert.equal(generatedLate, true, 'The adversarial provider really emitted late output');
  assert.equal(result.tools, 0);
  assert.equal([...run.Graph.pendingToolCallsByStep.values()].some((set) => set.size > 0), false);
});

test('submitted durable work outlives a thinking timeout with no replay or cancellation', async () => {
  let generations = 0;
  const job = { id: randomUUID(), state: 'not-submitted', submissions: 0 };
  let completion;
  const run = await fixture(async function* (...args) {
    generations++;
    if (generations === 1) {
      yield this._createResponseChunk('', [{ name: toolName, id: 'submit-once', args: '{}', index: 0 }]);
      return;
    }
    yield* endless.call(this, ...args);
  }, { tool: true });
  const result = await execute(run, () => {
    job.submissions++; job.state = 'running';
    completion = sleep(350).then(() => { job.state = 'completed'; });
    return JSON.stringify({ job_id: job.id, status: 'running' });
  });
  assertPause(result, 'model_deadline');
  assert.match(result.reply.content, new RegExp(job.id));
  assert.equal(job.state, 'running');
  assert.equal(job.submissions, 1); assert.equal(result.tools, 1);
  await completion;
  assert.equal(job.state, 'completed'); assert.equal(job.submissions, 1);
});

test('a slow ToolNode is outside the clock; a separate run is not blocked', async () => {
  let generations = 0;
  const slow = await fixture(async function* () {
    generations++;
    if (generations === 1) yield this._createResponseChunk('', [{ name: toolName, id: 'slow-once', args: '{}', index: 0 }]);
    else yield this._createResponseChunk('Finished after tool wait', undefined, { finish_reason: 'stop' });
  }, { tool: true, callMs: 100, turnMs: 180 });
  const fast = await fixture(async function* () { yield this._createResponseChunk('Independent result', undefined, { finish_reason: 'stop' }); });
  const [a, b] = await Promise.all([execute(slow, async () => { await sleep(350); return 'new completed data'; }), execute(fast)]);
  assert.equal(a.reply.content, 'Finished after tool wait');
  assert.equal(b.reply.content, 'Independent result');
  assert.ok(forRun(slow.Graph).usedMs < 180);
});

test('real OpenAI-compatible HTTP stream is aborted even while reasoning chunks arrive', async () => {
  let chunks = 0;
  let closed = false;
  const server = http.createServer((request, response) => {
    assert.equal(request.url, '/v1/chat/completions');
    request.resume();
    response.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' });
    const timer = setInterval(() => {
      chunks++;
      response.write('data: ' + JSON.stringify({ id: 'fixture-stream', object: 'chat.completion.chunk', model: 'transport-fixture',
        choices: [{ index: 0, delta: { reasoning_content: 'Continuous reasoning. ' }, finish_reason: null }] }) + '\n\n');
    }, 5);
    response.on('close', () => { closed = true; clearInterval(timer); });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const { ChatOpenAI } = r('../llm/openai/index.cjs');
    const run = await fixture(null, { callMs: 400, turnMs: 1500 });
    run.Graph.overrideModel = new ChatOpenAI({ model: 'transport-fixture', apiKey: 'local-fixture-only', maxRetries: 0,
      configuration: { baseURL: `http://127.0.0.1:${server.address().port}/v1` } });
    const result = await execute(run);
    assertPause(result, 'model_deadline');
    await sleep(50);
    assert.ok(chunks > 0); assert.equal(closed, true, 'Upstream HTTP socket closed, not just a UI timeout');
  } finally {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
});
