const test = require('node:test');
const assert = require('node:assert/strict');
const deliver = require('./scientific-verified-delivery.cjs');
const name = 'deliver_scientific_results_mcp_environment-execution';
function messages(changes = {}) {
  return [{ getType: () => 'ai', tool_calls: [{ name, id: 'call-1' }] },
    { getType: () => 'tool', name, tool_call_id: 'call-1', content: JSON.stringify({
      schema: 'scientific-verified-delivery/v1', status: 'completed', inference_submitted: false,
      result_count: 1, report_markdown: 'Measured **31 atoms**. [Files](/demos?tab=workspace)', ...changes,
    }) }];
}
test('explicit delivery retains exact scientific facts and URLs', () => {
  assert.equal(deliver(messages()), 'Measured **31 atoms**. [Files](/demos?tab=workspace)');
});
test('intermediate, failed, pending, mismatched and parallel tools do not finish', () => {
  for (const changes of [{ status: 'running' }, { error: 'missing' }, { result_count: 0 },
    { schema: 'other' }, { report_markdown: '' }, { inference_submitted: true }]) {
    assert.equal(deliver(messages(changes)), null);
  }
  const wrong = messages(); wrong[1].tool_call_id = 'other';
  assert.equal(deliver(wrong), null);
  const parallel = messages(); parallel[0].tool_calls.push({ name: 'another', id: '2' });
  assert.equal(deliver(parallel), null);
  const intermediate = messages(); intermediate[1].name = 'read_execution_mcp_environment-execution';
  assert.equal(deliver(intermediate), null);
  const failed = messages(); failed[1].status = 'error'; assert.equal(deliver(failed), null);
});
test('never scans past a later customer message; exact host budget notice is transparent', () => {
  assert.equal(deliver([...messages(), { getType: () => 'human', content: 'Wait, also analyze this.' }]), null);
  const host = { getType: () => 'human', additional_kwargs: { role: 'system',
    source: 'scientific-step-budget', injected: true, isMeta: true,
    provenance: { version: 1, parts: [{ attribution: 'synthetic' }] } } };
  assert.equal(deliver([...messages(), host]), deliver(messages()));
});
test('patch keeps upstream event/persistence boundary, and fails closed on drift', async () => {
  const { patchVerifiedDelivery } = await import('./patch-agent-reliability.mjs');
  const input = "const studyAdmissionText = require('/opt/hcls-librechat/scientific-study-admission.cjs')(messages);\n" +
    'response_metadata: { scientific_admission_acknowledgement: true }';
  const output = patchVerifiedDelivery(input);
  assert.match(output, /scientific_verified_delivery/);
  assert.throws(() => patchVerifiedDelivery(output));
  assert.throws(() => patchVerifiedDelivery('different upstream'));
});
