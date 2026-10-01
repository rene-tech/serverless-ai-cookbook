/* Immutable per-fact engineering/demo dispositions, not clinical certification. */
const crypto = require('node:crypto');
const hash = (value) => crypto.createHash('sha256').update(value).digest('hex');
const error = (message) => Object.assign(new Error(message), { status: 409 });
const KINDS = ['ai_engineering', 'self_declared_human_demo'];
const DISPOSITIONS = ['retain_for_demo', 'reject', 'uncertain'];
function keys(value, allowed) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).some((key) => !allowed.includes(key))
      || allowed.some((key) => !Object.hasOwn(value, key))) throw error('Invalid review fields.');
}
function normalizeReview(input, identity, ids) {
  keys(input, ['document_sha256', 'transcript_sha256', 'expected_review_sha256', 'reviewer_kind', 'decisions']);
  if (!/^[a-f0-9]{64}$/.test(input.document_sha256 || '') || input.document_sha256 !== identity.document_sha256
      || input.transcript_sha256 !== identity.transcript_sha256 || input.expected_review_sha256 !== null) {
    throw error('Review must bind the exact original document/transcript and an absent review snapshot.');
  }
  if (!KINDS.includes(input.reviewer_kind)) throw error('Choose AI engineering or self-declared human demo review; neither is clinician certification.');
  if (!Array.isArray(input.decisions) || input.decisions.length !== ids.length || new Set(ids).size !== ids.length) throw error('Review every exact model fact once.');
  const rows = new Map();
  for (const row of input.decisions) {
    keys(row, ['fact_id', 'disposition', 'reason']);
    if (!ids.includes(row.fact_id) || rows.has(row.fact_id) || !DISPOSITIONS.includes(row.disposition)) throw error('Unknown, duplicate or unreviewed fact disposition.');
    if (typeof row.reason !== 'string' || !row.reason.trim() || row.reason.length > 2000
        || /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(row.reason)) throw error('Every disposition needs a plain-text reason of 1–2000 characters.');
    rows.set(row.fact_id, { fact_id: row.fact_id, disposition: row.disposition, reason: row.reason.trim() });
  }
  return { document_sha256: input.document_sha256, transcript_sha256: input.transcript_sha256,
    expected_review_sha256: null, reviewer_kind: input.reviewer_kind, decisions: ids.map((id) => rows.get(id)) };
}
function makeReview(input, identity, ids, actor, at = new Date().toISOString()) {
  const normalized = normalizeReview(input, identity, ids);
  return { schema: 'clinical-demo/fact-review/v1', job_id: identity.job_id, actor_user: actor,
    original_provenance_sha256: hash(JSON.stringify(identity)), request_sha256: hash(JSON.stringify(normalized)),
    document_sha256: normalized.document_sha256, transcript_sha256: normalized.transcript_sha256,
    reviewer_kind: normalized.reviewer_kind, decisions: normalized.decisions, reviewed_at: at,
    clinical_signoff: false, human_review_required: true };
}
function validateReview(review, identity, ids, actor = review?.actor_user) {
  keys(review, ['schema', 'job_id', 'actor_user', 'original_provenance_sha256', 'request_sha256',
    'document_sha256', 'transcript_sha256', 'reviewer_kind', 'decisions', 'reviewed_at', 'clinical_signoff', 'human_review_required']);
  if (review.schema !== 'clinical-demo/fact-review/v1' || review.job_id !== identity.job_id
      || review.actor_user !== actor || !/^[a-f0-9]{64}$/.test(actor || '')
      || typeof review.reviewed_at !== 'string' || !Number.isFinite(Date.parse(review.reviewed_at))
      || review.clinical_signoff !== false || review.human_review_required !== true) throw error('Invalid saved review identity or scope.');
  const expected = makeReview({ document_sha256: review.document_sha256, transcript_sha256: review.transcript_sha256,
    expected_review_sha256: null, reviewer_kind: review.reviewer_kind, decisions: review.decisions }, identity, ids, actor, review.reviewed_at);
  if (review.original_provenance_sha256 !== expected.original_provenance_sha256 || review.request_sha256 !== expected.request_sha256) throw error('Saved review differs from original provenance or decisions.');
  return review;
}
module.exports = { normalizeReview, makeReview, validateReview, hash, KINDS, DISPOSITIONS };
