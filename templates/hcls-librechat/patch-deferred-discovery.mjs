// Additive image build only: do not replay patch-server or replace base config.
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import toolSearchPatch from './scientific-tool-search-patch.cjs';

export async function patchDeferredDiscovery(appRoot = '/app') {
  const targets = [
    ['node_modules/@librechat/agents/dist/cjs/messages/tools.cjs', 'cjs'],
    ['node_modules/@librechat/agents/dist/esm/messages/tools.mjs', 'esm'],
  ];
  // Validate both pinned seams before writing either file. Unknown/previously
  // patched SDKs fail the build; never pretend an arbitrary base is compatible.
  const edits = await Promise.all(targets.map(async ([relative, format]) => {
    const path = resolve(appRoot, relative);
    return [path, toolSearchPatch.patchDiscoveries(await readFile(path, 'utf8'), format)];
  }));
  for (const [path, source] of edits) await writeFile(path, source);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.length !== 2) throw new Error('This build patch accepts no arguments');
  await patchDeferredDiscovery();
}
