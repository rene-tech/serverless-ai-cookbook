import assert from 'node:assert/strict';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const workspaceTitle = 'Nebius Scientific AI Workspace';
const defaultAssets = join(dirname(fileURLToPath(import.meta.url)), 'assets');
const theme = `<style id="nebius-scientific-theme">
  /* The brand accent is confined to the shell; workflow surfaces use LibreChat theme roles. */
  #root { border-top: 3px solid #E0FF4F; }
  .nebius-wordmark { width: 92px; height: auto; flex-shrink: 0; }
  #nebius-scientific-workbench { flex: 0 0 auto; }
</style>`;

// Source mode brands Vite's public directory AND input HTML. A later rebuild
// must not recover LibreChat's stock public/logo.svg or its page title.
export async function brandClient(clientDir, assetsDir = defaultAssets, source = false) {
  const assetTarget = join(clientDir, source ? 'public/assets' : 'assets');
  const path = join(clientDir, 'index.html');
  let index = await readFile(path, 'utf8');
  assert.match(index, /<title>[\s\S]*?<\/title>/, 'Missing HTML title');
  assert.ok(index.includes('</head>'), 'Missing HTML head');
  index = index.replace(/<title>[\s\S]*?<\/title>/, `<title>${workspaceTitle}</title>`);
  index = index.replace(/<style id="nebius-scientific-theme">[\s\S]*?<\/style>\s*/g, '');
  index = index.replace('</head>', `${theme}</head>`);
  await mkdir(assetTarget, { recursive: true });
  for (const [from, to] of [
    ['nebius-logo.svg', 'nebius-logo.svg'],
    ['nebius-logo.svg', 'logo.svg'], // Upstream auth/loading compatibility.
    ['token-factory.svg', 'token-factory.svg'],
  ]) await copyFile(join(assetsDir, from), join(assetTarget, to));
  await writeFile(path, index);
  await verifyBranding(clientDir, assetsDir, source);
}

export async function verifyBranding(clientDir, assetsDir = defaultAssets, source = false) {
  const index = await readFile(join(clientDir, 'index.html'), 'utf8');
  assert.ok(index.includes(`<title>${workspaceTitle}</title>`), 'Workspace title regressed');
  assert.equal(index.split('id="nebius-scientific-theme"').length - 1, 1, 'Brand theme missing/duplicated');
  const assetTarget = join(clientDir, source ? 'public/assets' : 'assets');
  const logo = await readFile(join(assetsDir, 'nebius-logo.svg'));
  for (const name of ['logo.svg', 'nebius-logo.svg']) {
    assert.deepEqual(await readFile(join(assetTarget, name)), logo, `Wrong Nebius artwork: ${name}`);
  }
  assert.deepEqual(await readFile(join(assetTarget, 'token-factory.svg')),
    await readFile(join(assetsDir, 'token-factory.svg')), 'Token Factory artwork regressed');
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [clientDir, assetsDir = defaultAssets, ...options] = process.argv.slice(2);
  if (!clientDir) throw new Error('Expected client directory, optional asset directory and --source/--verify');
  if (options.includes('--verify')) await verifyBranding(clientDir, assetsDir, options.includes('--source'));
  else await brandClient(clientDir, assetsDir, options.includes('--source'));
}
