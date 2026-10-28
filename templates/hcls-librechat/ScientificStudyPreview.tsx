import { useQuery } from '@tanstack/react-query';
import { request } from 'librechat-data-provider';
import { scientificProgressDisplay, studyDisplay, studyNotice } from './scientific-run-display';
import type { ScientificProgress } from './scientific-run-display';
import WorkspaceReportPreview, { workspaceReportPath } from './WorkspaceReportPreview';
import { workspaceCodeHref } from './WorkspaceInlineCode';
import type { ReactNode } from 'react';

const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'needs_attention']);
type Study = {
  output_directory: string; state: string; phase?: string; current_step?: string;
  operation_admission?: string;
  admission_reason?: { code?: string; message?: string; retry_after_seconds?: number };
  updated_at?: number; failure?: { type?: string; message?: string };
  operations?: { step_id: string; operation_id: string; state?: string }[];
  completed_steps?: string[]; step_count?: number; queue_blocked?: boolean;
  model_progress?: { study_step_id: string; operation_id: string; progress: ScientificProgress }[];
  artifacts?: { name: string; download_url: string; size_bytes?: number }[];
};

/** Only an explicit same-origin whole-study link starts authenticated observation. */
export function scientificWorkflowPath(href: unknown): string | undefined {
  if (typeof href !== 'string' || !href.startsWith('/demos?') || /[\s\\]/u.test(href)) return;
  const url = new URL(href, 'https://workspace.invalid');
  if (url.pathname !== '/demos' || url.hash || url.searchParams.get('tab') !== 'runs' ||
      [...url.searchParams.keys()].some(key => !['tab', 'workflow'].includes(key)) ||
      ['tab', 'workflow'].some(key => url.searchParams.getAll(key).length !== 1)) return;
  const path = url.searchParams.get('workflow');
  return path?.startsWith('/workspace/') && path.length <= 1024 && !/[\0\\]/u.test(path) &&
    !path.split('/').some(part => ['.', '..'].includes(part)) ? path : undefined;
}

export default function ScientificStudyPreview({ href, children }: { href: string; children: ReactNode }) {
  const directory = scientificWorkflowPath(href);
  const status = useQuery(['scientific-demos', 'workflow-inline', directory], async () => {
    const result = await request.get<Study>(`/api/scientific-demos/studies/status?output_directory=${encodeURIComponent(directory!)}`);
    if (result.output_directory !== directory || typeof result.state !== 'string') throw new Error('Workflow location mismatch');
    return result;
  }, {
    enabled: !!directory, retry: false,
    refetchInterval: (data, query) => query.state.error || (data && TERMINAL.has(data.state)) ? false : 5000,
    refetchIntervalInBackground: false,
  });
  if (!directory) return <a href={href}>{children}</a>;
  const study = status.data;
  const display = study ? studyDisplay(study.state) : null;
  const measurements = (study?.model_progress || []).map(item => ({
    step: item.study_step_id, display: scientificProgressDisplay(item.progress),
  }));
  return <span role="group" aria-label="Live scientific study" className="my-3 block rounded-xl border border-border-medium p-3">
    <strong className="block">{children || 'Live scientific run'}</strong>
    {(study?.operations || []).map(operation => <span key={`${operation.step_id}-${operation.operation_id}`} className="block text-xs">
      {operation.step_id} · Operation <a className="underline" href={`/demos?tab=runs&operation=${encodeURIComponent(operation.operation_id)}`}><code>{operation.operation_id}</code></a>
      {operation.state ? ` · Study step state: ${operation.state}` : ''}
    </span>)}
    {study && !study.operations?.length && <span className="block text-sm">{study.operation_admission === 'unknown'
      ? 'Platform admission is unconfirmed; do not resubmit.' : 'No Serverless job has been admitted.'}</span>}
    {status.error && <span role="status" className="my-2 block">
      Live status is unavailable. Last known state is retained; compute may still be running. Refresh status; do not submit another copy.
    </span>}
    {!study && !status.error && <span role="status" className="block">Loading saved run status…</span>}
    {study && <>
      <span role="status" className="my-2 block">{display?.status}
        {study.current_step ? ` · ${study.current_step}` : ''}
        {Number.isSafeInteger(study.step_count) ? ` · ${study.completed_steps?.length ?? 0}/${study.step_count} phases` : ''}
      </span>
      {display?.description && <span className="block text-sm">{display.description}</span>}
      {studyNotice(study) && <span className="block text-sm">{studyNotice(study)}</span>}
      <span className="block text-xs">Last successful update: {status.dataUpdatedAt ? new Date(status.dataUpdatedAt).toLocaleString() : 'unavailable'}</span>
      {study.queue_blocked && <span role="status" className="block">Admission needs attention; the saved run has not been duplicated.</span>}
      {['failed', 'needs_attention'].includes(study.state) && <span role="alert" className="block">This study needs attention. Open Runs for its recorded failure and retained outputs.</span>}
      {!measurements.some(item => item.display?.rows.length) && <span className="block text-sm">Scientific progress and rate are not measured yet—not zero.</span>}
      {measurements.map(({ step, display: measured }, index) => <span key={`${step}-${index}`} className="block">
        {measured?.currentStep && <span className="block text-xs">{step} · Current operation stage: {measured.currentStep}</span>}
        {measured?.rows.map((row, n) => <span key={`${row.id}-${n}`} aria-label="Measured scientific progress" className="my-2 block text-sm">
          <strong>{step} · {row.id}</strong>
          <span className="block">Completed: {row.completed} · Target: {row.target}</span>
          <span className="block">Durably checkpointed: {row.durable}</span>
          <span className="block">{row.rateLabel}: {row.rate}</span>
          <span className="block text-xs text-text-secondary">{status.error ? 'Status refresh failed; showing last saved measurement' : row.freshness}{row.observedAt ? ` · ${row.observedAt}` : ''}</span>
        </span>)}
      </span>)}
      {(study.artifacts || []).map((artifact, index) => {
        const file = workspaceCodeHref(artifact.download_url);
        if (!file) return null;
        return workspaceReportPath(file)
          ? <WorkspaceReportPreview key={`${file}-${index}`} href={file}>{artifact.name}</WorkspaceReportPreview>
          : <a key={`${file}-${index}`} className="my-1 block underline" href={file} target="_blank" rel="noopener noreferrer">{artifact.name}</a>;
      })}
    </>}
    <span className="mt-2 flex gap-4 text-sm">
      <a href={href} target="_blank" rel="noopener noreferrer" className="underline">Open Runs</a>
      <button type="button" className="underline" disabled={status.isFetching} onClick={() => void status.refetch()}>Refresh status</button>
    </span>
    <span className="mt-2 block text-xs text-text-secondary">Read-only updates; refreshing never starts or restarts scientific work.</span>
  </span>;
}
