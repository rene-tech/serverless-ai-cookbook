import { useState } from 'react';
import { request } from 'librechat-data-provider';

type Decision = { fact_id: string; disposition: string; reason: string };
type Fact = { id: string; text: string; attribution: string; uncertain: boolean;
  source: { quote: string; spans: { start: number; end: number }[]; source_file: string }[]; dose_policy?: string;
  model_review?: { verdict?: string; reason?: string }; demo_disposition: Decision };
type Soap = { status: string; provenance: { document_sha256: string; transcript_sha256: string; report_model: string; reviewed_source?: unknown };
  sections: Record<string, { status: string; notice: string; facts: Fact[] }>; unassigned: Fact[];
  handoff: { source_fact_id: string; source_text: string; status: string; assignee: string; execution_authorized: boolean }[];
  notices: string[]; withheld_count: number; generation_warnings?: { code: string; detail: string }[]; demo_review?: { reviewed_at: string };
  review_candidates: Fact[]; excluded_from_reviewed_projection: Fact[]; review_complete: boolean;
  fact_review_sha256: string | null; fact_review: { reviewer_kind: string; decisions: Decision[] } | null;
  model_document_url: string; legacy_demo_review?: unknown };
const labels: Record<string, string> = { S: 'S · Subjective', O: 'O · Objective', A: 'A · Recorded assessment', P: 'P · Recorded plan' };

