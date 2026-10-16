import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

// Caller options must not enable polling for the synthetic new-chat ID.
// The backend correctly returns 404 because that conversation does not exist.
const file = join(process.argv[2] || '/app/client', 'src/data-provider/Subagents/queries.ts');
let source = await readFile(file, 'utf8');
const marker = '// Never let caller options enable a synthetic conversation.';
if (!source.includes(marker)) {
  const boundary = source.indexOf('const isTerminal =');
  if (boundary < 0) throw new Error('Unsupported parent-subagent query source');
  let parent = source.slice(0, boundary);
  const guard = `      enabled:
        parentConversationId !== '' &&
        parentConversationId !== Constants.NEW_CONVO &&
        parentConversationId !== Constants.PENDING_CONVO,
`;
  if (parent.split(guard).length !== 2 || parent.split('      ...config,').length !== 2) {
    throw new Error('Parent-subagent query guard changed; inspect before patching');
  }
  parent = parent.replace(guard, '').replace('      ...config,', `      ...config,
      ${marker}
      enabled:
        config?.enabled !== false &&
        parentConversationId !== '' &&
        parentConversationId !== Constants.NEW_CONVO &&
        parentConversationId !== Constants.PENDING_CONVO,`);
  source = parent + source.slice(boundary);
  await writeFile(file, source);
}
