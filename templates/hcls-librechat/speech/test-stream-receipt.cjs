const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { save, resolve, hash } = require('./stream-receipt.cjs');
test('paired receipt is caller/audio/model bound and resumes only the original successful operation', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'speech-stream-test-')); process.env.SCIENTIFIC_SPEECH_JOBS_DIR = root;
  const pcm = Buffer.alloc(3200, 3), wav = Buffer.concat([Buffer.alloc(44), pcm]);
  const operation = '243236ef-8af2-4dc6-85a4-c504b68c1b52', model = 'diar-streaming-sortformer-4spk-v2-1';
  const receipt = { schema: 'scientific-clinical/paired-stream/v1', asr_model: 'medical', diarization_model: model,
    operation_id: operation, key_hash: hash('ordinary'), pcm_sha256: hash(pcm), pcm_bytes: pcm.length, audio_seconds: .1 };
  const calls = [];
  const result = { model, audio_seconds: .1, events: [{ type: 'speaker.activity' }] };
  let envelope = result, status = 'succeeded', wrappedStatus = false;
  const platform = async (key, method, url) => {
    assert.equal(key, 'ordinary'); assert.equal(method, 'GET'); calls.push(url);
    const value = { id: operation, operation: 'diarize', status, model_id: model };
    return url.endsWith('/result') ? envelope : wrappedStatus ? { operation: value } : value;
  };
  try {
    const id = await save('owner', receipt);
    assert.deepEqual((await resolve('owner', id, 'ordinary', wav, 'medical', platform)).result, result);
    wrappedStatus = true; envelope = { operation: { id: operation }, result };
    assert.deepEqual((await resolve('owner', id, 'ordinary', wav, 'medical', platform)).result, result);
    envelope = { ...result, operation: 'diarize' }; wrappedStatus = false;
    assert.deepEqual((await resolve('owner', id, 'ordinary', wav, 'medical', platform)).result, envelope);
    envelope = { operation: { id: '9'.repeat(36) }, result };
    await assert.rejects(resolve('owner', id, 'ordinary', wav, 'medical', platform), /Mismatched/);
    envelope = result;
    assert.deepEqual((await resolve('owner', id, 'ordinary', wav, 'medical', platform)).result, result);
    assert.ok(calls.every(url => url.startsWith(`/v1/operations/${operation}`)));
    for (const args of [['other', id, 'ordinary', wav, 'medical'], ['owner', id, 'changed', wav, 'medical'], ['owner', id, 'ordinary', Buffer.alloc(wav.length), 'medical'], ['owner', id, 'ordinary', wav, 'other-model']]) {
      await assert.rejects(resolve(...args, platform));
    }
    status = 'failed'; await assert.rejects(resolve('owner', id, 'ordinary', wav, 'medical', platform), /successful/); status = 'succeeded';
    const bytes = Buffer.from(JSON.stringify(result));
    envelope = { schema: 'fs2-serve.nebius.ai/operation-artifact-result/v1', content_type: 'application/json', artifact: {
      artifact_id: '009ac735-c929-4298-a9c5-c94a0617ef96', compression: 'none', size_bytes: bytes.length, sha256: hash(bytes) } };
    const artifactBytes = async (key, url) => { assert.equal(key, 'ordinary'); assert.equal(url, '/v1/artifacts/009ac735-c929-4298-a9c5-c94a0617ef96/content'); return bytes; };
    assert.deepEqual((await resolve('owner', id, 'ordinary', wav, 'medical', platform, artifactBytes)).result, result);
    await assert.rejects(resolve('owner', id, 'ordinary', wav, 'medical', platform, async () => Buffer.from('bad')), /identity/);
  } finally { delete process.env.SCIENTIFIC_SPEECH_JOBS_DIR; await fs.rm(root, { recursive: true, force: true }); }
});
