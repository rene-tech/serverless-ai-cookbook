/* Actual TSX component + actual local service, with deterministic hook/request adapters.
 * Source event-wiring test, not a browser or deployed-image qualification. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const syncFs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const jsx = require('react/jsx-runtime');
const { renderToStaticMarkup } = require('react-dom/server');
const { hash } = require('./fact-review.cjs');

test('actual component controls persist rejection and gate exact-snapshot acknowledgement without modifying original output', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'clinical-fact-review-ui-'));
  process.env.SCIENTIFIC_DEMOS_DIR = root;
  const service = require('../demos/service.cjs');
  const owner = 'fixture-owner', id = 'a'.repeat(32), text = 'No fever. Which alternative? Yes.';
  const dir = path.join(root, hash(owner), id), output = path.join(dir, 'output');
  const facts = [['F0001', 0, 9], ['F0002', 10, text.length]].map(([factId, start, end]) => ({ id: factId,
    section: 'history', uncertain: false, source_attribution: 'patient_reported', source_attribution_extraction: 'patient_reported',
    source_attribution_review: 'patient_reported', source_phrases: [{ quote: text.slice(start, end), spans: [{ start, end }] }],
    review: { verdict: 'supported', reason: '<script>unverified interpretation</script>' } }));
  const document = { transcript_sha256: hash(text), facts, rejected: [] };
  try {
    await fs.mkdir(output, { recursive: true });
    await service.save(path.join(dir, 'request.json'), { kind: 'transcript', input_sha256: hash(text), report_model: 'fixture' });
    await service.save(path.join(dir, 'status.json'), { status: 'completed' });
    await fs.writeFile(path.join(output, 'document.json'), JSON.stringify(document));
    await fs.writeFile(path.join(output, 'transcript.txt'), text);
    const calls = [];
    const request = {
      get: async url => { calls.push(['GET', url]); assert.equal(url, `/api/scientific-demos/clinical/${id}/soap`); return service.soap(owner, id); },
      getResponse: async url => { calls.push(['GET_SOURCE', url]); assert.equal(url, `/api/scientific-demos/clinical/${id}/files/transcript.txt`); return { data: text }; },
      post: async (url, input) => {
        calls.push(['POST', url, structuredClone(input)]);
        if (url.endsWith('/fact-review')) return service.reviewSoapFacts(owner, id, input);
        assert.equal(url, `/api/scientific-demos/clinical/${id}/review`); return service.reviewSoap(owner, id, input);
      },
    };
    const states = []; let cursor = 0;
    const hooks = { useState(initial) { const slot = cursor++; if (!(slot in states)) states[slot] = initial;
      return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value; }]; } };
    const source = syncFs.readFileSync(path.join(__dirname, 'ClinicalSoap.tsx'), 'utf8');
    const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true }, reportDiagnostics: true });
    assert.equal((code.diagnostics || []).filter(x => x.category === ts.DiagnosticCategory.Error).length, 0);
    const module = { exports: {} };
    vm.runInNewContext(code.outputText, { exports: module.exports, module,
      require(name) { if (name === 'react') return hooks; if (name === 'react/jsx-runtime') return jsx;
        if (name === 'librechat-data-provider') return { request }; throw new Error('Unexpected import: ' + name); },
      URL, Blob, setTimeout, clearTimeout, console });
    const Component = module.exports.default;
    const render = () => { cursor = 0; return Component({ jobId: id }); };
    function nodes(value) {
      if (!value || typeof value !== 'object') return [];
      if (Array.isArray(value)) return value.flatMap(nodes);
      return [value, ...nodes(value.props?.children)];
    }
    const content = value => value == null || typeof value === 'boolean' ? '' : Array.isArray(value) ? value.map(content).join('')
      : typeof value === 'object' ? content(value.props?.children) : String(value);
    const find = predicate => { const found = nodes(render()).filter(predicate); assert.equal(found.length, 1); return found[0]; };
    const button = name => find(n => n.type === 'button' && content(n) === name);
    const control = label => find(n => n.props?.['aria-label'] === label);
    async function settle() { for (let i = 0; i < 50; i++) { await new Promise(resolve => setTimeout(resolve, 2)); if (!states[3]) return; } throw new Error('Unsettled local request'); }
    button('Open SOAP & task-handoff draft').props.onClick(); await settle();
    assert.equal(button('Record demo review — not clinical approval').props.disabled, true);
    assert.equal(button('Save immutable fact review').props.disabled, true);
    assert.match(renderToStaticMarkup(render()), /No complete fact review yet/);
    assert.ok(!renderToStaticMarkup(render()).includes('<script>'));
    assert.match(renderToStaticMarkup(render()), /&lt;script&gt;unverified interpretation/);
    button(`Original source 10–${text.length}`).props.onClick(); await settle();
    assert.ok(renderToStaticMarkup(render()).includes(`Transcript characters 10–${text.length}`));
    control('Demo reviewer kind').props.onChange({ target: { value: 'ai_engineering' } });
    control('Disposition for F0001').props.onChange({ target: { value: 'retain_for_demo' } });
    control('Reason for F0001').props.onChange({ target: { value: 'Literal source passage only; role unverified.' } });
    control('Disposition for F0002').props.onChange({ target: { value: 'reject' } });
    assert.equal(button('Save immutable fact review').props.disabled, true);
    control('Reason for F0002').props.onChange({ target: { value: 'Alternative and short answer unresolved; reject interpretation.' } });
    assert.equal(button('Save immutable fact review').props.disabled, false);
    button('Save immutable fact review').props.onClick(); await settle();
    const saved = await service.soap(owner, id);
    assert.equal(saved.sections.S.facts.length, 1); assert.equal(saved.sections.S.facts[0].id, 'F0001');
    assert.equal(saved.excluded_from_reviewed_projection[0].id, 'F0002');
    assert.equal(saved.fact_review.reviewer_kind, 'ai_engineering');
    assert.equal(control('Disposition for F0002').props.disabled, true);
    assert.equal(button('Save immutable fact review').props.disabled, true);
    assert.equal(button('Record demo review — not clinical approval').props.disabled, true);
    const checkbox = find(n => n.type === 'input' && n.props.type === 'checkbox');
    checkbox.props.onChange({ target: { checked: true } });
    assert.equal(button('Record demo review — not clinical approval').props.disabled, false);
    button('Record demo review — not clinical approval').props.onClick(); await settle();
    const final = await service.soap(owner, id);
    assert.equal(final.demo_review.fact_review_sha256, saved.fact_review_sha256);
    assert.equal(final.demo_review.reviewer_kind, 'ai_engineering'); assert.equal(final.clinical_signoff, false);
    assert.equal(final.human_review_required, true); assert.equal(final.handoff.length, 0);
    assert.equal(button('Record demo review — not clinical approval').props.disabled, true);
    assert.equal(calls.filter(call => call[0] === 'POST').length, 2);
    assert.equal(calls.find(call => call[1].endsWith('/fact-review'))[2].expected_review_sha256, null);
    assert.equal(await fs.readFile(path.join(output, 'document.json'), 'utf8'), JSON.stringify(document));
    assert.equal(await fs.readFile(path.join(output, 'transcript.txt'), 'utf8'), text);
  } finally { await fs.rm(root, { recursive: true }); } // Exact synthetic test-owned directory only.
});
