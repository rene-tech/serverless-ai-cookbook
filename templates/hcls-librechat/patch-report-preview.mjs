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
