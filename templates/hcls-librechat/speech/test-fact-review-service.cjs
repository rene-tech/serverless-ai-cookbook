const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { hash } = require('./fact-review.cjs');

test('durable fact snapshots: owner isolation, CAS, idempotency, concurrent saves, legacy acknowledgement and immutable outputs', async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'clinical-fact-review-'));
  process.env.SCIENTIFIC_DEMOS_DIR = root;
  const service = require('../demos/service.cjs');
  const owner = 'synthetic-owner', text = 'A question? Yes.';
  const document = { transcript_sha256: hash(text), facts: [{ id: 'F0001', section: 'history', uncertain: false,
    source_attribution: 'patient_reported', source_attribution_extraction: 'patient_reported', source_attribution_review: 'patient_reported',
    source_phrases: [{ quote: text, spans: [{ start: 0, end: text.length }] }], review: { verdict: 'supported', reason: 'Synthetic model rationale; unverified.' } }], rejected: [] };
  async function fixture(char) {
    const id = char.repeat(32), dir = path.join(root, hash(owner), id), output = path.join(dir, 'output');
    await fs.mkdir(output, { recursive: true });
    await service.save(path.join(dir, 'request.json'), { created_at: '2026-09-27T00:00:00Z', kind: 'transcript', input_sha256: hash(text), report_model: 'fixture' });
    await service.save(path.join(dir, 'status.json'), { status: 'completed' });
    await fs.writeFile(path.join(output, 'document.json'), JSON.stringify(document)); await fs.writeFile(path.join(output, 'transcript.txt'), text);
    const current = await service.soap(owner, id);
    const input = { document_sha256: current.provenance.document_sha256, transcript_sha256: current.provenance.transcript_sha256,
      expected_review_sha256: null, reviewer_kind: 'ai_engineering', decisions: [{ fact_id: 'F0001', disposition: 'reject', reason: 'Alternative/short answer unresolved.' }] };
    return { id, dir, output, current, input };
  }
  try {
    const a = await fixture('a');
    await t.test('no implicit acceptance before review', async () => {
      assert.equal(a.current.sections.S.facts.length, 0); assert.equal(a.current.review_candidates.length, 1);
      await assert.rejects(service.reviewSoap(owner, a.id, { document_sha256: a.input.document_sha256, fact_review_sha256: null, attestation: 'reviewed-demo-draft-not-clinical-signoff' }), /complete exact/);
      await assert.rejects(service.reviewSoapFacts('other-owner', a.id, a.input), /not found/);
    });
    await t.test('legacy acknowledgement does not qualify a new projection', async () => {
      const historical = { schema: 'clinical-demo/review/v1', document_sha256: a.input.document_sha256, clinical_signoff: false };
      await fs.writeFile(path.join(a.dir, 'demo-review.json'), JSON.stringify(historical));
      const value = await service.soap(owner, a.id);
      assert.equal(value.demo_review, null); assert.equal(value.legacy_demo_review.qualifies_current_projection, false);
      assert.deepEqual(JSON.parse(await fs.readFile(path.join(a.dir, 'demo-review.json'))), historical);
    });
    const saved = await service.reviewSoapFacts(owner, a.id, a.input);
    await t.test('rejection/reason survives fresh read and complete exported projection', async () => {
      const fresh = await service.soap(owner, a.id);
      assert.equal(fresh.fact_review_sha256, saved.fact_review_sha256);
      assert.equal(fresh.fact_review.decisions[0].reason, a.input.decisions[0].reason);
      assert.equal(fresh.sections.S.facts.length, 0); assert.equal(fresh.handoff.length, 0);
      assert.equal(fresh.excluded_from_reviewed_projection[0].id, 'F0001');
      assert.equal(fresh.review_candidates[0].model_review.reason, document.facts[0].review.reason);
      assert.equal((await fs.stat(path.join(a.dir, 'fact-review-v1.json'))).mode & 0o777, 0o600);
    });
    await t.test('same request idempotent, changed decisions conflict without overwrite', async () => {
      assert.equal((await service.reviewSoapFacts(owner, a.id, a.input)).fact_review_sha256, saved.fact_review_sha256);
      await assert.rejects(service.reviewSoapFacts(owner, a.id, { ...a.input, decisions: [{ ...a.input.decisions[0], disposition: 'retain_for_demo' }] }), /already exists/);
      assert.equal((await service.soap(owner, a.id)).fact_review_sha256, saved.fact_review_sha256);
    });
    await t.test('acknowledgement binds snapshot and reviewer kind, never source repair', async () => {
      const input = { document_sha256: a.input.document_sha256, fact_review_sha256: saved.fact_review_sha256, attestation: 'reviewed-demo-draft-not-clinical-signoff' };
      await assert.rejects(service.reviewSoap(owner, a.id, { ...input, fact_review_sha256: 'f'.repeat(64) }), /complete exact/);
      const ack = await service.reviewSoap(owner, a.id, input);
      assert.equal(ack.reviewer_kind, 'ai_engineering'); assert.equal(ack.clinical_signoff, false);
      assert.deepEqual(await service.reviewSoap(owner, a.id, input), ack);
      assert.equal(await fs.readFile(path.join(a.output, 'document.json'), 'utf8'), JSON.stringify(document));
      assert.equal(await fs.readFile(path.join(a.output, 'transcript.txt'), 'utf8'), text);
    });
    await t.test('two different concurrent saves have one winner and one retained conflict', async () => {
      const b = await fixture('b');
      const results = await Promise.allSettled([service.reviewSoapFacts(owner, b.id, b.input),
        service.reviewSoapFacts(owner, b.id, { ...b.input, decisions: [{ ...b.input.decisions[0], disposition: 'uncertain' }] })]);
      assert.equal(results.filter(x => x.status === 'fulfilled').length, 1);
      assert.equal(results.filter(x => x.status === 'rejected').length, 1);
      assert.match(results.find(x => x.status === 'rejected').reason.message, /already exists/);
      assert.equal((await service.soap(owner, b.id)).sections.S.facts.length, 0);
      assert.equal((await fs.readdir(b.dir)).filter(name => name.endsWith('.tmp')).length, 0);
    });
    await t.test('two same concurrent saves agree on immutable bytes', async () => {
      const c = await fixture('c');
      const results = await Promise.all([service.reviewSoapFacts(owner, c.id, c.input), service.reviewSoapFacts(owner, c.id, c.input)]);
      assert.equal(results[0].fact_review_sha256, results[1].fact_review_sha256);
    });
    await t.test('corrupt snapshot is not treated as absent or overwritten', async () => {
      const d = await fixture('d'); const file = path.join(d.dir, 'fact-review-v1.json');
      await fs.writeFile(file, '{broken');
      await assert.rejects(service.soap(owner, d.id), /unreadable/);
      await assert.rejects(service.reviewSoapFacts(owner, d.id, d.input), /unreadable/);
      assert.equal(await fs.readFile(file, 'utf8'), '{broken');
    });
    await t.test('changed original document invalidates saved review without erasure', async () => {
      await fs.writeFile(path.join(a.output, 'document.json'), JSON.stringify({ ...document, extra: 'changed original bytes' }));
      await assert.rejects(service.soap(owner, a.id), /exact original/);
      assert.equal(hash(await fs.readFile(path.join(a.dir, 'fact-review-v1.json'))), saved.fact_review_sha256);
    });
  } finally { await fs.rm(root, { recursive: true }); } // Exact mkdtemp test-owned synthetic directory only.
});
