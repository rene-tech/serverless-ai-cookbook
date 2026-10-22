// Offline source/build wiring regressions. No Docker, provider or network calls.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { pathToFileURL } = require('node:url');
const { patchDiscoveries } = require('./scientific-tool-search-patch.cjs');
const entrypoint = import(pathToFileURL(path.join(__dirname, 'patch-deferred-discovery.mjs')));
const source = `function extractToolDiscoveries(messages) { return messages.at(-1); }
function hasToolSearchInCurrentTurn(messages) { return messages.at(-1); }
`;
const modules = [
  ['node_modules/@librechat/agents/dist/cjs/messages/tools.cjs', 'cjs'],
  ['node_modules/@librechat/agents/dist/esm/messages/tools.mjs', 'esm'],
];

async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'deferred-discovery-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  for (const [relative] of modules) {
    const filename = path.join(root, relative);
    await fs.mkdir(path.dirname(filename), { recursive: true });
    await fs.writeFile(filename, source);
  }
  await fs.writeFile(path.join(root, 'librechat.yaml'), 'preserved-base-config');
  return root;
}

test('additive entrypoint matches full-build transformation and leaves configuration untouched', async (t) => {
  const root = await fixture(t);
  const { patchDeferredDiscovery } = await entrypoint;
  await patchDeferredDiscovery(root);
  for (const [relative, format] of modules) {
    assert.equal(await fs.readFile(path.join(root, relative), 'utf8'), patchDiscoveries(source, format));
  }
  assert.equal(await fs.readFile(path.join(root, 'librechat.yaml'), 'utf8'), 'preserved-base-config');
  await assert.rejects(patchDeferredDiscovery(root), /already installed/);
});

for (const invalid of ['unknown', 'already-patched']) {
  test(`validates both SDK modules before writing when ESM is ${invalid}`, async (t) => {
    const root = await fixture(t);
    const { patchDeferredDiscovery } = await entrypoint;
    const esm = path.join(root, modules[1][0]);
    const invalidSource = invalid === 'unknown' ? 'unsupported version' : patchDiscoveries(source, 'esm');
    await fs.writeFile(esm, invalidSource);
    await assert.rejects(patchDeferredDiscovery(root), /Unsupported pinned|already installed/);
    assert.equal(await fs.readFile(path.join(root, modules[0][0]), 'utf8'), source);
    assert.equal(await fs.readFile(esm, 'utf8'), invalidSource);
  });
}

test('full image applies existing patch-server and verifies actual installed modules', async () => {
  const full = await fs.readFile(path.join(__dirname, 'Dockerfile'), 'utf8');
  for (const file of ['scientific-study-admission.cjs', 'scientific-tool-search-patch.cjs', 'test-deferred-discovery-boundary.cjs']) {
    assert.ok(full.includes(`COPY templates/hcls-librechat/${file}`));
  }
  assert.ok(full.indexOf('RUN node /opt/hcls-librechat/patch-server.mjs') < full.indexOf('SCIENTIFIC_DISCOVERY_INSTALLED=1'));
  assert.match(full, /SCIENTIFIC_DISCOVERY_GRAPH=\/app\/node_modules\/\@librechat\/agents\/dist\/cjs\/graphs\/Graph\.cjs/);
  assert.match(full, /node --test \/opt\/hcls-librechat\/test-deferred-discovery-boundary\.cjs/);
});

test('additive image inherits the current qualified SDK instead of replaying historical patches', async () => {
  const dockerfile = await fs.readFile(path.join(__dirname, 'Dockerfile.default-release'), 'utf8');
  const release = await fs.readFile(path.join(__dirname, 'scripts/release-image.sh'), 'utf8');
  const digest = release.match(/^SCIENTIFIC_AI_RELEASE_DIGEST='(sha256:[a-f0-9]{64})'$/m)?.[1];
  assert.ok(digest, 'The current default must name an immutable image');
  assert.ok(dockerfile.split('\n').some(line => line.startsWith('ARG WORKBENCH_BASE=') && line.endsWith(`@${digest}`)));
  assert.doesNotMatch(dockerfile, /node \/opt\/hcls-librechat\/patch-deferred-discovery\.mjs/);
  assert.doesNotMatch(dockerfile, /node \/opt\/hcls-librechat\/patch-server\.mjs/);
  assert.equal(dockerfile.split('\n').filter(line => line.startsWith('FROM ')).length, 1);
  assert.match(dockerfile, /verify-observer-recovery\.py --source \/tmp\/client/);
});

test('build verification cannot silently skip the exact installed SDK', async () => {
  const gate = await fs.readFile(path.join(__dirname, 'test-deferred-discovery-boundary.cjs'), 'utf8');
  assert.match(gate, /if \(!installed && !process\.env\.SCIENTIFIC_DISCOVERY_GRAPH && !fs\.existsSync\(graphPath\)\)/);
  assert.match(gate, /installed ESM discovery matches the CJS behavior/);
  assert.match(gate, /exports\['\.\/messages'\]\.import\.default/);
  assert.match(gate, /fixture\(sdk\)/);
  assert.match(gate, /ESM rejects unrelated tool-call lineage/);
  assert.match(gate, /ESM does not scan through/);
  assert.match(gate, /actual ToolNode post-batch path/);
});
