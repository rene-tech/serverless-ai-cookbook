const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
let root;
const setup = (async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-report-preview-'));
  process.env.SCIENTIFIC_WORKSPACE = root;
  return require('./service.cjs');
})();
after(async () => { await setup; await fs.rm(root, { recursive: true, force: true }); });

test('preview reads saved workspace bytes only and rejects oversized or escaped paths', async () => {
  const service = await setup;
  const source = Buffer.from('<html><h1>Recorded scientific report</h1></html>');
  const target = path.join(root, 'report.html');
  await fs.writeFile(target, source);
  assert.deepEqual(await service.workspacePreview('qa-fixture-key', 'report.html'), source);
  assert.deepEqual(await fs.readFile(target), source);
  await assert.rejects(service.workspacePreview('qa-fixture-key', '../report.html'), /escape/);
  await fs.writeFile(path.join(root, 'large.html'), Buffer.alloc(8 * 1024 * 1024 + 1));
  await assert.rejects(service.workspacePreview('qa-fixture-key', 'large.html'), (error) => error.status === 413);
  assert.equal((await service.workspaceGet('qa-fixture-key', 'large.html')).size_bytes, 8 * 1024 * 1024 + 1,
    'preview limit does not prevent original download');
});

test('pinned Markdown link patch is additive and idempotent and refuses unknown seams', async () => {
  await setup;
  const client = path.join(root, 'client');
  const file = path.join(client, 'src/components/Chat/Messages/Content/MarkdownComponents.tsx');
  const blocksFile = path.join(client, 'src/components/Chat/Messages/Content/MarkdownBlocks.tsx');
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, 'const prior = "preserve";\n  if (!file_id || !filename) {\n    return <a href={href}>{children}</a>;\n  }\n');
  await fs.writeFile(blocksFile, '<Markdown rehypePlugins={blockRehypePlugins} />');
  const patch = path.resolve(__dirname, '../patch-report-preview.mjs');
  execFileSync(process.execPath, [patch, client]);
  const once = await fs.readFile(file, 'utf8');
  assert.match(once, /workspaceReportPath\(href\)/);
  assert.match(once, /WorkspaceReportPreview href=\{href\}/);
  assert.match(once, /const prior = "preserve"/);
  const blocksOnce = await fs.readFile(blocksFile, 'utf8');
  assert.match(blocksOnce, /rehypePlugins=\{\[\.\.\.blockRehypePlugins, workspaceMarkdownLinks\]\}/);
  execFileSync(process.execPath, [patch, client]);
  assert.equal(await fs.readFile(file, 'utf8'), once);
  assert.equal(await fs.readFile(blocksFile, 'utf8'), blocksOnce);
  await fs.writeFile(file, 'unsupported source');
  assert.throws(() => execFileSync(process.execPath, [patch, client], { stdio: 'pipe' }), /failed/i);
  assert.equal(await fs.readFile(file, 'utf8'), 'unsupported source');
});

test('preview transport is authenticated plain text rather than same-origin HTML execution', async () => {
  const source = await fs.readFile(path.join(__dirname, 'router.cjs'), 'utf8');
  assert.ok(source.indexOf('router.use(requireJwtAuth)') < source.indexOf("router.get('/workspace/preview'"));
  assert.match(source, /workspacePreview\(await key\(req\), req\.query\.path/);
  assert.match(source, /res\.set\('X-Content-Type-Options', 'nosniff'\)\.type\('text\/plain; charset=utf-8'\)/);
});
