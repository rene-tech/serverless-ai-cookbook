import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { request } from 'librechat-data-provider';
import { Button, Input } from '@librechat/client';

export const guidedApps = ['monai-spleen-ct', 'holoscan-endoscopy', 'isaac-healthcare'];
type Field = { type?: string | string[]; enum?: unknown[]; default?: unknown; minimum?: number; maximum?: number; description?: string };
type Contract = { parameters: { properties?: Record<string, Field> }; operations: string[]; service_classes: string[];
  entries: { name: string; media_type: string; semantic_type: string; compression?: string; allowed_compressions?: string[] }[]; revision?: string };
type Draft = { parameters: Record<string, unknown>; arguments: { source: string; entry_name: string; operation: string; service_class: string; compression: string };
  preflight_sha256: string; checks: string[]; source_sha256: string; size_bytes: number };
type Saved = { draft: Draft | null; intent?: boolean; workflow?: { progress_url: string } };
const field = 'rounded border border-border-medium bg-surface-primary p-2 text-text-primary';
const hint: Record<string, string> = {
  'monai-spleen-ct': 'One 3D CT in Hounsfield units. The spleen mask is a research prediction, not a diagnosis. Input geometry and explicit precision are preserved.',
  'holoscan-endoscopy': 'Recorded video in an uncompressed TAR. Count 0 selects the remaining clip; stride changes recurrent model context. Overlays use encoded-pixel orientation.',
  'isaac-healthcare': 'Use the input role and workflow exposed by this deployment. A finished simulation does not establish task success or physical validity. No GPU starts when you open this form.',
};
const message = (error: unknown) => (error as { response?: { data?: { error?: string } }; message?: string }).response?.data?.error
  || (error as Error).message || 'Request unavailable. Reopen this saved request before submitting another copy.';

