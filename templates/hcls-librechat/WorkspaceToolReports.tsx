import { useMemo } from 'react';
import type { ReactNode } from 'react';
import WorkspaceReportPreview, { WorkspaceToolReportPaths, workspaceReportPath } from './WorkspaceReportPreview';

type Report = { path: string; href: string; label: string };
const record = (value: unknown): Record<string, unknown> | undefined =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : undefined;

/** Current tool output can be flattened text or serialized MCP content blocks. */
function outputTexts(output: string): string[] {
  let value: unknown;
  try { value = JSON.parse(output); } catch { return [output]; }
  const result = record(value);
  if (result?.isError === true) return [];
  const blocks = Array.isArray(value) ? value : result?.content;
  return Array.isArray(blocks) ? blocks.flatMap((block) => {
    const item = record(block);
    return item?.type === 'text' && typeof item.text === 'string' ? [item.text] : [];
  }) : [];
}

/** Read only completed viewer results, never assistant prose or unverified arguments. */
export function workspaceToolReports(content: readonly unknown[] | undefined): Report[] {
  const reports = new Map<string, Report>();
  for (const part of content ?? []) {
    const entry = record(part);
    if (entry?.type !== 'tool_call') continue;
    const call = record(entry.tool_call);
    if (typeof call?.name !== 'string' || !(call.name === 'visualize_workspace_media'
      || call.name.startsWith('visualize_workspace_media_mcp_'))) continue;
    if (call.runStepStatus !== 'completed' && !(call.runStepStatus == null && call.progress === 1)) continue;
    if (typeof call.output !== 'string') continue;
    for (const text of outputTexts(call.output)) {
      for (const match of text.matchAll(/\[((?:\\.|[^\]\\])*)\]\(([^)\s]+)\)/gu)) {
        const [, label, href] = match;
        const path = workspaceReportPath(href);
        if (path && /\.html?$/iu.test(path) && !reports.has(path)) {
          reports.set(path, { path, href, label: label.replace(/\\([\\[\]])/gu, '$1') || 'Scientific report' });
        }
      }
    }
  }
  return [...reports.values()];
}

/** Outside tool/activity disclosures: visible during streaming and saved-chat reopening. */
export default function WorkspaceToolReports({ content, enabled, children }: {
  content: readonly unknown[] | undefined; enabled: boolean; children: ReactNode;
}) {
  const reports = useMemo(() => enabled ? workspaceToolReports(content) : [], [content, enabled]);
  const paths = useMemo(() => new Set(reports.map(report => report.path)), [reports]);
  return <WorkspaceToolReportPaths.Provider value={paths}>
    {children}
    {reports.length > 0 && <div className="w-full min-w-0" aria-label="Verified workspace reports">
      {reports.map(report => <WorkspaceReportPreview key={report.path} href={report.href} fromTool>
        {report.label}
      </WorkspaceReportPreview>)}
    </div>}
  </WorkspaceToolReportPaths.Provider>;
}
