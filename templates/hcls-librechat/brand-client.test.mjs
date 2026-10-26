import assert from 'node:assert/strict';
import { cp, mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { brandClient, verifyBranding, workspaceTitle } from './brand-client.mjs';

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), 'scientific-branding-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(join(root, 'index.html'), '<html><head><title>LibreChat</title></head><body></body></html>');
  return root;
}

test('restores exact artwork, title and theme; applying twice is idempotent', async (t) => {
  const root = await fixture(t);
  await brandClient(root);
  const first = await readFile(join(root, 'index.html'), 'utf8');
  await brandClient(root);
  assert.equal(await readFile(join(root, 'index.html'), 'utf8'), first);
  assert.ok(first.includes(workspaceTitle));
  await verifyBranding(root);
});

test('source branding survives Vite-style public asset copy and HTML rebuild', async (t) => {
  const root = await fixture(t);
  await brandClient(root, undefined, true);
  const dist = join(root, 'dist');
  await mkdir(dist);
  await cp(join(root, 'public'), dist, { recursive: true });
  await cp(join(root, 'index.html'), join(dist, 'index.html'));
  await verifyBranding(dist);
});

test('verification rejects upstream logo overwrite, not only a missing image', async (t) => {
  const root = await fixture(t);
  await brandClient(root);
  await writeFile(join(root, 'assets/logo.svg'), '<svg>stock LibreChat feather</svg>');
  await assert.rejects(verifyBranding(root), /Wrong Nebius artwork/);
});

test('verification rejects lost theme and title', async (t) => {
  const root = await fixture(t);
  await brandClient(root);
  await writeFile(join(root, 'index.html'), '<title>LibreChat</title>');
  await assert.rejects(verifyBranding(root), /Workspace title regressed/);
});

test('verification rejects a retained theme marker with lost or stale foreground rules', async (t) => {
  const root = await fixture(t);
  await brandClient(root);
  const index = await readFile(join(root, 'index.html'), 'utf8');
  for (const broken of [
    index.replace(/<style id="nebius-scientific-theme">[\s\S]*?<\/style>/,
      '<style id="nebius-scientific-theme"></style>'),
    index.replace('body { color: rgb(var(--text-primary)); }', 'body { color: black; }'),
    index.replace('--tw-prose-code: rgb(var(--text-primary));', '--tw-prose-code: #111827;'),
  ]) {
    await writeFile(join(root, 'index.html'), broken);
    await assert.rejects(verifyBranding(root), /Scientific theme rules regressed/);
  }
});
