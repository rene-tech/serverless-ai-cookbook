import { readFile, writeFile } from 'node:fs/promises';

const file = process.argv[2] || '/app/api/server/index.js';
const anchor = "  app.get('/index.html', sendIndexHtml);";
const addition = "  app.use(require('/opt/hcls-librechat/scientific-client-assets.cjs').freshClientAssets(appConfig.paths.dist));\n";
const source = await readFile(file, 'utf8');
if (!source.includes(addition)) {
  if (source.split(anchor).length !== 2) throw new Error('Unsupported client shell registration');
  await writeFile(file, source.replace(anchor, addition + anchor));
}
