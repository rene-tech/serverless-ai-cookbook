const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizeReview, makeReview, validateReview, hash } = require('./fact-review.cjs');
const { buildSoap } = require('./soap.cjs');
const identity = { job_id: 'a'.repeat(32), document_sha256: 'b'.repeat(64), transcript_sha256: hash('source') };
const actor = hash('owner');
const input = () => ({ document_sha256: identity.document_sha256, transcript_sha256: identity.transcript_sha256,
  expected_review_sha256: null, reviewer_kind: 'ai_engineering', decisions: [{ fact_id: 'F0001', disposition: 'reject', reason: 'Alternative remains unresolved.' }] });
test('snapshot binds full original identity and preserves explicit AI scope', () => {
  const row = makeReview(input(), identity, ['F0001'], actor);
  assert.equal(validateReview(row, identity, ['F0001'], actor), row);
  assert.equal(row.clinical_signoff, false); assert.equal(row.human_review_required, true);
  assert.equal(row.reviewer_kind, 'ai_engineering');
  assert.throws(() => validateReview(row, { ...identity, reviewed_source: { speaker_job: 'different' } }, ['F0001'], actor), /provenance/);
  assert.throws(() => validateReview(row, identity, ['F0001'], hash('other')), /identity/);
});
for (const [name, mutate] of [
  ['missing', x => { x.decisions = []; }],
  ['duplicate', x => { x.decisions.push(x.decisions[0]); }],
  ['unknown fact', x => { x.decisions[0].fact_id = 'F0002'; }],
  ['pending', x => { x.decisions[0].disposition = 'unreviewed'; }],
  ['blank reason', x => { x.decisions[0].reason = ' \n '; }],
  ['oversized reason', x => { x.decisions[0].reason = 'x'.repeat(2001); }],
  ['control characters', x => { x.decisions[0].reason = '\u0000bad'; }],
  ['nontext reason', x => { x.decisions[0].reason = { text: 'reason' }; }],
  ['changed document', x => { x.document_sha256 = 'c'.repeat(64); }],
  ['changed transcript', x => { x.transcript_sha256 = 'd'.repeat(64); }],
  ['non-absent CAS', x => { x.expected_review_sha256 = 'e'.repeat(64); }],
  ['implicit reviewer', x => { x.reviewer_kind = ''; }],
  ['invented certification', x => { x.reviewer_kind = 'certified_clinician'; }],
  ['spoofed owner', x => { x.actor_user = actor; }],
  ['fact text editing', x => { x.decisions[0].text = 'corrected medical meaning'; }],
]) test(`fail closed: ${name}`, () => { const x = input(); mutate(x); assert.throws(() => normalizeReview(x, identity, ['F0001'])); });
test('self-declared human demo remains explicitly uncertified', () => {
  const x = input(); x.reviewer_kind = 'self_declared_human_demo';
  const row = makeReview(x, identity, ['F0001'], actor);
  assert.equal(row.reviewer_kind, x.reviewer_kind); assert.equal(row.clinical_signoff, false);
});
test('saved decisions cannot be altered or gain fields', () => {
  const row = makeReview(input(), identity, ['F0001'], actor);
  assert.throws(() => validateReview({ ...row, decisions: [{ ...row.decisions[0], reason: 'changed' }] }, identity, ['F0001'], actor), /decisions/);
  assert.throws(() => validateReview({ ...row, clinical_signoff: true }, identity, ['F0001'], actor), /scope/);
  assert.throws(() => validateReview({ ...row, extra: true }, identity, ['F0001'], actor), /fields/);
});
test('all unreviewed/rejected/uncertain candidates stay outside SOAP and task proposals', () => {
  const source = 'Proposed follow-up.';
  const fact = { id: 'F0001', section: 'plan', source_attribution: 'clinician_statement', source_attribution_extraction: 'clinician_statement',
    source_attribution_review: 'clinician_statement', uncertain: false, source_phrases: [{ quote: source, spans: [{ start: 0, end: source.length }] }],
    review: { reason: 'Synthetic unverified model rationale.' } };
  const document = { transcript_sha256: hash(source), facts: [fact], rejected: [] };
  const id = { ...identity, transcript_sha256: hash(source), document_sha256: hash(JSON.stringify(document)) };
  const original = JSON.stringify(document);
  for (const disposition of ['unreviewed', 'reject', 'uncertain', 'retain_for_demo']) {
    const review = disposition === 'unreviewed' ? null : makeReview({ ...input(), document_sha256: id.document_sha256,
      transcript_sha256: id.transcript_sha256, decisions: [{ fact_id: 'F0001', disposition, reason: 'Synthetic demo decision.' }] }, id, ['F0001'], actor);
    const value = buildSoap(document, source, id, review);
    assert.equal(value.review_candidates.length, 1); assert.equal(value.review_candidates[0].model_review.reason, fact.review.reason);
    assert.equal(value.sections.P.facts.length, disposition === 'retain_for_demo' ? 1 : 0);
    assert.equal(value.handoff.length, disposition === 'retain_for_demo' ? 1 : 0);
    if (value.handoff.length) assert.equal(value.handoff[0].execution_authorized, false);
    assert.equal(value.excluded_from_reviewed_projection.length, disposition === 'retain_for_demo' ? 0 : 1);
    assert.equal(value.status, 'DRAFT'); assert.equal(value.human_review_required, true); assert.equal(value.clinical_signoff, false);
    assert.equal(JSON.stringify(document), original);
  }
});