export default function ScientificAppForm({ model, requestId }: { model: string; requestId: string }) {
  const base = `/api/scientific-demos/apps/${encodeURIComponent(model)}`;
  const [contract, setContract] = useState<Contract>();
  const [source, setSource] = useState('');
  const [entry, setEntry] = useState('');
  const [operation, setOperation] = useState('');
  const [serviceClass, setServiceClass] = useState('');
  const [compression, setCompression] = useState('none');
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [advanced, setAdvanced] = useState('');
  const [saved, setSaved] = useState<Saved>({ draft: null });
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [uncertain, setUncertain] = useState(false);
  useEffect(() => {
    let active = true;
    Promise.all([request.get<Contract>(`${base}/contract`), request.get<Saved>(`${base}/draft?request_id=${requestId}`)])
      .then(([value, previous]) => {
        if (!active) return;
        setContract(value); setSaved(previous); setUncertain(Boolean(previous.intent));
        const args = previous.draft?.arguments;
        setSource(args?.source || ''); setEntry(args?.entry_name || value.entries[0]?.name || '');
        setOperation(args?.operation || value.operations[0] || ''); setServiceClass(args?.service_class || value.service_classes[0] || '');
        setCompression(args?.compression || value.entries[0]?.compression || value.entries[0]?.allowed_compressions?.[0] || 'none');
        const initial = previous.draft?.parameters || Object.fromEntries(Object.entries(value.parameters.properties || {}).filter(([, v]) => v.default !== undefined).map(([k, v]) => [k, v.default]));
        setParameters(initial); setAdvanced(JSON.stringify(initial, null, 2));
      }).catch(e => { if (active) setError(message(e)); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [base, requestId]);
  const restore = (value: Saved) => {
    setSaved(value); setUncertain(Boolean(value.intent));
    if (!value.draft) return;
    const args = value.draft.arguments;
    setSource(args.source); setEntry(args.entry_name); setOperation(args.operation);
    setServiceClass(args.service_class); setCompression(args.compression);
    setParameters(value.draft.parameters); setAdvanced(JSON.stringify(value.draft.parameters, null, 2));
  };
  const change = (next: Record<string, unknown>) => { setParameters(next); setAdvanced(JSON.stringify(next, null, 2)); setSaved({ draft: null }); };
  const locked = busy || uncertain || Boolean(saved.workflow);
  async function check() {
    setBusy(true); setError(''); setSaved({ draft: null });
    try {
      const value = JSON.parse(advanced);
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Parameters must be a JSON object.');
      const result = await request.post<Saved>(`${base}/preflight`, { request_id: requestId, source, entry_name: entry,
        operation, service_class: serviceClass, compression, parameters: value });
      setSaved(result);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function submit() {
    setBusy(true); setUncertain(true); setError('');
    try {
      const workflow = await request.post<{ progress_url: string }>(`${base}/submit`, { request_id: requestId, preflight_sha256: saved.draft?.preflight_sha256 });
      setSaved({ ...saved, workflow });
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <section aria-label={`${model} guided request`} className="my-4 rounded-xl border border-border-medium p-4">
    <h3 className="font-semibold">{model}</h3><p className="my-2 text-sm">{hint[model]}</p>
    <p className="text-xs text-text-secondary">Request {requestId}{contract?.revision ? ` · Contract ${contract.revision}` : ''}</p>
    {error && <p role="alert" className="my-2">{error}</p>}
    {busy && <p role="status">Checking the saved request…</p>}
    {saved.workflow ? <Link className="underline" to={saved.workflow.progress_url}>Open the existing workflow in Runs</Link> : <>
      {uncertain && <p role="status">Submission outcome needs reconciliation. Reconnect to read its receipt, or resume this exact saved request with the same identity.</p>}
      <fieldset disabled={locked} className="my-3 grid gap-3 md:grid-cols-2" onChange={() => setSaved({ draft: null })}>
        <label>Workspace input file<Input value={source} onChange={e => setSource(e.target.value)} placeholder="/workspace/inputs/..." /></label>
        <label>Input role<select className={`${field} block w-full`} value={entry} onChange={e => setEntry(e.target.value)}>{contract?.entries.map(item => <option key={item.name}>{item.name}</option>)}</select></label>
        <label>Operation<select className={`${field} block w-full`} value={operation} onChange={e => setOperation(e.target.value)}>{contract?.operations.map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Service class<select className={`${field} block w-full`} value={serviceClass} onChange={e => setServiceClass(e.target.value)}>{contract?.service_classes.map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Compression<select className={`${field} block w-full`} value={compression} onChange={e => setCompression(e.target.value)}>{['none', 'gzip', 'zstd'].map(v => <option key={v}>{v}</option>)}</select></label>
        {Object.entries(contract?.parameters.properties || {}).filter(([, spec]) => !['object', 'array'].some(t => (Array.isArray(spec.type) ? spec.type : [spec.type]).includes(t)) && !('$ref' in spec)).map(([name, spec]) => {
          const choices = spec.enum || (spec.type === 'boolean' ? [true, false] : undefined);
          const numeric = (Array.isArray(spec.type) ? spec.type : [spec.type]).some(t => t === 'number' || t === 'integer');
          return <label key={name}>{name.replaceAll('_', ' ')}{choices
            ? <select className={`${field} block w-full`} value={JSON.stringify(parameters[name]) ?? ''} onChange={e => change({ ...parameters, [name]: JSON.parse(e.target.value) })}>
              <option value="" disabled>Select a value</option>{choices.map(v => <option key={JSON.stringify(v)} value={JSON.stringify(v)}>{v === null ? 'Use authored default (null)' : String(v)}</option>)}</select>
            : <Input type={numeric ? 'number' : 'text'} min={spec.minimum} max={spec.maximum} step={spec.type === 'integer' ? 1 : 'any'} value={parameters[name] == null ? '' : typeof parameters[name] === 'object' ? JSON.stringify(parameters[name]) : String(parameters[name])}
              placeholder={parameters[name] === null ? 'Authored default (null)' : 'Optional unless required by schema'} onChange={e => {
                const next = { ...parameters };
                if (e.target.value === '') delete next[name]; else next[name] = numeric ? Number(e.target.value) : e.target.value;
                change(next);
              }} />}
            <span className="block text-xs text-text-secondary">{spec.description}</span></label>;
        })}
        <details className="md:col-span-2"><summary>Advanced parameters</summary><textarea aria-label="Advanced parameters JSON" className={`${field} mt-2 w-full font-mono text-xs`} rows={10} value={advanced} onChange={e => { setAdvanced(e.target.value); try { const value = JSON.parse(e.target.value); if (value && typeof value === 'object' && !Array.isArray(value)) setParameters(value); } catch {} }} /></details>
      </fieldset>
      <div className="flex gap-2"><Button disabled={locked || !contract || !source} onClick={() => void check()}>Check inputs</Button>
        <Button disabled={locked || !saved.draft} onClick={() => void submit()}>Submit checked request</Button>
        <Button variant="outline" disabled={busy} onClick={async () => { setBusy(true); try { const value = await request.get<Saved>(`${base}/draft?request_id=${requestId}`); restore(value); } catch (e) { setError(message(e)); } finally { setBusy(false); } }}>Reconnect</Button>
        {uncertain && saved.draft && <Button disabled={busy} onClick={() => void submit()}>Resume saved request</Button>}</div>
      {saved.draft && <div role="status" className="mt-3 text-sm"><p>Preflight complete · {saved.draft.size_bytes.toLocaleString()} bytes. No compute submitted by this check.</p>
        {saved.draft.checks.map(text => <p key={text}>{text}</p>)}<p className="break-all text-xs">Input SHA256 {saved.draft.source_sha256}</p></div>}
    </>}
  </section>;
}
