import { readFile, writeFile } from 'node:fs/promises';
const path = '/app/client/src/components/Chat/Messages/Content/ToolCallInfo.tsx';
let source = await readFile(path, 'utf8');
for (const [before, after] of [
  ["import { OutputRenderer } from './ToolOutput';", "import ScientificExecutionOutput from './ScientificExecutionOutput';"],
  ['{output && <OutputRenderer text={output} />}', '<ScientificExecutionOutput input={input} output={output} />'],
]) {
  if (source.split(before).length !== 2) throw new Error('Unsupported pinned execution UI seam');
  source = source.replace(before, after);
}
await writeFile(path, source);
