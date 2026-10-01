// Execute in the exact LibreChat image, without network or real credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createRequire } = require('node:module');
const { spawnSync } = require('node:child_process');
const installedRequire = createRequire('/app/package.json');
const { configSchema } = installedRequire('librechat-data-provider');
const renderer = process.argv[2] || '/opt/hcls-librechat/render-config.mjs';
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speech-config-qualification-'));
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !/^(SCIENTIFIC_|SEED_|CLINICAL_|NEBIUS_)/.test(key)));
Object.assign(env, {
  SCIENTIFIC_DISCOVER_CHAT_MODELS: 'false',
  SCIENTIFIC_MODELS_API_BASE_URL: 'https://platform.invalid/v1',
  SCIENTIFIC_MODELS_MCP_URL: 'https://platform.invalid/mcp',
});
for (const medical of [false, true]) {
  const output = path.join(directory, medical ? 'medical.json' : 'default.json');
  const configured = { ...env, ...(medical ? {
    SCIENTIFIC_MEDICAL_SPEECH_HTTP_URL: 'https://medical.invalid',
    SCIENTIFIC_MEDICAL_SPEECH_API_KEY: 'synthetic-medical-credential',
  } : {}) };
  const child = spawnSync('node', [renderer, output], { env: configured, encoding: 'utf8' });
  assert.equal(child.status, 0, 'Offline configuration renderer must succeed');
  const raw = fs.readFileSync(output, 'utf8');
  assert(!raw.includes('synthetic-medical-credential'), 'Rendered configuration must not embed credentials');
  const config = JSON.parse(raw);
  const parsed = configSchema.safeParse(config);
  assert(parsed.success, `Installed LibreChat configuration schema rejected medical=${medical}: ${JSON.stringify(parsed.error?.issues)}`);
  assert.equal(Boolean(config.mcpServers['medical-speech']), medical);
  if (medical) {
    assert.equal(config.mcpServers['medical-speech'].env.SCIENTIFIC_MEDICAL_SPEECH_API_KEY, '${SCIENTIFIC_MEDICAL_SPEECH_API_KEY}');
    assert.equal(config.mcpServers['medical-speech'].command, '/opt/scientific-client/bin/python');
  }
}
console.log(JSON.stringify({ installed_librechat_schema: 'passed', default_configuration: 'passed', medical_configuration: 'passed', literal_credential_absent: true }));
