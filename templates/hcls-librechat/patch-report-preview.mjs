import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

// Additive and idempotent over the currently pinned Markdown renderer. Never
// replay the broader patch-client mutations against an already running client.
const root = process.argv[2] || '/app/client';
const filename = path.join(root, 'src/components/Chat/Messages/Content/MarkdownComponents.tsx');
let source = await readFile(filename, 'utf8');
// Upgrade the pinned parent's build-time renderer seam; no UUID-link handler
// or alternate public protocol is retained in the generated application.
source = source.replaceAll('scientificStudyId', 'scientificWorkflowPath');
const importLine = "import WorkspaceReportPreview, { workspaceReportPath } from '~/components/WorkspaceReportPreview';";
const anchor = '  if (!file_id || !filename) {';
const legacyInserted = `  if (workspaceReportPath(href)) {
    return <WorkspaceReportPreview href={href}>{children}</WorkspaceReportPreview>;
  }

`;
const inserted = legacyInserted.replace('if (workspaceReportPath(href))', "if (!reportLinkOnly && workspaceReportPath(href))");
const oldSignature = 'function MarkdownAnchor({ href, children }: TAnchorProps)';
const newSignature = "function MarkdownAnchor({ href, children, 'data-scientific-report-link': reportLinkOnly }: TAnchorProps)";
if (source.includes(oldSignature)) {
  source = source.replace(oldSignature, newSignature)
    .replace('type TAnchorProps = {', "type TAnchorProps = {\n  'data-scientific-report-link'?: string;");
} else if (!source.includes(newSignature)) {
  throw new Error('Unsupported MarkdownAnchor link-only seam');
}
if (source.includes(legacyInserted)) source = source.replace(legacyInserted, inserted);
if (!source.includes(importLine)) {
  if (source.split(anchor).length !== 2) throw new Error('Unsupported MarkdownAnchor report-preview seam');
  source = importLine + '\n' + source.replace(anchor, inserted + anchor);
  await writeFile(filename, source);
} else if (!source.includes(inserted)) {
  throw new Error('Report-preview import exists without its guarded renderer seam');
}

const legacyStudyImport = "import ScientificStudyPreview, { scientificWorkflowPath } from '~/components/ScientificStudyPreview';";
const studyImport = "import ScientificStudyPreview, { scientificWorkflowPath, scientificOperationId } from '~/components/ScientificStudyPreview';";
source = source.replace(legacyStudyImport, studyImport)
  .replace('if (scientificWorkflowPath(href)) {', 'if (scientificWorkflowPath(href) || scientificOperationId(href)) {');
const studyInserted = `  if (scientificWorkflowPath(href) || scientificOperationId(href)) {
    return <ScientificStudyPreview href={href}>{children}</ScientificStudyPreview>;
  }

`;
if (!source.includes(studyImport)) {
  if (source.split(anchor).length !== 2) throw new Error('Unsupported study-preview anchor seam');
  source = studyImport + '\n' + source.replace(anchor, studyInserted + anchor);
  await writeFile(filename, source);
} else if (!source.includes(studyInserted)) {
  throw new Error('Study preview import exists without its renderer seam');
}
await writeFile(filename, source);
await writeFile(path.join(root, 'src/components/WorkspaceMarkdownLinks.ts'),
  await readFile(new URL('./WorkspaceMarkdownLinks.ts', import.meta.url)));
await writeFile(path.join(root, 'src/components/WorkspaceReportPreview.tsx'),
  await readFile(new URL('./WorkspaceReportPreview.tsx', import.meta.url)));

// Rehype runs before react-markdown strips unsupported schemes. An anchor-only
// fix is too late: sandbox:/workspace links have already become href="".
const blocksFile = path.join(root, 'src/components/Chat/Messages/Content/MarkdownBlocks.tsx');
let blocks = await readFile(blocksFile, 'utf8');
const artifactImport = "import { normalizeArtifactMarkdown } from '~/components/ScientificArtifactMarkdown';";
const artifactBefore = 'splitMarkdownIntoBlocks(content).map';
const artifactAfter = 'splitMarkdownIntoBlocks(normalizeArtifactMarkdown(content)).map';
await writeFile(path.join(root, 'src/components/ScientificArtifactMarkdown.ts'),
  await readFile(new URL('./ScientificArtifactMarkdown.ts', import.meta.url)));
if (!blocks.includes(artifactImport)) {
  if (blocks.split(artifactBefore).length !== 2) throw new Error('Unsupported artifact Markdown boundary seam');
  blocks = artifactImport + '\n' + blocks.replace(artifactBefore, artifactAfter);
} else if (!blocks.includes(artifactAfter)) {
  throw new Error('Artifact boundary normalizer imported without its parser seam');
}
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
await writeFile(blocksFile, blocks);
