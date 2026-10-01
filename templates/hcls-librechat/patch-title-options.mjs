import { readFile, writeFile } from 'node:fs/promises';
const path = '/app/api/server/controllers/agents/client.js';
const before = 'const titleResult = await this.run.generateTitle({\n        provider,\n        clientOptions,';
const after = "const titleResult = await this.run.generateTitle({\n        provider,\n        clientOptions: require('/opt/hcls-librechat/scientific-title-options.cjs')(clientOptions, endpoint),";
const source = await readFile(path, 'utf8');
if (source.includes(after)) throw new Error('Title options already patched; do not stack release patches');
if (source.split(before).length !== 2) throw new Error('Unsupported pinned title client');
await writeFile(path, source.replace(before, after));
