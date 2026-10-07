const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

function routeFixture(env, personal) {
  const routes = [], middleware = [], calls = [];
  const auth = () => {};
  const router = { use: (...args) => middleware.push(...args) };
  for (const verb of ['get', 'post', 'put']) router[verb] = (route, ...handlers) => routes.push({ route, handlers });
  const dependencies = {
    express: { Router: () => router }, multer: () => ({ single: () => () => {} }),
    '~/server/middleware': { requireJwtAuth: auth },
    '~/server/services/PluginService': { getUserPluginAuthValue: async () => personal },
    '/opt/hcls-librechat/demos/service.cjs': {
      platform: async (key) => { calls.push(key); return { data: [] }; },
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'router.cjs'), 'utf8'), {
    require: (name) => dependencies[name] || require(name), module: { exports: {} }, process: { env },
  });
  assert.equal(middleware[0], auth, 'shared credentials never bypass login');
  return { calls, async get(route) {
    return new Promise((resolve, reject) => routes.find((r) => r.route === route).handlers[0](
      { user: { id: 'new-participant' }, query: {} }, { json: resolve }, reject,
    ));
  } };
}

for (const scenario of [
  { label: 'default does not share a server key', env: { SCIENTIFIC_MODELS_API_KEY: 'server-fixture' }, expected: undefined },
  { label: 'explicit shared tenant serves new registrations', env: { SCIENTIFIC_MODELS_API_KEY: 'server-fixture', SCIENTIFIC_SHARED_GATEWAY_ENABLED: 'true' }, expected: 'server-fixture' },
  { label: 'personal configuration is preserved', env: { SCIENTIFIC_MODELS_API_KEY: 'server-fixture', SCIENTIFIC_SHARED_GATEWAY_ENABLED: 'true' }, personal: 'personal-fixture', expected: 'personal-fixture' },
  { label: 'missing shared credential remains unconfigured', env: { SCIENTIFIC_SHARED_GATEWAY_ENABLED: 'true' }, expected: undefined },
]) {
  test(scenario.label, async () => {
    const fixture = routeFixture(scenario.env, scenario.personal);
    const settings = await fixture.get('/settings');
    assert.equal(settings.configured, Boolean(scenario.expected));
    assert.ok(!JSON.stringify(settings).includes('fixture'));
    await fixture.get('/apps');
    assert.deepEqual(fixture.calls, [scenario.expected, scenario.expected]);
  });
}

for (const shared of [false, true]) {
  test(`MCP config uses ${shared ? 'server-managed' : 'personal'} workbench credential`, () => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'scientific-shared-registration-'));
    try {
      const root = path.resolve(__dirname, '..');
      const output = path.join(directory, 'config.json');
      const env = { ...process.env, SCIENTIFIC_MODELS_API_KEY: 'synthetic-secret-never-render',
        SCIENTIFIC_SHARED_GATEWAY_ENABLED: String(shared), SCIENTIFIC_DISCOVER_CHAT_MODELS: 'false',
        SCIENTIFIC_CORE_INSTRUCTIONS_PATH: path.join(root, 'agent-instructions.md') };
      delete env.NEBIUS_API_KEY;
      const child = spawnSync('node', [path.join(root, 'render-config.mjs'), output], { env, encoding: 'utf8' });
      assert.equal(child.status, 0, child.stderr);
      const raw = fs.readFileSync(output, 'utf8');
      const config = JSON.parse(raw).mcpServers['scientific-demos'];
      assert.equal(config.env.SCIENTIFIC_MODELS_API_KEY,
        shared ? '${SCIENTIFIC_MODELS_API_KEY}' : '{{SCIENTIFIC_MODELS_API_KEY}}');
      assert.equal(Boolean(config.customUserVars), !shared);
      assert.ok(!raw.includes('synthetic-secret-never-render'));
    } finally { fs.rmSync(directory, { recursive: true }); }
  });
}
