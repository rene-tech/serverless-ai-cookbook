const test = require('node:test');
const assert = require('node:assert/strict');
const { patchFactory, patchDiscoveries, ROUTING_NOTICE } = require('./scientific-tool-search-patch.cjs');

const fixture = `
const toolsListSection = \`Deferred tools (search to load; \\u2026 = has params, search first):\`;
const serverFilters = normalizeServerFilter(rawServerFilter);
const hasServerFilter = serverFilters.length > 0;
if (toolRegistry == null) return [];
`;

test('blocks only an empty scientific-ai-apps server enumeration', () => {
  const patched = patchFactory(fixture);
  assert.match(patched, /query\.trim\(\) === ""/);
  assert.match(patched, /serverFilters\.includes\("scientific-ai-apps"\)/);
  assert.match(patched, /scientific_catalog_listing_disabled: true/);
  assert.ok(patched.includes(ROUTING_NOTICE));
  assert.equal(patchFactory(patched), patched);
});

test('rejects an unknown pinned ToolSearch build', () => {
  assert.throws(() => patchFactory('const hasServerFilter = true;'), /Unsupported pinned/);
});

const discoveryFixture = `function extractToolDiscoveries(messages) {
  return messages.at(-1);
}
function hasToolSearchInCurrentTurn(messages) {
  return messages.at(-1);
}
`;

for (const format of ['cjs', 'esm']) test(`patches both ${format} discovery views, not provider history`, () => {
  const result = patchDiscoveries(discoveryFixture, format);
  assert.equal(result.match(/isHostBudgetNotice\(messages\.at\(-1\)\)/g).length, 2);
  assert.equal(result.match(/messages = messages\.slice\(0, -1\)/g).length, 2);
  assert.ok(result.includes("'/opt/hcls-librechat/scientific-study-admission.cjs'"));
  assert.match(result, format === 'esm' ? /^import / : /^const .*require\(/);
  assert.throws(() => patchDiscoveries(result, format), /already installed/);
});

test('discovery patch refuses missing, duplicate or unknown module seams', () => {
  assert.throws(() => patchDiscoveries('upstream changed'), /Unsupported pinned/);
  assert.throws(() => patchDiscoveries(discoveryFixture + discoveryFixture), /Unsupported pinned/);
  assert.throws(() => patchDiscoveries(discoveryFixture, 'other'), /module format/);
});

test('image integration patches both pinned module variants without changing tool search', () => {
  const source = require('node:fs').readFileSync(require('node:path').join(__dirname, 'patch-server.mjs'), 'utf8');
  assert.match(source, /dist\/cjs\/messages\/tools\.cjs', 'cjs'/);
  assert.match(source, /dist\/esm\/messages\/tools\.mjs', 'esm'/);
  assert.match(source, /toolSearchPatch\.patchDiscoveries/);
  assert.match(source, /toolSearchPatch\.patchFactory/);
});
