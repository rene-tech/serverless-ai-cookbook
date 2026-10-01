/* Local lineage test only. Mocked ASR result and draft worker, never GPU evidence. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const checkpoint = '2a2b1cae8e96d62e83a82351f7d483df01fc28d1d64793ce45a5de514a6c3b5f';

test('selected medical App result retains exact checkpoint JSON through MCP transcript-input draft without new ASR', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'selected-speech-lineage-'));
  const owner = 'ordinary-fixture-user', key = 'ordinary-fixture-key';
  const operationId = '12345678-1234-4234-8234-123456789abc';
  const artifactId = '23456789-2345-4345-8345-23456789abcd';
  const publicModel = 'nemotron-speech-en-medical-0-6b';
  Object.assign(process.env, { SCIENTIFIC_DEMOS_DIR: path.join(root, 'jobs'),
    SCIENTIFIC_WORKSPACE: path.join(root, 'workspace'), NEBIUS_API_KEY: 'fixture-report-key',
    SCIENTIFIC_MODELS_API_BASE_URL: 'https://fixture.invalid/v1',
    SCIENTIFIC_CLINICAL_PYTHON: process.execPath,
    SCIENTIFIC_CLINICAL_SCRIPT: path.join(__dirname, '../demos/worker-fixture.cjs'),
    SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'platform',
    LIBRECHAT_USER_ID: owner, SCIENTIFIC_MODELS_API_KEY: key });
  for (const name of ['SCIENTIFIC_ENGLISH_SPEECH_URL', 'SCIENTIFIC_ENGLISH_SPEECH_API_KEY',
    'SCIENTIFIC_MEDICAL_SPEECH_URL', 'SCIENTIFIC_MEDICAL_SPEECH_API_KEY',
    'CLINICAL_REPORT_BASE_URL', 'CLINICAL_REPORT_API_KEY']) delete process.env[name];
  await fs.mkdir(process.env.SCIENTIFIC_WORKSPACE);
  const operation = { id: operationId, status: 'succeeded', model_id: publicModel,
    model_revision: 'sha256:' + checkpoint };
  // Native wire model is distinct from the public App identity. Real source:
  // speech-runtime/audio.py transcribe_file and server.py /generate response.
  const result = { text: 'Synthetic speaker says no fever. Full-source sentinel. '.repeat(2500),
    segments: [], audio_seconds: 5, processing_seconds: 1,
    model: 'nemotron-speech-en-0.6b', language: 'en-US', model_revision: 'sha256:' + checkpoint,
    runtime_identity: { checkpoint_sha256: checkpoint, checkpoint_kind: 'operator_pinned',
      parent_repository: 'nvidia/nemotron-speech-streaming-en-0.6b',
      parent_revision: 'ebe59e5a817142986528bbbee5dba8db7b38ed50',
      configured_max_sessions: 4, configured_max_batch_size: 4, capacity_status: 'fixture_not_measured' } };
  const bytes = Buffer.from(JSON.stringify(result));
  let corrupt = false;
  const calls = [], originalFetch = global.fetch;
  global.fetch = async (url, init) => {
    calls.push({ url, method: init.method });
    assert.equal(init.headers.Authorization, 'Bearer ' + key);
    assert.equal(init.method, 'GET', 'Retained-result-to-draft path must not submit new ASR');
    const resource = new URL(url).pathname;
    if (resource === `/v1/operations/${operationId}`) return Response.json(operation);
    if (resource === `/v1/operations/${operationId}/result`) return Response.json({
      schema: 'fs2-serve.nebius.ai/operation-artifact-result/v1', content_type: 'application/json',
      artifact: { artifact_id: artifactId, size_bytes: bytes.length, compression: 'none',
        sha256: corrupt ? '0'.repeat(64) : digest(bytes) } });
    if (resource === `/v1/artifacts/${artifactId}/content`) return new Response(bytes);
    throw new Error('Unexpected request: ' + resource);
  };
  try {
    const service = require('../demos/service.cjs');
    const mcp = require('../demos/mcp.cjs');
    const retained = await mcp.dispatch('workbench_get_operation_result', { operation_id: operationId });
    assert.equal(retained.operation.model_id, publicModel);
    assert.equal(retained.operation.model_revision, 'sha256:' + checkpoint);
    assert.equal(retained.workspace_file.sha256, digest(bytes));
    assert.deepEqual(await fs.readFile(retained.workspace_file.path), bytes);
    const saved = JSON.parse(await fs.readFile(retained.workspace_file.path));
    assert.equal(saved.runtime_identity.checkpoint_sha256, checkpoint);
    assert.equal(saved.text, result.text);
    const args = { workspace_path: retained.workspace_file.relative_path, language: 'en',
      idempotency_key: 'selected-parent-transcript-fixture' };
    const job = await mcp.dispatch('clinical_report_from_workspace', args);
    let completed;
    for (let attempt = 0; attempt < 200; attempt++) {
      completed = await service.status(owner, job.id);
      if (!['running', 'queued'].includes(completed.status)) break;
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    assert.equal(completed.status, 'completed');
    assert.equal(completed.input_provenance.kind, 'transcript');
    assert.equal(completed.input_provenance.asr_backend, undefined);
    assert.equal(completed.input_provenance.sha256, digest(bytes));
    assert.equal(completed.input_provenance.size_bytes, bytes.length);
    const requestDir = path.join(root, 'jobs', digest(owner), job.id);
    assert.deepEqual(await fs.readFile(path.join(requestDir, 'input.json')), bytes);
    const request = await service.read(path.join(requestDir, 'request.json'));
    assert.equal(request.source_workspace, retained.workspace_file.relative_path);
    assert.equal(request.kind, 'transcript');
    assert.equal(request.asr_backend, undefined);
    assert.equal((await mcp.dispatch('clinical_report_from_workspace', args)).id, job.id);
    await fs.writeFile(retained.workspace_file.path, JSON.stringify({ ...result, text: 'Changed source.' }));
    await assert.rejects(mcp.dispatch('clinical_report_from_workspace', args), /different input/);
    corrupt = true;
    await assert.rejects(mcp.dispatch('workbench_get_operation_result', { operation_id: operationId }), /SHA-256/);
    assert.equal(calls.length, 6);
    assert.ok(calls.every(call => call.method === 'GET'));
  } finally {
    global.fetch = originalFetch;
    // Only the exact fresh task-owned scratch path is removed.
    await fs.rm(root, { recursive: true, force: false });
  }
});
