import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const client = process.argv[2] || '/app/client';
const headerPath = join(client, 'src/components/Chat/Header.tsx');
let header = await readFile(headerPath, 'utf8');
if (!header.includes('data-testid="nebius-workspace-brand"')) {
  const anchor = '        {parentConversationId != null && (';
  if (header.split(anchor).length !== 2) throw new Error('Unsupported chat header; branding anchor missing');
  header = header.replace(anchor, `        <div data-testid="nebius-workspace-brand" className="flex shrink-0 items-center gap-2 border-r border-border-light pr-2" aria-label="Nebius Scientific AI Workspace">
          <img src="/assets/nebius-logo.svg" alt="Nebius" width="76" height="21" className="h-auto w-16 sm:w-[76px]" />
          <span className="hidden text-xs font-medium text-text-secondary xl:inline">Scientific AI Workspace</span>
        </div>
${anchor}`);
}
const headerFade = 'bg-gradient-to-b from-presentation via-presentation/70 to-transparent';
const desktopFade = ' md:from-presentation/80 md:via-presentation/50 2xl:from-presentation/0 2xl:via-transparent';
if (!header.includes('gap-2 bg-presentation p-2')) {
  if (!header.includes(headerFade) || !header.includes(desktopFade)) throw new Error('Unsupported chat header background');
  header = header.replace(headerFade, 'bg-presentation').replace(desktopFade, '');
}
await writeFile(headerPath, header);
const authPath = join(client, 'src/components/Auth/AuthLayout.tsx');
let auth = await readFile(authPath, 'utf8');
if (!auth.includes('src="/assets/nebius-logo.svg"')) {
  if (!auth.includes('src="assets/logo.svg"')) throw new Error('Unsupported authentication logo');
  auth = auth.replace('src="assets/logo.svg"', 'src="/assets/nebius-logo.svg"');
  await writeFile(authPath, auth);
}
