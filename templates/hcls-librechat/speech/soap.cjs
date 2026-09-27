/* Deterministic, source-linked SOAP presentation. No additional model inference. */
const crypto = require('node:crypto');
const hash = (value) => crypto.createHash('sha256').update(value).digest('hex');
const UNKNOWN = 'Not documented in accepted source-linked facts; this does not mean normal, absent or denied.';
function buildSoap(document, transcript, identity, review = null) {
  if (document.transcript_sha256 !== hash(transcript)) throw new Error('SOAP transcript hash differs from the accepted document');
  // Python provenance offsets count Unicode code points, not JS UTF-16 units.
  const characters = [...transcript];
  const sections = Object.fromEntries(['S', 'O', 'A', 'P'].map((key) => [key, { status: 'not_documented', notice: UNKNOWN, facts: [] }]));
  const unassigned = [], reviewCandidates = [], excluded = [];
  const ids = (document.facts || []).map((fact) => fact.id);
  if (new Set(ids).size !== ids.length) throw new Error('Duplicate model fact identity');
  if (review) require('./fact-review.cjs').validateReview(review, identity, ids);
  const decisions = new Map((review?.decisions || []).map((row) => [row.fact_id, row]));
  for (const fact of document.facts || []) {
    if (!/^F[0-9]+$/.test(fact.id) || !Array.isArray(fact.source_phrases) || !fact.source_phrases.length) throw new Error('SOAP requires validated source phrases');
    const source = fact.source_phrases.map((phrase) => {
      if (!phrase.spans?.length || phrase.spans.some((span) => !Number.isInteger(span.start) || !Number.isInteger(span.end) || span.start < 0 || span.end <= span.start || span.end > characters.length || characters.slice(span.start, span.end).join('') !== phrase.quote)) throw new Error('SOAP source phrase does not match transcript bytes');
      return { quote: phrase.quote, spans: phrase.spans,
        source_file: `/api/scientific-demos/clinical/${identity.job_id}/files/transcript.txt` };
    });
    const attribution = fact.source_attribution === fact.source_attribution_extraction && fact.source_attribution === fact.source_attribution_review ? fact.source_attribution : 'unclear';
    const item = { id: fact.id, text: source.map((phrase) => phrase.quote).join(' … '), source,
      attribution, uncertain: Boolean(fact.uncertain), source_section: fact.section,
      source_anchors: fact.source_anchors || [],
      medication_or_dose: Boolean(fact.medication_or_dose),
      ...(fact.medication_or_dose ? { dose_policy: 'Only the exact source anchors are known; unstated dose, unit, frequency or duration remain unknown.' } : {}) };
    const decision = decisions.get(item.id) || { fact_id: item.id, disposition: 'unreviewed', reason: '' };
    item.demo_disposition = decision;
    reviewCandidates.push({ ...item, model_review: fact.review || null,
      model_original_statement: fact.original_statement || fact.statement || null });
    if (decision.disposition !== 'retain_for_demo') {
      excluded.push({ ...item, reason: 'Not retained in reviewed SOAP/tasks; original model evidence remains unchanged.' });
      continue;
    }
    let section;
    if (!item.uncertain && attribution === 'patient_reported' && ['history', 'background', 'findings'].includes(fact.section)) section = 'S';
    else if (!item.uncertain && attribution === 'clinician_observed' && fact.section === 'findings') section = 'O';
    else if (!item.uncertain && ['clinician_statement', 'clinician_observed'].includes(attribution) && fact.section === 'assessment') section = 'A';
    else if (!item.uncertain && attribution === 'clinician_statement' && fact.section === 'plan') section = 'P';
    if (section) { sections[section].facts.push(item); sections[section].status = 'source_passages_for_review'; }
    else unassigned.push({ ...item, reason: 'Uncertain, ambiguous, teaching or incompatible attribution; not forced into a SOAP section.' });
  }
  return { schema: 'clinical-demo/soap-handoff/v1', status: 'DRAFT', human_review_required: true,
    clinical_signoff: false, clinical_validation: false,
    provenance: identity, sections, unassigned, review_candidates: reviewCandidates, excluded_from_reviewed_projection: excluded,
    fact_review: review, review_complete: Boolean(review),
    model_document_url: `/api/scientific-demos/clinical/${identity.job_id}/files/document.json`,
    handoff: sections.P.facts.map((fact) => ({ source_fact_id: fact.id, source_text: fact.text,
      source: fact.source, status: 'proposal_requires_clinician_review', assignee: 'not_assigned',
      execution_authorized: false, timing_and_dose: 'Only what is explicitly present in source_text/source anchors; otherwise unknown.' })),
    notices: ['Reviewed SOAP includes only explicitly retained demo passages; rejected, uncertain and unreviewed model candidates remain in separate review evidence.',
      'Original model JSON and hashes are preserved. A retained-for-demo disposition is not clinical validation or independently verified speaker attribution.',
      'Automated attribution and source matching are not clinical validation. Review transcript, rejected facts and completeness.',
      'Demo acknowledgement is not clinical sign-off and never executes a task.'],
    withheld_count: (document.rejected || []).length,
    generation_warnings: document.generation_warnings || [],
    review_url: `/api/scientific-demos/clinical/${identity.job_id}/files/review.md` };
}
module.exports = { buildSoap, hash, UNKNOWN };
