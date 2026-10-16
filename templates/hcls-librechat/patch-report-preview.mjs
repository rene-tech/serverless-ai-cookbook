import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

// Additive and idempotent over the currently pinned Markdown renderer. Never
// replay the broader patch-client mutations against an already running client.
const root = process.argv[2] || '/app/client';
const filename = path.join(root, 'src/components/Chat/Messages/Content/MarkdownComponents.tsx');
let source = await readFile(filename, 'utf8');
const importLine = "import WorkspaceReportPreview, { workspaceReportPath } from '~/components/WorkspaceReportPreview';";
const anchor = '  if (!file_id || !filename) {';
const inserted = `  if (workspaceReportPath(href)) {
    return <WorkspaceReportPreview href={href}>{children}</WorkspaceReportPreview>;
  }

`;
if (!source.includes(importLine)) {
  if (source.split(anchor).length !== 2) throw new Error('Unsupported MarkdownAnchor report-preview seam');
  source = importLine + '\n' + source.replace(anchor, inserted + anchor);
  await writeFile(filename, source);
} else if (!source.includes(inserted)) {
  throw new Error('Report-preview import exists without its guarded renderer seam');
}

// Rehype runs before react-markdown strips unsupported schemes. An anchor-only
// fix is too late: sandbox:/workspace links have already become href="".
const blocksFile = path.join(root, 'src/components/Chat/Messages/Content/MarkdownBlocks.tsx');
let blocks = await readFile(blocksFile, 'utf8');
const pluginImport = "import workspaceMarkdownLinks from '~/components/WorkspaceMarkdownLinks';";
const pluginBefore = 'rehypePlugins={blockRehypePlugins}';
const pluginAfter = 'rehypePlugins={[...blockRehypePlugins, workspaceMarkdownLinks]}';
if (!blocks.includes(pluginImport)) {
  if (blocks.split(pluginBefore).length !== 2) throw new Error('Unsupported MarkdownBlocks URL-normalization seam');
  blocks = pluginImport + '\n' + blocks.replace(pluginBefore, pluginAfter);
  await writeFile(blocksFile, blocks);
} else if (!blocks.includes(pluginAfter)) {
  throw new Error('Workspace Markdown plugin imported without its renderer seam');
}
