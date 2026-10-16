import { useEffect, useState } from 'react';
import { request } from 'librechat-data-provider';
import { workspaceCodeHref } from './WorkspaceInlineCode';
import type { ReactNode } from 'react';

const PREVIEW_LIMIT = 8 * 1024 * 1024;
const MEDIA_TYPES: Record<string, string> = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
  gif: 'image/gif', webp: 'image/webp', mp4: 'video/mp4', webm: 'video/webm' };
function previewKind(path: string) {
  if (/\.html?$/iu.test(path)) return 'html';
  if (path.split('/').pop() === 'native-timing-report.json') return 'md-summary';
  const type = MEDIA_TYPES[path.split('.').pop()?.toLowerCase() || ''];
  return type?.startsWith('image/') ? 'image' : type?.startsWith('video/') ? 'video' : null;
}

/** Older live clients can adopt static UI assets without restarting their API. */
export async function readWorkspacePreview(path: string): Promise<Blob> {
  const controller = new AbortController();
  let exceeded = false;
  const options = { responseType: 'blob' as const, signal: controller.signal,
    onDownloadProgress: (event: { loaded: number }) => {
      if (event.loaded > PREVIEW_LIMIT + 1) { exceeded = true; controller.abort(); }
    } };
  const read = async (route: string, legacy = false) => {
    const response = await request.getResponse<Blob>(`/api/scientific-demos/workspace/${route}?path=${encodeURIComponent(path)}`,
      { ...options, ...(legacy ? { headers: { Range: `bytes=0-${PREVIEW_LIMIT}` } } : {}) });
    if (response.data.size > PREVIEW_LIMIT) throw new Error('preview_limit');
    return response.data;
  };
  try {
    try { return await read('preview'); }
    catch (problem) {
      // Never retry a permissions error or failed backend as another path.
      if ((problem as { response?: { status?: number } })?.response?.status !== 404) throw problem;
      return await read('file', true);
    }
  } catch (problem) {
    if (exceeded) throw new Error('preview_limit');
    throw problem;
  }
}

/** Reuse the existing authenticated workspace URL contract, never arbitrary URLs. */
export function workspaceReportPath(href: unknown): string | undefined {
  const validated = workspaceCodeHref(href);
  if (!validated) return undefined;
  const parsed = new URL(validated, 'https://workspace.invalid');
  const relative = (value: string) => value.replace(/^\/workspace(?:\/|$)/, '').replace(/^\/+/, '');
  const folder = relative(parsed.searchParams.get('path') || '');
  const file = relative(parsed.searchParams.get('file') || '');
  const target = file.includes('/') ? file : [folder, file].filter(Boolean).join('/');
  return previewKind(target) ? target : undefined;
}

/** Keep the report's interactive inline plots in an opaque, network-isolated frame. */
export function isolatedReportHtml(html: string): string {
  const policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    + "img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; "
    + "object-src 'none'; base-uri 'none'; form-action 'none'";
  return '<!doctype html><meta http-equiv="Content-Security-Policy" content="' + policy + '">' + html;
}

type PrecheckSummary = { status: string; verdict: string; counts: { fail?: number; warn?: number; info?: number } };
export function precheckSummary(value: unknown): PrecheckSummary | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  if (source.schema !== 'mdprecheck/check/v1' || typeof source.status !== 'string' || typeof source.verdict !== 'string') return null;
  const counts = source.counts && typeof source.counts === 'object' ? source.counts as Record<string, unknown> : {};
  return { status: source.status.toUpperCase(), verdict: source.verdict,
    counts: Object.fromEntries(['fail', 'warn', 'info'].filter((key) => Number.isSafeInteger(counts[key]) && (counts[key] as number) >= 0)
      .map((key) => [key, counts[key]])) };
}

type NativeMdSummary = { complete: boolean; rows: { step: string; engine: string; rate: number | null;
  executed: number | null; durable: number | null; requested: number | null; seconds: number | null }[] };
export function nativeMdSummary(value: unknown): NativeMdSummary | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  if (source.schema !== 'scientific-ai/native-md-timing-report/v1' || !Array.isArray(source.timing_rows)) return null;
  const number = (item: unknown) => typeof item === 'number' && Number.isFinite(item) && item >= 0 ? item : null;
  return { complete: source.complete === true, rows: source.timing_rows.filter((row) => row && typeof row === 'object')
    .map((row) => ({ step: typeof row.step_id === 'string' ? row.step_id : 'Unknown step',
      engine: typeof row.engine === 'string' ? row.engine : 'Unknown engine', rate: number(row.performance_ns_per_day),
      executed: number(row.executed_steps), durable: number(row.durably_completed_steps), requested: number(row.requested_steps),
      seconds: number(row.wall_seconds) })) };
}

