const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

const seedSource = fs.readFileSync(path.join(__dirname, 'seed-workbench.js'), 'utf8');
function seedPolicy(env = {}) {
  const context = {
    process: { env }, module: { exports: {} },
    require(name) {
      if (name === 'mongodb') return { ObjectId: class {} };
      if (name === 'node:fs') return { readFileSync: () => 'GATEWAY_INSTRUCTIONS' };
      if (name === 'librechat-data-provider') return { Constants: { mcp_all: 'mcp_all' } };
      throw new Error(`Unexpected dependency ${name}`);
    },
  };
  vm.runInNewContext(seedSource.replace(/main\(\)\.catch\([\s\S]*$/, '')
    + '\nmodule.exports = { agents, seedAgent, reasoningEffort, fastWorkflowInstructions, completionTokens };', context);
  return context.module.exports;
}

function renderConfig(extra = {}) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'fast-chat-policy-'));
  try {
    const instructions = path.join(directory, 'gateway.md');
    const output = path.join(directory, 'config.json');
    fs.writeFileSync(instructions, 'GATEWAY_INSTRUCTIONS');
    const env = Object.fromEntries(Object.entries(process.env)
      .filter(([key]) => !/^(SCIENTIFIC_|TEAM_|SEED_|CLINICAL_|NEBIUS_)/.test(key)));
    const child = spawnSync(process.execPath, [path.join(__dirname, 'render-config.mjs'), output], {
      env: { ...env, SCIENTIFIC_DISCOVER_CHAT_MODELS: 'false',
        SCIENTIFIC_AGENT_INSTRUCTIONS_PATH: instructions, ...extra }, encoding: 'utf8',
    });
    assert.equal(child.status, 0, child.stderr);
    return JSON.parse(fs.readFileSync(output, 'utf8'));
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

test('scope policy leaves default reasoning and output capacity unchanged', () => {
  const policy = seedPolicy();
  assert.equal(policy.reasoningEffort, undefined);
  assert.equal(policy.completionTokens, 16384);
});

test('explicit research effort is preserved; unknown efforts are rejected', () => {
  for (const effort of ['low', 'high', 'max']) {
    assert.equal(seedPolicy({ SCIENTIFIC_CHAT_REASONING_EFFORT: effort }).reasoningEffort, effort);
  }
  assert.throws(() => seedPolicy({ SCIENTIFIC_CHAT_REASONING_EFFORT: 'none' }), /Unsupported/);
});

test('scope policy does not add parameters to other providers or models', () => {
  assert.equal(seedPolicy({ SCIENTIFIC_CHAT_PROVIDER: 'openAI' }).reasoningEffort, undefined);
  assert.equal(seedPolicy({ SCIENTIFIC_CHAT_MODEL: 'Qwen/Qwen3-235B-A22B-Instruct-2507' }).reasoningEffort, undefined);
});

test('every seeded tutorial receives final scope rules without dropping tools or parameters', async () => {
  const policy = seedPolicy();
  const saved = [];
  const collection = {
    async updateOne(_filter, update) { saved.push(update.$set); },
    async findOne() { return { _id: 'synthetic-agent' }; },
  };
  for (const definition of policy.agents()) {
    await policy.seedAgent({ agents: collection, aclEntries: { async updateOne() {} },
      owner: { _id: 'synthetic-owner' }, now: new Date(0), definition });
  }
  assert(saved.length > 1);
  for (const agent of saved) {
    assert.deepEqual(JSON.parse(JSON.stringify(agent.model_parameters)), {
      model: 'zai-org/GLM-5.3-Flash', max_tokens: 16384,
    });
    assert(agent.instructions.endsWith(policy.fastWorkflowInstructions));
    assert(agent.instructions.includes('GATEWAY_INSTRUCTIONS'));
    assert(agent.tools.includes('workbench_get_operation_mcp_scientific-demos'));
    assert(agent.tools.includes('execute_command_mcp_environment-execution'));
  }
});

test('direct presets share scope rules without adding reasoning parameters', () => {
  const config = renderConfig();
  const direct = config.modelSpecs.list.filter(spec => spec.preset.endpoint !== 'agents');
  assert.equal(config.endpoints.agents.recursionLimit, 50);
  for (const spec of direct) {
    assert(spec.preset.promptPrefix.endsWith(seedPolicy().fastWorkflowInstructions));
    assert.equal(spec.preset.reasoning_effort, undefined);
  }
});

test('renderer preserves its original provider parameter contract', () => {
  const config = renderConfig({ SCIENTIFIC_CHAT_REASONING_EFFORT: 'high' });
  const glm = config.modelSpecs.list.find(spec => spec.preset.model === 'zai-org/GLM-5.3-Flash');
  assert.equal(glm.preset.reasoning_effort, undefined);
});

test('workshop has only two speech tools without changing the general agent or reasoning', async () => {
  const policy = seedPolicy({ SCIENTIFIC_SPEECH_WORKSHOP: 'true', SCIENTIFIC_CHAT_REASONING_EFFORT: 'high' });
  const saved = [];
  const collection = { async updateOne(_filter, update) { saved.push(update.$set); },
    async findOne() { return { _id: 'synthetic-agent' }; } };
  for (const definition of policy.agents()) await policy.seedAgent({ agents: collection,
    aclEntries: { async updateOne() {} }, owner: { _id: 'owner' }, now: new Date(0), definition });
  const speech = saved.find(agent => agent.id === 'agent_audio_transcription_tutorial');
  assert.deepEqual(Array.from(speech.tools), ['workbench_transcribe_audio_mcp_scientific-demos',
    'workbench_get_transcription_mcp_scientific-demos']);
  assert.deepEqual(Array.from(speech.mcpServerNames), ['scientific-demos']);
  assert.equal(speech.skills_enabled, false);
  assert.equal(speech.model_parameters.reasoning_effort, 'high');
  assert.equal(speech.model_parameters.max_tokens, 16384);
  assert(speech.instructions.length < 2000);
  assert(!speech.instructions.includes('GATEWAY_INSTRUCTIONS'));
  assert(speech.instructions.includes('fresh inference'));
  const general = saved.find(agent => agent.id === 'agent_nebius_scientific_ai');
  assert(general.instructions.includes('GATEWAY_INSTRUCTIONS'));
  assert(general.tools.includes('execute_command_mcp_environment-execution'));
});

test('workshop is an explicit new-chat default; speech secrets remain environment references', () => {
  const config = renderConfig({ SCIENTIFIC_SPEECH_WORKSHOP: 'true',
    SCIENTIFIC_ENGLISH_SPEECH_API_KEY: 'synthetic-speech-key',
    SCIENTIFIC_MEDICAL_SPEECH_URL: 'https://medical.invalid' });
  assert.deepEqual(config.modelSpecs.list.filter(spec => spec.default).map(spec => spec.preset.agent_id),
    ['agent_audio_transcription_tutorial']);
  assert.equal(config.mcpServers['scientific-demos'].env.SCIENTIFIC_ENGLISH_SPEECH_API_KEY,
    '${SCIENTIFIC_ENGLISH_SPEECH_API_KEY}');
  assert(!JSON.stringify(config).includes('synthetic-speech-key'));
  assert.equal(renderConfig().modelSpecs.list.find(spec => spec.default).preset.agent_id,
    'agent_nebius_scientific_ai');
});

test('scope rule keeps safeguards, durable polling and explicit deep work', () => {
  const text = seedPolicy().fastWorkflowInstructions;
  for (const expected of ['result and stop', 'notebook', 'SOAP note', 'once and reuse',
    'authorization, input validation, request isolation and required clinical review',
    'Poll only the original operation', 'all reasoning, analysis and checks necessary',
    'source investigation and debugging remain in scope',
    'Fully perform scientific analysis needed']) assert(text.includes(expected));
});

test('explicit speech model override changes only the enabled workshop agent', async () => {
  for (const enabled of [false, true]) {
    const policy = seedPolicy({ SCIENTIFIC_SPEECH_WORKSHOP: String(enabled),
      SCIENTIFIC_SPEECH_CHAT_MODEL: 'Qwen/Qwen3.8-27B', SCIENTIFIC_CHAT_REASONING_EFFORT: 'high' });
    const saved = [];
    const collection = { async updateOne(_filter, update) { saved.push(update.$set); },
      async findOne() { return { _id: 'synthetic-agent' }; } };
    for (const definition of policy.agents()) await policy.seedAgent({ agents: collection,
      aclEntries: { async updateOne() {} }, owner: { _id: 'owner' }, now: new Date(0), definition });
    for (const agent of saved) {
      const expected = enabled && agent.id === 'agent_audio_transcription_tutorial'
        ? 'Qwen/Qwen3.8-27B' : 'zai-org/GLM-5.3-Flash';
      assert.equal(agent.model, expected);
      assert.equal(agent.model_parameters.model, expected);
      assert.equal(agent.model_parameters.reasoning_effort, 'high');
      assert.equal(agent.model_parameters.max_tokens, 16384);
    }
  }
});

test('workshop retains its previous model and reasoning default without explicit override', async () => {
  const policy = seedPolicy({ SCIENTIFIC_SPEECH_WORKSHOP: 'true' });
  let saved;
  await policy.seedAgent({ agents: { async updateOne(_filter, update) { saved = update.$set; },
    async findOne() { return { _id: 'synthetic-agent' }; } }, aclEntries: { async updateOne() {} },
    owner: { _id: 'owner' }, now: new Date(0),
    definition: policy.agents().find(agent => agent.id === 'agent_audio_transcription_tutorial') });
  assert.equal(saved.model, 'zai-org/GLM-5.3-Flash');
  assert.equal(saved.model_parameters.model, 'zai-org/GLM-5.3-Flash');
  assert.equal(saved.model_parameters.reasoning_effort, undefined);
});

test('only the two explicit speech tools join the immediately available workbench surface', () => {
  const options = require('./scientific-tool-options.cjs');
  const names = ['workbench_transcribe_audio_mcp_scientific-demos', 'workbench_get_transcription_mcp_scientific-demos'];
  const result = options({ tools: names, tool_options: {} }, names.map(name => ({ name })));
  for (const name of names) assert.equal(result[name], undefined);
  assert.equal(result['clinical_report_from_transcript_mcp_scientific-demos'].defer_loading, true);
  assert.equal(result['future_speech_tool_mcp_scientific-demos'].defer_loading, true);
  assert.equal(result['infer_nemotron_speech_en_medical_0_6b_native_mcp_scientific-ai-apps'].defer_loading, true);
});
