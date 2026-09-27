/* User-scoped durable post-stop speaker jobs; exact WAV + actual ASR timings. */
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const multer = require('/app/node_modules/multer');
const os = require('node:os');
const root = process.env.SCIENTIFIC_SPEECH_JOBS_DIR || '/data/hcls-speech';
const hash = (value) => crypto.createHash('sha256').update(value).digest('hex');
const fail = (text, status = 400) => Object.assign(new Error(text), { status });
const reading = async (file) => JSON.parse(await fs.readFile(file, 'utf8'));
const pending = new Set();
function sourceReceipt(value) {
  if (!value || value.schema !== 'scientific-clinical/browser-asr-source/v1' || typeof value.raw_transcript !== 'string' || !value.raw_transcript.trim() || value.raw_transcript.length > 500000 || !Array.isArray(value.segments) || !value.segments.length || value.segments.length > 20000 || value.segments.some(item => typeof item.id !== 'string' || typeof item.text !== 'string' || item.final !== true || !Number.isFinite(item.revision))) throw fail('Completed raw ASR source evidence is required.');
  if (value.segments.map(item => item.text).join('').trim() !== value.raw_transcript) throw fail('Raw ASR segments do not match the source transcript.');
  const timings = value.timings;
  if (!timings || !['ready_at', 'audio_start_at', 'input_end_at', 'completed_at'].every(name => typeof timings[name] === 'string' && Number.isFinite(Date.parse(timings[name])))) throw fail('Completed browser timing evidence is required.');
  return value;
}
async function save(file, value) {
  const temporary = `${file}.${crypto.randomUUID()}.tmp`;
  await fs.writeFile(temporary, JSON.stringify(value), { mode: 0o600 }); await fs.rename(temporary, file);
}
function directory(owner, id) {
  if (!owner || !/^[a-f0-9]{32}$/.test(id)) throw fail('Invalid speaker job');
  return path.join(root, hash(owner), id);
}
async function status(owner, id) {
  const dir = directory(owner, id);
  const result = await reading(path.join(dir, 'result.json')).catch(() => null);
  const receipt = await reading(path.join(dir, 'status.json')).catch(() => ({ state: 'prepared' }));
  if (result) return { id, state: 'completed', result };
  const state = receipt.state === 'running' && !pending.has(dir) ? 'interrupted' : receipt.state;
  return { id, state, error: receipt.error };
}
async function run(owner, credential, id) {
  const dir = directory(owner, id);
  const request = await reading(path.join(dir, 'request.json'));
  if (request.key_hash !== hash(credential || '')) throw fail('Use the original submitting key.', 403);
  if (pending.has(dir) || (await status(owner, id)).state === 'completed') return status(owner, id);
  if ([...pending].some((item) => path.dirname(item) === path.dirname(dir))) throw fail('A speaker job is already running for this account.', 429);
  pending.add(dir);
  await save(path.join(dir, 'status.json'), { state: 'running' });
  const child = spawn('/opt/scientific-client/bin/python', ['/opt/hcls-librechat/speech/speaker-finalize.py', dir], {
    stdio: 'ignore', env: { PATH: process.env.PATH, LANG: 'C.UTF-8',
      SCIENTIFIC_MODELS_API_KEY: credential,
      SCIENTIFIC_MODELS_API_BASE_URL: process.env.SCIENTIFIC_MODELS_API_BASE_URL || 'https://89.169.99.188/v1',
      SCIENTIFIC_MODELS_MCP_URL: process.env.SCIENTIFIC_MODELS_MCP_URL || 'https://89.169.99.188/mcp' },
  });
  const finish = async (code) => { pending.delete(dir); await save(path.join(dir, 'status.json'), {
    state: code === 0 ? 'completed' : code === 75 ? 'pending' : 'incomplete',
    ...(code && code !== 75 ? { error: 'Speaker processing incomplete. Resume the same job; original inputs and receipts are retained.' } : {}),
  }); };
  child.once('error', () => void finish(1)); child.once('exit', (code) => void finish(code ?? 1));
  return { id, state: 'running' };
}
function installRoutes(router, { key, platform, artifactBytes }) {
  const upload = multer({ dest: os.tmpdir(), limits: { fileSize: 20 * 1024 * 1024, files: 1, fields: 6, fieldSize: 2 * 1024 * 1024 } });
  const wrap = (handler) => (req, res, next) => Promise.resolve(handler(req, res)).catch(next);
  router.post('/speech/diarization', upload.single('file'), wrap(async (req, res) => {
    if (!req.file) throw fail('Attach captured mono PCM WAV audio.');
    try {
      const credential = await key(req);
      if (!credential) throw fail('Configure your Scientific AI key.', 401);
      if (!/^[A-Za-z0-9_.:-]{1,100}$/.test(req.body.idempotency_key || '')) throw fail('Supply a request identity.');
      const words = JSON.parse(req.body.words || '[]');
      if (!Array.isArray(words) || !words.length || words.length > 20000) throw fail('Actual acoustic word timestamps are required.');
      const source = sourceReceipt(JSON.parse(req.body.source_receipt || 'null'));
      const bytes = await fs.readFile(req.file.path);
      if (bytes.length < 46 || bytes.toString('ascii', 0, 4) !== 'RIFF' || bytes.toString('ascii', 8, 12) !== 'WAVE' || bytes.readUInt16LE(20) !== 1 || bytes.readUInt16LE(22) !== 1 || bytes.readUInt32LE(24) !== 16000 || bytes.readUInt16LE(34) !== 16 || bytes.readUInt32LE(40) !== bytes.length - 44) throw fail('Expected exact captured 16 kHz mono PCM16 WAV.');
      const id = hash(req.body.idempotency_key).slice(0, 32); const dir = directory(req.user.id, id);
      const streamReceipt = req.body.stream_receipt || null;
      const identity = hash(JSON.stringify([hash(bytes), words, req.body.model, hash(credential), source, ...(streamReceipt ? [streamReceipt] : [])]));
      const existing = await reading(path.join(dir, 'request.json')).catch(() => null);
      if (existing) {
        if (existing.identity !== identity) throw fail('Request belongs to different input. Retry unchanged.', 409);
        res.status(202).json(await run(req.user.id, credential, id)); return;
      }
      // Fetch the exact completed stream result with the same ordinary key.
      // Any lookup/mismatch fails closed; never fall back to another inference.
      const streamed = streamReceipt ? await require('./stream-receipt.cjs').resolve(req.user.id,
        streamReceipt, credential, bytes, req.body.model, platform, artifactBytes) : null;
      await fs.mkdir(path.dirname(dir), { recursive: true, mode: 0o700 });
      try {
        await fs.mkdir(dir, { mode: 0o700 });
        await fs.writeFile(path.join(dir, 'input.wav'), bytes, { mode: 0o600 });
        if (streamed) await save(path.join(dir, 'streamed-diarization.json'), streamed);
        await save(path.join(dir, 'request.json'), { id, identity, words, asr_model: req.body.model,
          audio_sha256: hash(bytes), source_receipt: source,
          asr_runtime: streamed ? streamed.receipt.asr_runtime : (source.timings.model_identity || null),
          asr_runtime_identity_origin: streamed ? streamed.receipt.asr_runtime_identity_origin : 'Browser-captured relay runtime identity; not an independently signed attestation.',
          ...(streamed ? { stream_operation_id: streamed.receipt.operation_id, stream_receipt: streamReceipt,
            streamed_result_sha256: hash(JSON.stringify(streamed)) } : {}),
          key_hash: hash(credential), audio_seconds: (bytes.length - 44) / 32000 });
      } catch (error) {
        if (error.code !== 'EEXIST') throw error;
        const previous = await reading(path.join(dir, 'request.json')).catch(() => null);
        if (previous?.identity !== identity) throw fail('Request is being admitted or belongs to different input. Retry unchanged.', 409);
      }
      res.status(202).json(await run(req.user.id, credential, id));
    } finally { await fs.unlink(req.file.path).catch(() => {}); }
  }));
  router.get('/speech/diarization/:id', wrap(async (req, res) => {
    await fs.access(path.join(directory(req.user.id, req.params.id), 'request.json')).catch(() => { throw fail('Speaker job not found.', 404); });
    res.json(await status(req.user.id, req.params.id));
  }));
  router.post('/speech/diarization/:id/resume', wrap(async (req, res) => res.json(await run(req.user.id, await key(req), req.params.id))));
}
async function reviewSource(owner, id) {
  const dir = directory(owner, id);
  const requestBytes = await fs.readFile(path.join(dir, 'request.json')).catch(() => { throw fail('Speaker job not found for this account.', 404); });
  const request = JSON.parse(requestBytes);
  const resultBytes = await fs.readFile(path.join(dir, 'result.json')).catch(() => { throw fail('Complete the owned speaker job before generating a live reviewed draft.', 409); });
  const result = JSON.parse(resultBytes);
  const source = sourceReceipt(request.source_receipt);
  const audioHash = hash(await fs.readFile(path.join(dir, 'input.wav')));
  if (audioHash !== request.audio_sha256 || !Array.isArray(request.words) || !request.words.length || !Array.isArray(result.turns) || !result.turns.length || !Array.isArray(result.words) || !result.words.length) throw fail('Speaker source evidence is incomplete or changed.', 409);
  return { speaker_job: id, audio_sha256: audioHash, speaker_request_sha256: hash(requestBytes),
    raw_asr_transcript_sha256: hash(source.raw_transcript), acoustic_words_sha256: hash(JSON.stringify(request.words)),
    browser_source_receipt_sha256: hash(JSON.stringify(source)), browser_timings: source.timings,
    source_evidence_origin: 'Browser-captured ASR output; immutable after speaker job admission, not server-attested clinical evidence.',
    speaker_result_sha256: hash(resultBytes), asr_model: request.asr_model, asr_runtime: request.asr_runtime || null,
    diarization_operation_id: result.operation_id,
    anonymous_transcript_sha256: hash(result.turns.map((turn) => `[${turn.speaker}] ${turn.text}`).join('\n')) };
}
module.exports = { installRoutes, reviewSource, sourceReceipt };
