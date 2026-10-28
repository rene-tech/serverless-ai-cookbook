import { useState } from 'react';
import { request } from 'librechat-data-provider';
import { Button } from '@librechat/client';
import { Link } from 'react-router-dom';

type RecordValue = Record<string, any>;
const object = (value: unknown): RecordValue => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
const scalar = (value: unknown) => ['string', 'number', 'boolean'].includes(typeof value) ? (String(value).length > 2048 ? String(value).slice(0, 2048) + '…' : String(value)) : undefined;
const workspaceLink = (value: unknown) => typeof value === 'string' && value.startsWith('/demos?tab=workspace&') ? value : undefined;

export default function ScientificResult({ value }: { value: unknown }) {
  const [retrieved, setRetrieved] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [technical, setTechnical] = useState(false);
  const [busy, setBusy] = useState(false);
  const envelope = object(value);
  const result = object(envelope.scientific_summary ?? envelope.result?.summary ?? envelope.result ?? value);
  const operation = object(envelope.operation);
  const validation = object(result.validation);
  const rows: [string, unknown][] = [
    ['App', result.model_id ?? result.model ?? operation.model_id], ['Operation', operation.id ?? result.operation],
    ['Status', operation.status ?? result.status ?? result.terminal_status ?? envelope.status], ['Error', operation.error_detail ?? envelope.error],
    ['Result', typeof envelope.result === 'string' ? envelope.result : undefined],
    ['Foreground voxels', validation.foreground_voxels], ['Foreground volume (mm³)', validation.foreground_volume_mm3],
    ['Geometry preserved', validation.geometry_preserved], ['Model bundle', result.bundle], ['Bundle version', result.bundle_version],
    ['Frames completed', result.frames_completed], ['Annotation orientation', result.preprocessing?.annotation_orientation],
    ['Workflow', result.workflow], ['Mode', result.mode], ['Scene', result.scene], ['Task complete', result.task_complete],
    ['Successful episodes', result.successful_episodes], ['Requested episodes', result.requested_episodes],
    ['Interpretation', result.intended_use ?? result.recording_semantics],
  ];
  const file = object(envelope.workspace_file);
  const href = workspaceLink(file.workspace_url);
  const files = Object.entries(object(result.files)).slice(0, 100);
  const scenarios = Array.isArray(result.scenarios) ? result.scenarios.slice(0, 100).map(object) : [];
  const visible = rows.filter(([, item]) => scalar(item) !== undefined);
  return <div className="mt-3 space-y-3 text-sm">
    {visible.length ? <dl className="grid gap-2 sm:grid-cols-2">{visible.map(([label, item]) => <div key={label}><dt className="text-text-secondary">{label}</dt><dd className="break-words">{scalar(item)}</dd></div>)}</dl>
      : <p>No recognized scientific summary is present. Inspect the retained result and its manifest before drawing conclusions.</p>}
    {href && <p><Link className="underline" to={href}>Open retained result file</Link>{typeof file.size_bytes === 'number' && ` · ${file.size_bytes.toLocaleString()} bytes`}</p>}
    {file.sha256 && <p className="break-all text-xs">Retained file SHA256 {String(file.sha256)}</p>}
    {Array.isArray(envelope.artifacts) && <ul>{envelope.artifacts.slice(0, 1000).map(object).map((artifact: RecordValue, i: number) => <li key={i} className="my-2">
      {String(artifact.name)} · {String(artifact.media_type)} · {Number(artifact.size_bytes).toLocaleString()} bytes · {String(artifact.semantic_type)}
      {workspaceLink(retrieved[artifact.retrieve_url]) ? <Link className="ml-2 underline" to={retrieved[artifact.retrieve_url]}>Open verified artifact</Link>
        : Number(artifact.size_bytes) <= 32 * 1024 * 1024 && /^\/api\/scientific-demos\/runs\/op-[a-z0-9-]+\/artifacts\/\d+$/.test(artifact.retrieve_url) ? <Button disabled={busy} variant="outline" onClick={async () => {
          setBusy(true); setError('');
          try { const saved = await request.get<{ workspace_url: string }>(artifact.retrieve_url); setRetrieved(previous => ({ ...previous, [artifact.retrieve_url]: saved.workspace_url })); }
          catch (e) { setError((e as Error).message || 'Retrieval failed. Retry the same artifact; no compute is submitted.'); }
          finally { setBusy(false); }
        }}>Retrieve artifact</Button> : <span> · Retrieve this larger original with the batch file client or saved workflow.</span>}
    </li>)}</ul>}
    {envelope.artifact_error && <p role="alert">{String(envelope.artifact_error)}</p>}
    {error && <p role="alert">{error}</p>}
    {files.length > 0 && <div><p className="font-semibold">Reported output files</p><ul>{files.map(([name, metadata]) => <li key={name}>{name}{typeof object(metadata).size_bytes === 'number' && ` · ${object(metadata).size_bytes.toLocaleString()} bytes`}</li>)}</ul><p className="text-xs">Names and sizes reported by the App. Use the saved workflow artifacts or manifest to retrieve originals; listing alone does not verify downloaded bytes.</p></div>}
    {scenarios.map((item: RecordValue, i: number) => <p key={i}>Scenario {scalar(item.name) ?? i + 1} · Task complete: {scalar(item.task_complete) ?? 'unknown'} · Samples: {scalar(item.samples) ?? 'unknown'}</p>)}
    <p className="text-xs text-text-secondary">Execution status and structural checks do not establish clinical accuracy, task success or physical validity.</p>
    <details onToggle={e => setTechnical(e.currentTarget.open)}><summary>Technical details</summary>{technical && <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs">{JSON.stringify(value, null, 2)}</pre>}</details>
  </div>;
}
