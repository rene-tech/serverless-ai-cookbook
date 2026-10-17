import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const file = path.join(process.argv[2] || '/app/client', 'src/App.jsx');
const imported = "import ScientificClientUpdate from '~/components/ScientificClientUpdate';";
const anchor = '                  <WakeLockManager />';
let source = await readFile(file, 'utf8');
if (!source.includes(imported)) {
  if (source.split(anchor).length !== 2) throw new Error('Unsupported client App update seam');
  source = imported + '\n' + source.replace(anchor, '                  <ScientificClientUpdate />\n' + anchor);
  await writeFile(file, source);
} else if (!source.includes('<ScientificClientUpdate />')) {
  throw new Error('Client update imported without its component');
}
