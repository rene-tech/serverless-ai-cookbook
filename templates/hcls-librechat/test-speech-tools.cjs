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
      if (name === 'node:fs') return { readFileSync: (file) => String(file).endsWith('/agent-instructions.md') ? 'CORE_INSTRUCTIONS' : 'GATEWAY_INSTRUCTIONS' };
      if (name === 'librechat-data-provider') return { Constants: { mcp_all: 'mcp_all' } };
      throw new Error(`Unexpected dependency ${name}`);
    },
  };
  vm.runInNewContext(seedSource.replace(/main\(\)\.catch\([\s\S]*$/, '')
    + '\nmodule.exports = { agents, seedAgent, reasoningEffort, completionTokens };', context);
  return context.module.exports;
}

function renderConfig(extra = {}) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speech-tools-'));
  try {
    const instructions = path.join(directory, 'gateway.md');
    const output = path.join(directory, 'config.json');
    fs.writeFileSync(instructions, 'GATEWAY_INSTRUCTIONS');
    const env = Object.fromEntries(Object.entries(process.env)
      .filter(([key]) => !/^(SCIENTIFIC_|TEAM_|SEED_|CLINICAL_|NEBIUS_)/.test(key)));
    const child = spawnSync(process.execPath, [path.join(__dirname, 'render-config.mjs'), output], {
      env: { ...env, SCIENTIFIC_DISCOVER_CHAT_MODELS: 'false',
        SCIENTIFIC_AGENT_INSTRUCTIONS_PATH: instructions,
        SCIENTIFIC_CORE_INSTRUCTIONS_PATH: path.join(__dirname, 'agent-instructions.md'), ...extra }, encoding: 'utf8',
    });
    assert.equal(child.status, 0, child.stderr);
    return JSON.parse(fs.readFileSync(output, 'utf8'));
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

async function seedAll(env = {}) {
  const policy = seedPolicy(env);
  const saved = [];
  const collection = { async updateOne(_filter, update) { saved.push(update.$set); },
    async findOne() { return { _id: 'synthetic-agent' }; } };
  for (const definition of policy.agents()) await policy.seedAgent({ agents: collection,
    aclEntries: { async updateOne() {} }, owner: { _id: 'owner' }, now: new Date(0), definition });
  return saved;
}

const speechTools = ['workbench_transcribe_audio_mcp_scientific-demos', 'workbench_get_transcription_mcp_scientific-demos'];

test('default reasoning and output capacity are unchanged; explicit efforts are validated', () => {
  const policy = seedPolicy();
  assert.equal(policy.reasoningEffort, undefined);
  assert.equal(policy.completionTokens, 16384);
  for (const effort of ['low', 'high', 'max']) {
    assert.equal(seedPolicy({ SCIENTIFIC_CHAT_REASONING_EFFORT: effort }).reasoningEffort, effort);
  }
  assert.throws(() => seedPolicy({ SCIENTIFIC_CHAT_REASONING_EFFORT: 'none' }), /Unsupported/);
});

test('chat audio transcription is a default capability of the primary and speech agents', async () => {
  const saved = await seedAll({ SCIENTIFIC_CHAT_REASONING_EFFORT: 'high' });
  const speech = saved.find(agent => agent.id === 'agent_audio_transcription_tutorial');
  const general = saved.find(agent => agent.id === 'agent_nebius_scientific_ai');
  for (const agent of [speech, general]) {
    for (const name of speechTools) assert(agent.tools.includes(name), `${agent.id} lacks ${name}`);
    assert(agent.instructions.includes('AUDIO ATTACHMENTS'), `${agent.id} lacks the audio attachment rules`);
    assert(agent.instructions.includes('"medical-speakers"'));
    assert.equal(agent.skills_enabled, true);
    assert.equal(agent.model_parameters.reasoning_effort, 'high');
    assert.equal(agent.model_parameters.max_tokens, 16384);
    assert(agent.mcpServerNames.includes('scientific-demos'));
    assert(agent.tools.includes('execute_command_mcp_environment-execution'));
  }
  // The primary agent keeps its compact core prompt; tutorials keep the full guides.
  assert(general.instructions.startsWith('CORE_INSTRUCTIONS'));
  assert(!general.instructions.includes('GATEWAY_INSTRUCTIONS'));
  assert(speech.instructions.includes('GATEWAY_INSTRUCTIONS'));
  assert.equal(speech.name, 'Speech & Clinical Documentation');
  assert.deepEqual(Array.from(speech.conversation_starters).slice(0, 3),
    ['Transcribe this with Nemotron', 'Now transcribe it with the fine-tuned Nemotron', 'Now add speaker detection']);
  const protein = saved.find(agent => agent.id === 'agent_protein_structure');
  for (const name of speechTools) assert(!protein.tools.includes(name));
  assert(!protein.instructions.includes('AUDIO ATTACHMENTS'));
});

test('no workshop mode: the primary agent stays the default and speech secrets remain environment references', () => {
  const config = renderConfig({ SCIENTIFIC_SPEECH_WORKSHOP: 'true', SCIENTIFIC_SPEECH_CHAT_MODEL: 'Qwen/Qwen3.8-27B',
    SCIENTIFIC_ENGLISH_SPEECH_API_KEY: 'synthetic-speech-key', SCIENTIFIC_MEDICAL_SPEECH_URL: 'https://medical.invalid' });
  assert.deepEqual(config.modelSpecs.list.filter(spec => spec.default).map(spec => spec.preset.agent_id),
    ['agent_nebius_scientific_ai']);
  assert(!config.modelSpecs.list.some(spec => spec.name === 'speech-workshop'));
  assert.equal(config.mcpServers['scientific-demos'].env.SCIENTIFIC_ENGLISH_SPEECH_API_KEY,
    '${SCIENTIFIC_ENGLISH_SPEECH_API_KEY}');
  assert.equal(config.mcpServers['scientific-demos'].env.SCIENTIFIC_MEDICAL_SPEECH_URL, '${SCIENTIFIC_MEDICAL_SPEECH_URL}');
  assert(!JSON.stringify(config).includes('synthetic-speech-key'));
  const plain = renderConfig();
  assert.equal(plain.mcpServers['scientific-demos'].env.SCIENTIFIC_MEDICAL_SPEECH_URL, undefined);
});

test('the two speech tools join the immediately available workbench surface; other speech tools stay deferred', () => {
  const options = require('./scientific-tool-options.cjs');
  const result = options({ tools: speechTools, tool_options: {} }, speechTools.map(name => ({ name })));
  for (const name of speechTools) assert.equal(result[name], undefined);
  assert.equal(result['clinical_report_from_transcript_mcp_scientific-demos'].defer_loading, true);
  assert.equal(result['future_speech_tool_mcp_scientific-demos'].defer_loading, true);
  assert.equal(result['infer_nemotron_speech_en_medical_0_6b_native_mcp_scientific-ai-apps'].defer_loading, true);
});
