// Actual startup seeder, actual installed MongoDB and SDK, synthetic offline env.
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const { createRequire } = require('node:module');
const installedRequire = createRequire('/app/package.json');
const { MongoClient } = installedRequire('mongodb');
const tools = ['describe_clinical_asr','upload_clinical_workspace_audio','transcribe_clinical_audio','get_clinical_transcription','cancel_clinical_transcription'].map(name => `${name}_mcp_medical-speech`);
async function main() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'clinical-seed-gate-'));
  const daemon = spawn('mongod', ['--dbpath', root, '--port', '27919', '--bind_ip', '127.0.0.1', '--noauth', '--quiet'], { stdio: 'ignore' });
  const stopped = new Promise(resolve => daemon.once('exit', resolve));
  try {
    assert.deepEqual(await fs.readFile('/app/seed-hcls-workbench.js'), await fs.readFile('/opt/hcls-librechat/seed-workbench.js'), 'Installed startup seeder must match the versioned candidate');
    const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !/^(SCIENTIFIC_|SEED_|CLINICAL_|NEBIUS_|MONGO_)/.test(key)));
    for (const [medical, english, platform = false] of [[false, false], [false, true], [true, false], [true, true], [false, false, true]]) {
      const uri = `mongodb://127.0.0.1:27919/clinical_seed_${medical}_${english}_${platform}`;
      const client = new MongoClient(uri, { serverSelectionTimeoutMS: 10000 });
      await client.connect();
      try {
        execFileSync('node', ['/app/seed-hcls-workbench.js'], { env: { ...env, MONGO_URI: uri,
          ...(platform ? { SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'platform' } : {}),
          ...(english ? { SCIENTIFIC_ENGLISH_SPEECH_URL: 'https://english.invalid/v1/audio/stream' } : {}),
          ...(medical ? { SCIENTIFIC_MEDICAL_SPEECH_HTTP_URL: 'https://medical.invalid', SCIENTIFIC_MEDICAL_SPEECH_API_KEY: 'synthetic-only-not-a-secret' } : {}) }, stdio: 'pipe' });
        const db = client.db();
        for (const id of ['agent_nebius_scientific_ai', 'agent_audio_transcription_tutorial']) {
          const agent = await db.collection('agents').findOne({ id });
          assert(agent, `Missing seeded agent ${id}`);
          assert.equal(agent.mcpServerNames.includes('medical-speech'), medical);
          for (const tool of tools) assert.equal(agent.tools.includes(tool), medical, `Missing actual seeded tool ${tool}`);
          if (medical) assert(agent.instructions.includes('separately configured medical-speech MCP'));
          assert.equal(agent.instructions.includes('Do not call the legacy platform English App'), english);
          assert.equal(agent.instructions.includes('This clinical-speech release uses shared Scientific AI Apps'), platform);
          if (platform) {
            assert(agent.tools.includes('invoke_model_mcp_scientific-ai-apps'));
            assert(agent.instructions.includes('nemotron-speech-en-medical-0-6b'));
            assert(agent.instructions.includes('runs Sortformer after Stop'));
            assert(!agent.mcpServerNames.includes('medical-speech'));
          }
          if (medical) assert(agent.instructions.includes('dedicated medical Serverless endpoint, not the Scientific AI platform operation service'));
          const acl = await db.collection('aclentries').findOne({ principalType: 'public', resourceType: 'agent', resourceId: agent._id });
          assert.equal(acl?.permBits, 1, 'Ordinary users retain view access, not public mutation');
        }
        const owner = await db.collection('users').findOne({ email: 'nebius-scientific-ai-agent@localhost.invalid' });
        assert.equal(owner.role, 'USER');
      } finally { await client.close(); }
    }
    console.log(JSON.stringify({ installed_startup_seed: 'passed', default_and_medical: true, primary_and_audio_agents: true, ordinary_owner: true, public_read_only_acl: true, inference_calls: 0 }));
  } finally {
    daemon.kill('SIGTERM'); await stopped;
    await fs.rm(root, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
