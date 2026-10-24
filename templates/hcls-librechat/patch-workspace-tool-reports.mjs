import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

// One message-wide owner keeps previews outside tool/activity folds and
// deduplicates an optional Markdown relay without altering the saved transcript.
const root = process.argv[2] || '/app/client';
const target = path.join(root, 'src/components/Chat/Messages/Content/ContentParts.tsx');
let source = await readFile(target, 'utf8');
const importLine = "import WorkspaceToolReports from '~/components/WorkspaceToolReports';";
const before = '      <ContentPartsBody {...props} />';
const after = `      <WorkspaceToolReports content={props.content} enabled={!props.isCreatedByUser && !props.edit}>
        <ContentPartsBody {...props} />
      </WorkspaceToolReports>`;
if (!source.includes(importLine)) {
  if (source.split(before).length !== 2) throw new Error('Unsupported message-wide tool-report seam');
  source = importLine + '\n' + source.replace(before, after);
} else if (!source.includes(after)) {
  throw new Error('Tool-report import exists without its message-wide renderer seam');
}
for (const name of ['WorkspaceToolReports.tsx', 'WorkspaceReportPreview.tsx']) {
  await writeFile(path.join(root, 'src/components', name), await readFile(new URL('./' + name, import.meta.url)));
}
await writeFile(target, source);