export default function WorkspaceReportPreview({ href, children }: { href: string; children: ReactNode }) {
  const reportPath = workspaceReportPath(href);
  const [expanded, setExpanded] = useState(true);
  const [html, setHtml] = useState<string | null>(null);
  const [summary, setSummary] = useState<PrecheckSummary | null>(null);
  const [mdSummary, setMdSummary] = useState<NativeMdSummary | null>(null);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [error, setError] = useState('');
  const kind = reportPath ? previewKind(reportPath) : null;
  const jsonPath = reportPath?.endsWith('/report.html') || reportPath === 'report.html'
    ? reportPath.replace(/\.html$/u, '.json') : undefined;
  const fileUrl = (path: string) => `/api/scientific-demos/workspace/file?path=${encodeURIComponent(path)}`;
  const download = async (path: string) => {
    try {
      const response = await request.getResponse<Blob>(fileUrl(path), { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url; link.download = path.split('/').pop() || 'report'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError('Download unavailable. The original workspace link remains available.'); }
  };
  useEffect(() => {
    if (!reportPath || !expanded) return;
    let cancelled = false;
    let objectUrl: string | undefined;
    setHtml(null); setSummary(null); setMdSummary(null); setMediaUrl(null); setError('');
    void (async () => {
      try {
        const data = await readWorkspacePreview(reportPath);
        if (kind === 'image' || kind === 'video') {
          objectUrl = URL.createObjectURL(new Blob([data], {
            type: MEDIA_TYPES[reportPath.split('.').pop()?.toLowerCase() || ''] }));
          if (!cancelled) setMediaUrl(objectUrl);
          else URL.revokeObjectURL(objectUrl);
        } else {
          const content = await data.text();
          if (kind === 'html' && !cancelled) setHtml(isolatedReportHtml(content));
          if (kind === 'md-summary') {
            const parsed = nativeMdSummary(JSON.parse(content));
            if (!parsed) throw new Error('Unknown timing report schema');
            if (!cancelled) setMdSummary(parsed);
          }
        }
        if (jsonPath) {
          const metadata = await readWorkspacePreview(jsonPath);
          const parsed = precheckSummary(JSON.parse(await metadata.text()));
          if (!cancelled) setSummary(parsed);
        }
      } catch (problem) {
        if (!cancelled) setError(problem instanceof Error && problem.message === 'preview_limit'
          ? 'This report is too large for the inline preview. Download the complete original below.'
          : 'The complete report or summary could not be loaded. Use the original workspace file below.');
      }
    })();
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [reportPath, expanded, jsonPath, kind]);
  if (!reportPath) return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
  return <span className="my-3 block rounded-xl border border-border-medium p-3" role="group" aria-label="Scientific report preview">
    <span className="block font-semibold">{children || 'Scientific report'}</span>
    {summary && <span className="my-2 block" role="status">
      <strong>MD precheck: {summary.status}</strong> · {summary.verdict}
      <span className="block text-xs">Failures: {summary.counts.fail ?? 'unknown'} · Warnings: {summary.counts.warn ?? 'unknown'} · Information: {summary.counts.info ?? 'unknown'}</span>
    </span>}
    <span className="my-2 flex flex-wrap gap-3 text-sm">
      <button type="button" className="underline" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Collapse report' : 'View report here'}</button>
      <button type="button" className="underline" onClick={() => void download(reportPath)}>{kind === 'html' ? 'Download HTML' : 'Download original'}</button>
      {jsonPath && <button type="button" className="underline" onClick={() => void download(jsonPath)}>Download JSON</button>}
      <a href={href} target="_blank" rel="noopener noreferrer" className="underline">Workspace file</a>
    </span>
    {error && <span role="status" className="my-2 block text-sm">{error}</span>}
    {expanded && !html && !mediaUrl && !mdSummary && !error && <span role="status" className="block text-sm">Loading the saved result; no new model work is submitted.</span>}
    {expanded && html && <iframe title="Scientific report" srcDoc={html} sandbox="allow-scripts"
      referrerPolicy="no-referrer" className="block h-[640px] w-full resize-y rounded border border-border-light bg-white" />}
    {expanded && kind === 'image' && mediaUrl && <img src={mediaUrl} alt={reportPath.split('/').pop() || 'Scientific result'} className="block max-h-[640px] w-full object-contain" />}
    {expanded && kind === 'video' && mediaUrl && <video src={mediaUrl} controls preload="metadata" className="block max-h-[640px] w-full" aria-label="Scientific trajectory video" />}
    {expanded && mdSummary && <span className="block text-sm" aria-label="Measured molecular dynamics results">
      <strong>{mdSummary.complete ? 'Saved MD measurements' : 'Incomplete MD measurements'}</strong>
      {mdSummary.rows.map((row, index) => <span key={`${row.step}-${index}`} className="my-2 block">
        <strong>{row.engine} · {row.step}</strong>
        <span className="block">Measured rate: {row.rate === null ? 'Unknown' : `${row.rate} ns/day`}</span>
        <span className="block">Executed steps: {row.executed ?? 'Unknown'} · Durably completed: {row.durable ?? 'Unknown'} · Requested: {row.requested ?? 'Unknown'}</span>
        <span className="block">Measured elapsed: {row.seconds === null ? 'Unknown' : `${row.seconds} s`}</span>
      </span>)}
      <span className="block text-xs">Reported measurements are retained evidence, not a scientific validation of the simulation. Missing quantities remain unknown.</span>
    </span>}
  </span>;
}
