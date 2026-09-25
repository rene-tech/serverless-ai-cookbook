import { useState } from 'react';
import { request } from 'librechat-data-provider';

type Fact = { id: string; text: string; attribution: string; uncertain: boolean;
  source: { quote: string; spans: { start: number; end: number }[]; source_file: string }[]; dose_policy?: string };
type Soap = { status: string; provenance: { document_sha256: string; transcript_sha256: string; report_model: string; reviewed_source?: unknown };
  sections: Record<string, { status: string; notice: string; facts: Fact[] }>; unassigned: Fact[];
  handoff: { source_fact_id: string; source_text: string; status: string; assignee: string; execution_authorized: boolean }[];
  notices: string[]; withheld_count: number; generation_warnings?: { code: string; detail: string }[]; demo_review?: { reviewed_at: string }; };
const labels: Record<string, string> = { S: 'S · Subjective', O: 'O · Objective', A: 'A · Recorded assessment', P: 'P · Recorded plan' };

export default function ClinicalSoap({ jobId }: { jobId: string }) {
  const [value, setValue] = useState<Soap | null>(null);
  const [error, setError] = useState('');
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [evidence, setEvidence] = useState<{ before: string; quote: string; after: string; start: number; end: number } | null>(null);
  const base = `/api/scientific-demos/clinical/${jobId}`;
  async function load() {
    setError(''); setBusy(true);
    try { setValue(await request.get<Soap>(`${base}/soap`)); }
    catch { setError('SOAP view could not be loaded. The original report remains unchanged.'); }
    finally { setBusy(false); }
  }
  async function source(item: Fact['source'][0], span: { start: number; end: number }) {
    try {
      const response = await request.getResponse<string>(item.source_file, { responseType: 'text' });
      const text = [...response.data];
      setEvidence({ before: text.slice(Math.max(0, span.start - 100), span.start).join(''),
        quote: text.slice(span.start, span.end).join(''), after: text.slice(span.end, span.end + 100).join(''), ...span });
    } catch { setError('Source transcript could not be read; do not approve from the summary alone.'); }
  }
  const fact = (item: Fact) => <li key={item.id} className="my-2">
    <p>{item.text} <span className="text-xs">[{item.id}; {item.attribution}{item.uncertain ? '; uncertain' : ''}]</span></p>
    <div className="flex flex-wrap gap-2">{item.source.flatMap((part, index) => part.spans.map((span) =>
      <button type="button" className="text-xs underline" key={`${index}-${span.start}`} onClick={() => void source(part, span)}>Source {span.start}–{span.end}</button>))}</div>
    {item.dose_policy && <p className="text-xs">{item.dose_policy}</p>}
  </li>;
  return <section className="mt-3" aria-label={`SOAP draft ${jobId}`}>
    <button type="button" disabled={busy} className="rounded border p-2" onClick={() => void load()}>Open SOAP & task-handoff draft</button>
    {error && <p role="alert">{error}</p>}
    {value && <div className="mt-3 rounded border border-border-medium p-3">
      <h4 className="font-semibold">DRAFT · human review required · not clinical sign-off</h4>
      <p className="my-2 text-xs">{value.provenance.report_model} · {value.withheld_count} withheld entries require separate review. Unknown sections are not normal findings.</p>
      <p className="my-2 text-xs">Check short answers such as “yes” or “no” against the preceding question in their source context; they are not independently interpretable clinical facts.</p>
      {value.generation_warnings?.map((warning, index) => <p role="alert" key={index} className="my-2 text-sm text-status-error">Generation incomplete: {warning.code} — {warning.detail}</p>)}
      {Object.entries(value.sections).map(([key, section]) => <section key={key} className="my-3">
        <h5 className="font-semibold">{labels[key]}</h5>
        {section.facts.length ? <ul>{section.facts.map(fact)}</ul> : <p className="text-sm">{section.notice}</p>}
      </section>)}
      {value.unassigned.length > 0 && <section><h5 className="font-semibold">Unassigned / uncertain source passages</h5><ul>{value.unassigned.map(fact)}</ul></section>}
      <h5 className="mt-3 font-semibold">Task handoff · proposals only</h5>
      {value.handoff.length ? <ul>{value.handoff.map((item) => <li key={item.source_fact_id} className="my-2">{item.source_text} [{item.source_fact_id}]<p className="text-xs">Assignee not assigned · clinician review required · execution not authorized</p></li>)}</ul> : <p className="text-sm">No accepted recorded plan. No task or treatment action was inferred.</p>}
      {evidence && <aside className="my-3 rounded border p-2" aria-label="Exact source evidence"><p>Transcript characters {evidence.start}–{evidence.end}</p><pre className="whitespace-pre-wrap text-sm">{evidence.before}<mark>{evidence.quote}</mark>{evidence.after}</pre></aside>}
      <details className="my-3"><summary>Transcript / model / correction audit</summary><pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(value.provenance, null, 2)}</pre></details>
      <p className="my-2 text-xs">{value.notices.join(' ')}</p>
      <label className="block text-sm"><input type="checkbox" checked={ack} onChange={(event) => setAck(event.target.checked)} /> I checked source evidence, negation, medication/dose uncertainty and withheld facts for this demonstration.</label>
      <button type="button" className="my-2 rounded border p-2" disabled={!ack || busy || Boolean(value.demo_review)} onClick={() => void (async () => {
        setBusy(true); setError('');
        try { await request.post(`${base}/review`, { document_sha256: value.provenance.document_sha256, attestation: 'reviewed-demo-draft-not-clinical-signoff' }); await load(); }
        catch { setError('Review acknowledgement was not recorded. Recheck the exact draft.'); }
        finally { setBusy(false); }
      })()}>Record demo review — not clinical approval</button>
      {value.demo_review && <p role="status">Demo review recorded {value.demo_review.reviewed_at}. Not clinical sign-off; no task executed.</p>}
      <button type="button" className="ml-2 rounded border p-2" onClick={() => { const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = url; link.download = `soap-draft-${jobId}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}>Download structured draft</button>
    </div>}
  </section>;
}
