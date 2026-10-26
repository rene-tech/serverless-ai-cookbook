/* Run against the actual packaged LibreChat, offline; all credentials below are synthetic. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const requireApp = createRequire('/app/package.json');
let api = requireApp('@librechat/api');
const dp = requireApp('librechat-data-provider');
const config = JSON.parse(fs.readFileSync(`${__dirname}/connection.json`));

async function main() {
  const rawConfig = structuredClone(config);
  rawConfig.headers['X-CamSol-Email'] = '{{CAMSOL_EMAIL}}';
  rawConfig.headers['X-CamSol-Password'] = '{{CAMSOL_PASSWORD}}';
  const oldOptions = (password) => api.processMCPEnv({ options: rawConfig, user: { id: 'user-one' },
    customUserVars: { CAMSOL_EMAIL: 'one@example.test', CAMSOL_PASSWORD: password } });
  const inheritedLiteralDefect = oldOptions('$&-$$').headers['X-CamSol-Password'] !== '$&-$$';
  let inheritedUnicodeLimit = false;
  try { new Headers(oldOptions('synthetic-雪').headers); } catch { inheritedUnicodeLimit = true; }
  const legacy = { options: { type: 'streamable-http', url: 'https://provider.example.test/mcp',
    headers: { Authorization: 'Bearer {{API_KEY}}', Other: '{{UNDECLARED:base64}}' } },
    customUserVars: { API_KEY: 'ordinary-synthetic-token' } };
  const legacyBefore = api.processMCPEnv(legacy);

  // Compile an isolated, patched copy of the ACTUAL installed module. No image,
  // live API, dependency or on-disk runtime file is changed by this CPU probe.
  const { patchPrivateVars } = await import('./patch-private-vars.mjs');
  const modulePath = requireApp.resolve('@librechat/api');
  const source = fs.readFileSync(modulePath, 'utf8');
  const patchedSource = patchPrivateVars(source);
  assert.equal(patchPrivateVars(patchedSource), patchedSource);
  const { Module } = require('node:module');
  const candidate = new Module(modulePath);
  candidate.filename = modulePath;
  candidate.paths = Module._nodeModulePaths(require('node:path').dirname(modulePath));
  candidate._compile(patchedSource, modulePath);
  api = candidate.exports;
  assert.deepEqual(api.processMCPEnv(legacy), legacyBefore);
  assert.equal(api.processMCPEnv(legacy).headers.Other, '{{UNDECLARED:base64}}');
  assert(dp.configSchema.safeParse({ version: '1.3.5', mcpServers: { camsol: config },
    mcpSettings: { allowedAddresses: ['127.0.0.1:8786'] } }).success);
  assert(api.requiresUserScopedConnection(config));
  assert.equal(api.canUseAppConnection(config), false);
  const options = (id, password) => api.processMCPEnv({ options: config,
    user: { id }, customUserVars: { CAMSOL_EMAIL: `${id}@example.test`, CAMSOL_PASSWORD: password } });
  const one = options('user-one', 'dummy%2F+value');
  const two = options('user-two', 'other-password');
  assert.equal(one.headers['X-Scientific-User'], 'user-one');
  assert.equal(two.headers['X-Scientific-User'], 'user-two');
  assert.equal(Buffer.from(one.headers['X-CamSol-Password'], 'base64').toString(), 'dummy%2F+value');
  for (const password of ['$&-$$', 'private-雪', '{{LIBRECHAT_USER_ID}}', 'b64:literal', '%2F +value']) {
    const resolved = options('user-one', password);
    new Headers(resolved.headers);
    assert.equal(Buffer.from(resolved.headers['X-CamSol-Password'], 'base64').toString(), password);
  }
  assert.equal(api.processMCPEnv({ options: { ...config, source: 'plugin' },
    user: { id: 'user-one' }, customUserVars: { CAMSOL_PASSWORD: 'dummy' } }).headers['X-CamSol-Password'],
    '{{CAMSOL_PASSWORD:base64}}');
  assert.equal(api.processMCPEnv({ options: rawConfig,
    customUserVars: { CAMSOL_PASSWORD: '$&-$$' } }).headers['X-CamSol-Password'], '$&-$$');
  assert.equal(api.isSSRFTarget('127.0.0.1', ['127.0.0.1:8786'], 8786), false);
  assert.equal(api.isSSRFTarget('127.0.0.1', ['127.0.0.1:8786'], 8787), true);
  let patched = null;
  let invalidations = 0;
  const handlers = api.createAdminConfigHandlers({
    hasConfigCapability: async () => true,
    findConfigByPrincipal: async () => null,
    patchConfigFields: async (principalType, principalId, principalModel, fields) => {
      patched = { principalType, principalId, principalModel, fields };
      return null;
    },
    invalidateConfigCaches: async () => { invalidations++; },
  });
  const response = { code: 200, status(code) { this.code = code; return this; },
    json(body) { this.body = body; return this; } };
  await handlers.patchConfigField({ user: { id: 'operator', role: 'ADMIN' },
    params: { principalType: 'user', principalId: '0123456789abcdef01234567' },
    body: { entries: [{ fieldPath: 'mcpServers.camsol', value: config },
      { fieldPath: 'mcpSettings.allowedAddresses', value: ['127.0.0.1:8786'] }] },
  }, response);
  assert.equal(response.code, 200, JSON.stringify(response.body));
  assert.equal(patched.principalType, 'user');
  assert.equal(patched.principalId, '0123456789abcdef01234567');
  assert.deepEqual(Object.keys(patched.fields), ['mcpServers.camsol', 'mcpSettings.allowedAddresses']);
  assert.equal(invalidations, 1);
  patched = null;
  await handlers.patchConfigField({ user: { id: 'operator', role: 'ADMIN' },
    params: { principalType: 'user', principalId: '0123456789abcdef01234567' },
    body: { entries: [{ fieldPath: 'mcpServers.camsol', value: { type: 'stdio', command: 'python' } }] },
  }, response);
  assert.equal(response.code, 400);
  assert.equal(patched, null);

  process.stdout.write(JSON.stringify({ schema: 'PASS', user_connection: 'PASS',
    two_user_headers: 'PASS', scoped_loopback_ssrf: 'PASS', admin_http_patch: 'PASS',
    stdio_override_guard: 'PASS', inherited_literal_replacement_defect: inheritedLiteralDefect,
    inherited_unicode_header_limit: inheritedUnicodeLimit, private_variable_candidate: 'PASS',
    plugin_placeholder_boundary: 'PASS', legacy_and_unknown_templates: 'PASS', live_api_bytes_changed: false,
    real_login_qualified: false, scientific_submission_available: false }) + '\n');
}
main().catch(() => { process.stderr.write('Installed connection-contract check failed.\n'); process.exitCode = 1; });
