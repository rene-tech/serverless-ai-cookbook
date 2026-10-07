/* Wire-level discovery regressions: no customer credentials or model execution. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { spawn } = require('node:child_process');
const path = require('node:path');

const native = [
  ['boltz2', 'predict'], ['diffdock', 'dock'], ['msa-search-pdb70', 'search-msa'],
  ['openfold2', 'predict-structure'], ['openfold3', 'predict-structure'],
  ['proteinmpnn', 'design-protein'], ['scvi-scanvi', 'fit-transform'],
].map(([id, operation]) => ({ id, operations: [operation], protocols: ['native'] }));
const batch = [
  ['boltzgen', 'design-binders'], ['esmfold2', 'predict-structure'],
  ['esmfold2-fast', 'predict-protein-structure'], ['gromacs', 'run-workflow'],
  ['gromacs-mpi', 'run-workflow'], ['lammps', 'run-workflow'], ['namd', 'run-workflow'],
  ['openfold3-openbind', 'predict-complex-structure'], ['rfdiffusion', 'design-backbone'],
  ['scvi-scanvi', 'fit-transform'],
].map(([model_id, operation]) => ({ model_id, operations: [operation] }));
const ids = [...new Set([...native.map(x => x.id), ...batch.map(x => x.model_id)])].sort();

async function rpc(t, requests, options = {}) {
  const calls = [];
  const server = http.createServer((req, res) => {
    calls.push({ method: req.method, path: req.url, authorization: req.headers.authorization });
    if (options.status) { res.writeHead(options.status); res.end(JSON.stringify({ detail: 'fixture unavailable' })); return; }
    let data = req.url === '/v1/models' ? native : batch;
    if (options.grants) data = data.filter(x => options.grants.includes(x.id || x.model_id));
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(options.malformed && req.url === '/v1/scientific-models' ? {} : { data }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const child = spawn(process.execPath, [path.join(__dirname, 'mcp.cjs')], { env: {
    ...process.env, LIBRECHAT_USER_ID: 'catalog-regression-fixture',
    SCIENTIFIC_MODELS_API_KEY: 'fixture-scoped-key',
    SCIENTIFIC_MODELS_API_BASE_URL: `http://127.0.0.1:${server.address().port}/v1`,
  } });
  let stdout = '', stderr = '';
  child.stdout.on('data', x => stdout += x);
  child.stderr.on('data', x => stderr += x);
  child.stdin.end(requests.map((x, i) => JSON.stringify({ jsonrpc: '2.0', id: i + 1, ...x })).join('\n') + '\n');
  const code = await new Promise((resolve, reject) => { child.on('exit', resolve); child.on('error', reject); });
  assert.equal(code, 0, stderr);
  assert.ok(calls.every(x => x.method === 'GET' && ['/v1/models', '/v1/scientific-models'].includes(x.path)));
  assert.ok(calls.every(x => x.authorization === 'Bearer fixture-scoped-key'));
  return stdout.trim().split('\n').map(JSON.parse);
}
const invoke = (name, args = {}) => ({ method: 'tools/call', params: { name, arguments: args } });
const value = result => JSON.parse(result.result.content[0].text);

test('full listing cannot be filtered by old chat/tool-cache arguments', async t => {
  const requests = [{ method: 'tools/list' }, ...[
    {}, { query: 'all' }, { query: 'protein' },
    { query: 'molecular and protein candidate design and ranking' },
    { query: 'DNA genomics sequence' }, { query: 'DiffDock docking ligand' },
  ].map(args => invoke('workbench_list_apps', args))];
  const results = await rpc(t, requests);
  const tools = results.shift().result.tools;
  assert.deepEqual(tools.find(x => x.name === 'workbench_list_apps').inputSchema.properties, {});
  assert.deepEqual(tools.find(x => x.name === 'workbench_search_apps').inputSchema.required, ['query']);
  for (const result of results) {
    assert.equal(result.result.isError, false);
    const catalog = value(result);
    assert.deepEqual(catalog.data.map(x => x.model_id).sort(), ids);
    assert.equal(catalog.count, 16);
    assert.equal(catalog.total_authorized_count, 16);
    assert.equal(catalog.catalog_scope, 'full_authorized_catalog');
    assert.equal(catalog.filter_applied, null);
    assert.deepEqual(catalog.data.find(x => x.model_id === 'scvi-scanvi').contract_kinds, ['native', 'scientific-batch']);
    assert.equal(catalog.groups.flatMap(x => x.apps).length, 16);
  }
});

test('explicit searches distinguish matches from grants, including genuine misses', async t => {
  const results = await rpc(t, ['protein', 'molecular dynamics', 'single-cell', 'DiffDock docking ligand', 'missing']
    .map(query => invoke('workbench_search_apps', { query })));
  assert.deepEqual(results.map(x => value(x).count), [10, 4, 1, 0, 0]);
  for (const result of results) {
    const catalog = value(result);
    assert.equal(catalog.total_authorized_count, 16);
    assert.equal(catalog.catalog_scope, 'search_matches');
    assert.match(catalog.answer_rules, /NOT the full authorization list/);
    assert.match(catalog.next_step, /workbench_list_apps with \{\}/);
  }
  const missing = await rpc(t, [invoke('workbench_search_apps'), invoke('workbench_search_apps', { query: ' ' })]);
  assert.ok(missing.every(x => x.result.isError));
});

test('scoped and empty catalogs never broaden grants or borrow another caller catalog', async t => {
  for (const grants of [['scvi-scanvi', 'gromacs'], []]) {
    const [result] = await rpc(t, [invoke('workbench_list_apps')], { grants });
    assert.equal(result.result.isError, false);
    assert.deepEqual(value(result).data.map(x => x.model_id).sort(), [...grants].sort());
    assert.equal(value(result).total_authorized_count, grants.length);
  }
});

test('unreadable, unauthorized or partially malformed catalogs fail, never become empty success', async t => {
  for (const options of [{ status: 401 }, { status: 503 }, { malformed: true }]) {
    const [result] = await rpc(t, [invoke('workbench_list_apps')], options);
    assert.equal(result.result.isError, true);
    assert.equal(value(result).count, undefined);
  }
});
