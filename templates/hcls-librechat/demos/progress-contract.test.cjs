const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const originalFetch = global.fetch;
let root;
const setup = (async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-progress-contract-'));
  process.env.SCIENTIFIC_DEMOS_DIR = root;
  return require('./service.cjs');
})();
after(async () => { global.fetch = originalFetch; await setup; await fs.rm(root, { recursive: true, force: true }); });

const progress = { schema: 'scientific-ai/progress/v1', available: true, stale: false,
  updated_at: '2026-10-16T12:00:00Z', stale_after_seconds: 120,
  steps: [{ step_id: 'production', state: 'running', unit: 'ns', completed_units: 2.5,
    durable_completed_units: 2, target_units: 10, rate: 210, rate_unit: 'ns/day', gpu_count: 8,
    native_job_id: 'private-native-job', runtime: { image: 'private-image' } }], gpu_type: 'private-device' };
const operation = (id) => ({ id, model_id: 'gromacs', protocol: 'scientific-batch-v1', status: 'running',
  attempt: 2, progress, native_job_id: 'private-native-job', gpu_count: 8, gpu_type: 'private-device',
  placement: { pool: 'private-pool', node: 'private-node' }, runtime_image: 'private-image' });

test('status allowlist preserves scientific progress and strips execution implementation', async () => {
  const service = await setup;
  const safe = service.customerOperation(operation(crypto.randomUUID()));
  assert.equal(safe.progress.steps[0].completed_units, 2.5);
  assert.equal(safe.progress.steps[0].durable_completed_units, 2);
  assert.equal(safe.progress.steps[0].rate, 210);
  assert.equal(safe.attempt, 2);
  assert.doesNotMatch(JSON.stringify(safe), /private-|gpu_count|gpu_type|runtime|placement|native_job_id/);
  const catalog = service.customerCatalogItem({ id: 'gromacs', gpu_count: 8, gpu_class: 'private-device',
    runtime: { image: 'private-image' }, capabilities: ['run-workflow'], license: 'GPL' });
  assert.deepEqual(catalog, { id: 'gromacs', capabilities: ['run-workflow'], license: 'GPL' });
});

test('actual tracking consumes top-level progress and saves only customer status', async () => {
  const service = await setup;
  const id = crypto.randomUUID();
  global.fetch = async () => new Response(JSON.stringify({ operation: { ...operation(id), progress: undefined },
    progress, batch: { status: 'running', result_published: false, native_job_id: 'private-native-job' } }));
  const result = await service.track('qa-user', 'qa-only-fixture', id);
  assert.equal(result.operation.progress.steps[0].rate, 210);
  assert.deepEqual(result.batch, { status: 'running', result_published: false });
  assert.doesNotMatch(JSON.stringify(result), /private-|gpu_count|native_job_id/);
});

test('older cached terminal rows are projected when backend history is unavailable', async () => {
  const service = await setup;
  const id = crypto.randomUUID();
  const hash = (value) => crypto.createHash('sha256').update(value).digest('hex');
  const folder = path.join(root, 'workbench', hash('old-client'), 'runs', hash('fixture-key'));
  await fs.mkdir(folder, { recursive: true });
  await fs.writeFile(path.join(folder, id + '.json'), JSON.stringify({ id, status: 'succeeded',
    updated_at: new Date().toISOString(), operation: { ...operation(id), status: 'succeeded' } }));
  global.fetch = async () => new Response('{}', { status: 404 });
  const result = await service.runs('old-client', 'fixture-key');
  assert.equal(result.data.length, 1);
  assert.equal(result.data[0].operation.progress.steps[0].completed_units, 2.5);
  assert.doesNotMatch(JSON.stringify(result), /private-|gpu_count|native_job_id/);
});

test('MCP status help names measured units and checkpoint distinction, not fabricated throughput', () => {
  const tool = require('./mcp.cjs').tools.find((item) => item.name === 'workbench_get_operation');
  assert.match(tool.description, /completed ns and ns\/day/);
  assert.match(tool.description, /durably checkpointed/);
  assert.match(tool.description, /stale\/unknown/);
  assert.match(tool.description, /never estimate speed/);
});

test('real progress card renders measured units, uncertainty and checkpoint distinction without hardware', async () => {
  const ts = require(process.env.TYPESCRIPT_MODULE || 'typescript');
  const vm = require('node:vm');
  const compile = async (filename) => ts.transpileModule(await fs.readFile(path.join(__dirname, filename), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const display = { exports: {} };
  vm.runInNewContext(await compile('run-display.ts'), { module: display, exports: display.exports });
  const jsx = (type, props) => typeof type === 'function' ? type(props) : { type, props };
  const components = { exports: {} };
  const dependencies = { 'react/jsx-runtime': { jsx, jsxs: jsx, Fragment: 'fragment' },
    './scientific-run-display': display.exports };
  vm.runInNewContext(await compile('Demos.tsx'), { module: components, exports: components.exports,
    require: (name) => dependencies[name] || {} });
  const node = components.exports.ScientificProgressView({ progress });
  const rendered = JSON.stringify(node);
  assert.match(rendered, /Completed:/); assert.match(rendered, /2\.5 ns/);
  assert.match(rendered, /Durably checkpointed:/); assert.match(rendered, /2 ns/);
  assert.match(rendered, /210 ns\/day/); assert.doesNotMatch(rendered, /private-|gpu_count|native_job_id/);
  const unknown = components.exports.ScientificProgressView({ progress: { ...progress, available: false, updated_at: null,
    steps: [{ step_id: 'predict', state: 'running', unit: 'structures', completed_units: null, rate: null }] } });
  const text = JSON.stringify(unknown);
  assert.match(text, /Unknown does not mean zero/); assert.match(text, /Observation freshness unknown/);
  assert.match(text, /Measured rate \(freshness unknown\)/);
});
