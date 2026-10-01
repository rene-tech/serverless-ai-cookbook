// Opt-in compatibility check on the installed graph, not a scientific/readiness
// benchmark. Requires only a Token Factory key; no platform/customer work is run.
const test = require('node:test');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const { randomUUID } = require('node:crypto');
const r = createRequire('/app/node_modules/@librechat/agents/dist/cjs/graphs/Graph.cjs');
const { Run } = r('../run.cjs');
const { HumanMessage } = r('@langchain/core/messages');
const baseURL = 'https://api.tokenfactory.nebius.com/v1';
const model = 'zai-org/GLM-5.3-Flash'; // Existing product default, not a new selection.
const apiKey = process.env.NEBIUS_API_KEY;
if (!apiKey) throw new Error('Supply the Token Factory key through the environment, not arguments.');

test('existing model is present in the live Token Factory catalog', async () => {
  // Use the installed SDK transport, just like the actual model connection.
  const { ChatOpenAI } = r('../llm/openai/index.cjs');
  const transport = new ChatOpenAI({ model, apiKey, configuration: { baseURL }, timeout: 20000, maxRetries: 0 });
  transport._getClientOptions({});
  const response = await transport.client.models.list();
  assert.ok(response.data.some((entry) => entry.id === model));
});

for (const effort of ['low', 'high']) test(`installed graph completes a Token Factory ${effort}-reasoning response normally`, async () => {
  const run = await Run.create({ runId: randomUUID(), graphConfig: { type: 'standard', agents: [{
    agentId: 'default', provider: 'openAI', tools: [],
    clientOptions: { model, apiKey, configuration: { baseURL }, maxTokens: 2048,
      modelKwargs: { reasoning_effort: effort } },
  }] } });
  const started = performance.now();
  for await (const event of run.graphRunnable.streamEvents({ messages: [new HumanMessage('What is 17 + 25? Respond with only the integer.')] }, {
    version: 'v2', recursionLimit: 4, callbacks: [{ handleCustomEvent: run.createCustomEventCallback() }],
  })) { /* Same streaming graph used by the workbench. No customer tools. */ }
  const reply = run.Graph.messages.at(-1);
  assert.equal(reply.response_metadata.scientific_agent_incomplete, undefined);
  assert.equal(reply.content.trim(), '42');
  console.log(JSON.stringify({ model, reasoning_effort: effort, elapsed_ms: Math.round(performance.now() - started),
    finish_reason: reply.response_metadata.finish_reason, usage: reply.usage_metadata ?? null }));
});
