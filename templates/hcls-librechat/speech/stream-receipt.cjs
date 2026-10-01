/* Server-attested routing/audio hash only. No credential, audio or transcript payload. */
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const root = () => process.env.SCIENTIFIC_SPEECH_JOBS_DIR || '/data/hcls-speech';
function directory(owner) { if (!owner) throw new Error('Missing stream owner'); return path.join(root(), hash(owner), '_streams'); }
async function save(owner, value) {
  const id = crypto.randomUUID(); const dir = directory(owner);
  await fs.mkdir(dir, { recursive: true, mode: 0o700 });
  await fs.writeFile(path.join(dir, id + '.json'), JSON.stringify({ ...value, id, completed_at: new Date().toISOString() }), { flag: 'wx', mode: 0o600 });
  return id;
}
async function load(owner, id) {
  if (!/^[a-f0-9-]{36}$/.test(id || '')) throw new Error('Invalid completed stream receipt');
  return JSON.parse(await fs.readFile(path.join(directory(owner), id + '.json'), 'utf8'));
}
async function resolve(owner, id, credential, audio, model, platform, artifactBytes) {
  const receipt = await load(owner, id);
  if (receipt.schema !== 'scientific-clinical/paired-stream/v1' || receipt.key_hash !== hash(credential)
      || receipt.asr_model !== model || receipt.pcm_bytes !== audio.length - 44 || receipt.pcm_sha256 !== hash(audio.subarray(44))
      || receipt.diarization_model !== 'diar-streaming-sortformer-4spk-v2-1' || !/^[a-f0-9-]{36}$/.test(receipt.operation_id || '')) throw new Error('Captured audio, model or caller differs from the completed paired stream');
  const op = receipt.operation_id;
  const envelope = await platform(credential, 'GET', `/v1/operations/${op}`);
  const operation = envelope.operation && typeof envelope.operation === 'object' ? envelope.operation : envelope;
  if (operation.id !== op || operation.status !== 'succeeded' || operation.model_id !== receipt.diarization_model) throw new Error('Original diarization operation is not a matching successful result');
  const wrapped = await platform(credential, 'GET', `/v1/operations/${op}/result`);
  const wrappedOperation = wrapped.operation && typeof wrapped.operation === 'object' ? wrapped.operation : null;
  if (wrappedOperation && wrappedOperation.id !== op) throw new Error('Mismatched diarization result identity');
  let result = wrappedOperation ? wrapped.result : wrapped;
  if (result.schema === 'fs2-serve.nebius.ai/operation-artifact-result/v1') {
    const a = result.artifact || {};
    if (result.content_type !== 'application/json' || a.compression !== 'none' || !/^[a-f0-9-]{36}$/.test(a.artifact_id || '') || !Number.isInteger(a.size_bytes) || a.size_bytes < 0 || a.size_bytes > 8 * 1024 * 1024) throw new Error('Unsupported diarization result artifact');
    const bytes = await artifactBytes(credential, `/v1/artifacts/${a.artifact_id}/content`);
    if (bytes.length !== a.size_bytes || hash(bytes) !== a.sha256) throw new Error('Diarization artifact bytes do not match their identity');
    result = JSON.parse(bytes);
  }
  if (result.model !== receipt.diarization_model || !Array.isArray(result.events) || !Number.isFinite(result.audio_seconds)
      || Math.abs(result.audio_seconds - receipt.audio_seconds) > 0.001) throw new Error('Diarization result does not match captured stream');
  return { receipt, operation, result };
}
module.exports = { save, load, hash, resolve };