export default function ClinicalSoap({ jobId }: { jobId: string }) {
  const [value, setValue] = useState<Soap | null>(null);
  const [error, setError] = useState('');
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reviewerKind, setReviewerKind] = useState('');
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [evidence, setEvidence] = useState<{ before: string; quote: string; after: string; start: number; end: number } | null>(null);
  const base = `/api/scientific-demos/clinical/${jobId}`;
  async function load() {
    setError(''); setBusy(true);
    try {
      const result = await request.get<Soap>(`${base}/soap`);
      setValue(result); setAck(false);
      setReviewerKind(result.fact_review?.reviewer_kind || '');
      setDecisions(Object.fromEntries(result.review_candidates.map((item) => [item.id, item.demo_disposition])));
    }
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
  const fact = (item: Fact, original = false) => <li key={item.id} className="my-2">
    <p>{item.text} <span className="text-xs">[{item.id}; {item.attribution}{item.uncertain ? '; uncertain' : ''}]</span></p>
    <div className="flex flex-wrap gap-2">{item.source.flatMap((part, index) => part.spans.map((span) =>
      <button type="button" className="text-xs underline" key={`${index}-${span.start}`} onClick={() => void source(part, span)}>{original ? 'Original source' : 'Source'} {span.start}–{span.end}</button>))}</div>
    {item.dose_policy && <p className="text-xs">{item.dose_policy}</p>}
  </li>;
  const canSave = Boolean(value && !value.review_complete && reviewerKind && value.review_candidates.every((item) =>
    ['retain_for_demo', 'reject', 'uncertain'].includes(decisions[item.id]?.disposition)
      && decisions[item.id]?.reason.trim() && decisions[item.id]?.reason.length <= 2000));
  async function saveFacts() {
    if (!value || !canSave) return;
    setBusy(true); setError('');
    try {
      await request.post(`${base}/fact-review`, { document_sha256: value.provenance.document_sha256,
        transcript_sha256: value.provenance.transcript_sha256, expected_review_sha256: null,
        reviewer_kind: reviewerKind, decisions: value.review_candidates.map((item) => decisions[item.id]) });
      await load();
    } catch { setError('Fact review was not confirmed. Reload the saved snapshot; never overwrite or blindly resubmit different decisions.'); }
    finally { setBusy(false); }
  }
  return <section className="mt-3" aria-label={`SOAP draft ${jobId}`}>
    <button type="button" disabled={busy} className="rounded border p-2" onClick={() => void load()}>Open SOAP & task-handoff draft</button>
    {error && <p role="alert">{error}</p>}
    {value && <div className="mt-3 rounded border border-border-medium p-3">
      <h4 className="font-semibold">DRAFT · human review required · not clinical sign-off</h4>
      <p className="my-2 text-xs">{value.provenance.report_model} · {value.withheld_count} withheld entries require separate review. Unknown sections are not normal findings.</p>
      <p className="my-2 text-xs">Check short answers such as “yes” or “no” against the preceding question in their source context; they are not independently interpretable clinical facts.</p>
      {value.generation_warnings?.map((warning, index) => <p role="alert" key={index} className="my-2 text-sm text-status-error">Generation incomplete: {warning.code} — {warning.detail}</p>)}
      <section aria-label="Original model candidates and fact review" className="my-3 rounded border p-3">
        <h5 className="font-semibold">Original model candidates · not reviewed SOAP</h5>
        <p className="my-2 text-xs">The original model output is immutable. Automated attribution and review reasons may be wrong. Keep rejected or unresolved meanings out of the reviewed projection; do not edit source wording or infer roles. <a className="underline" href={value.model_document_url}>Download original model JSON</a></p>
        <label className="block">Reviewer kind
          <select aria-label="Demo reviewer kind" disabled={busy || value.review_complete} value={reviewerKind} onChange={(event) => setReviewerKind(event.target.value)}>
            <option value="">Choose explicitly</option>
            <option value="ai_engineering">AI engineering review · not human or clinical approval</option>
            <option value="self_declared_human_demo">Self-declared human demo review · not clinician certification</option>
          </select>
        </label>
        {value.review_candidates.map((item) => <div role="group" aria-label={`Review fact ${item.id}`} key={item.id} className="my-3 rounded border p-2">
          <ul>{fact(item, true)}</ul>
          {item.model_review && <p className="my-2 text-xs">Original automated verdict / rationale — unverified: {item.model_review.verdict || 'unknown'} · {item.model_review.reason || 'not provided'}</p>}
          <label className="block">Disposition for {item.id}
            <select aria-label={`Disposition for ${item.id}`} disabled={busy || value.review_complete} value={decisions[item.id]?.disposition || 'unreviewed'} onChange={(event) => setDecisions({ ...decisions, [item.id]: { fact_id: item.id, disposition: event.target.value, reason: decisions[item.id]?.reason || '' } })}>
              <option value="unreviewed">Unreviewed · excluded</option>
              <option value="retain_for_demo">Retain source passage for demo · not clinical validation</option>
              <option value="reject">Reject · exclude from SOAP and task proposals</option>
              <option value="uncertain">Uncertain · exclude from SOAP and task proposals</option>
            </select>
          </label>
          <label className="block">Reason for {item.id}
            <textarea aria-label={`Reason for ${item.id}`} maxLength={2000} disabled={busy || value.review_complete} value={decisions[item.id]?.reason || ''} onChange={(event) => setDecisions({ ...decisions, [item.id]: { fact_id: item.id, disposition: decisions[item.id]?.disposition || 'unreviewed', reason: event.target.value } })} />
          </label>
        </div>)}
        {!value.review_candidates.length && <p>No model facts to retain. An explicit reviewer-kind snapshot is still required.</p>}
        <p className="my-2 text-xs">Saving freezes all dispositions and reasons as a separate, hash-bound snapshot. Check every decision before saving; existing snapshots are never overwritten.</p>
        <button type="button" className="rounded border p-2" disabled={busy || !canSave} onClick={() => void saveFacts()}>Save immutable fact review</button>
        {value.review_complete && <p role="status">Fact review saved · {value.fact_review?.reviewer_kind} · SHA256 {value.fact_review_sha256}. Original model output unchanged.</p>}
      </section>
      <h5 className="font-semibold">Reviewed SOAP projection · retained demo passages only</h5>
      {!value.review_complete && <p role="status">No complete fact review yet. Unreviewed model candidates are excluded from SOAP and task proposals.</p>}
      {Object.entries(value.sections).map(([key, section]) => <section key={key} className="my-3">
        <h5 className="font-semibold">{labels[key]}</h5>
        {section.facts.length ? <ul>{section.facts.map((item) => fact(item))}</ul> : <p className="text-sm">{section.notice}</p>}
      </section>)}
      {value.unassigned.length > 0 && <section><h5 className="font-semibold">Unassigned / uncertain source passages</h5><ul>{value.unassigned.map((item) => fact(item))}</ul></section>}
      {value.excluded_from_reviewed_projection.length > 0 && <section aria-label="Excluded fact review evidence"><h5 className="font-semibold">Excluded from reviewed SOAP / tasks · evidence retained above</h5><ul>{value.excluded_from_reviewed_projection.map((item) => <li key={item.id}>[{item.id}] {item.demo_disposition.disposition}: {item.demo_disposition.reason || 'Awaiting explicit review'}</li>)}</ul></section>}
      <h5 className="mt-3 font-semibold">Task handoff · proposals only</h5>
      {value.handoff.length ? <ul>{value.handoff.map((item) => <li key={item.source_fact_id} className="my-2">{item.source_text} [{item.source_fact_id}]<p className="text-xs">Assignee not assigned · clinician review required · execution not authorized</p></li>)}</ul> : <p className="text-sm">No accepted recorded plan. No task or treatment action was inferred.</p>}
      {evidence && <aside className="my-3 rounded border p-2" aria-label="Exact source evidence"><p>Transcript characters {evidence.start}–{evidence.end}</p><pre className="whitespace-pre-wrap text-sm">{evidence.before}<mark>{evidence.quote}</mark>{evidence.after}</pre></aside>}
      <details className="my-3"><summary>Transcript / model / correction audit</summary><pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(value.provenance, null, 2)}</pre></details>
      <p className="my-2 text-xs">{value.notices.join(' ')}</p>
      <label className="block text-sm"><input type="checkbox" checked={ack} onChange={(event) => setAck(event.target.checked)} /> I checked source evidence, negation, medication/dose uncertainty and withheld facts for this demonstration.</label>
      {value.legacy_demo_review && <p className="text-xs">A historical acknowledgement is retained, but does not qualify this reviewed projection.</p>}
      <button type="button" className="my-2 rounded border p-2" disabled={!ack || busy || !value.review_complete || Boolean(value.demo_review)} onClick={() => void (async () => {
        setBusy(true); setError('');
        try { await request.post(`${base}/review`, { document_sha256: value.provenance.document_sha256, fact_review_sha256: value.fact_review_sha256, attestation: 'reviewed-demo-draft-not-clinical-signoff' }); await load(); }
        catch { setError('Review acknowledgement was not recorded. Recheck the exact draft.'); }
        finally { setBusy(false); }
      })()}>Record demo review — not clinical approval</button>
      {value.demo_review && <p role="status">Demo review recorded {value.demo_review.reviewed_at}. Not clinical sign-off; no task executed.</p>}
      <button type="button" className="ml-2 rounded border p-2" onClick={() => { const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = url; link.download = `soap-draft-${jobId}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}>Download structured draft</button>
    </div>}
  </section>;
}
