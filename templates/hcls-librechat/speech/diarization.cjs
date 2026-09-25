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
function installRoutes(router, { key }) {
  const upload = multer({ dest: os.tmpdir(), limits: { fileSize: 20 * 1024 * 1024, files: 1, fields: 4, fieldSize: 2 * 1024 * 1024 } });
  const wrap = (handler) => (req, res, next) => Promise.resolve(handler(req, res)).catch(next);
  router.post('/speech/diarization', upload.single('file'), wrap(async (req, res) => {
    if (!req.file) throw fail('Attach captured mono PCM WAV audio.');
    try {
      const credential = await key(req);
      if (!credential) throw fail('Configure your Scientific AI key.', 401);
      if (!/^[A-Za-z0-9_.:-]{1,100}$/.test(req.body.idempotency_key || '')) throw fail('Supply a request identity.');
      const words = JSON.parse(req.body.words || '[]');
      if (!Array.isArray(words) || !words.length || words.length > 20000) throw fail('Actual acoustic word timestamps are required.');
      const bytes = await fs.readFile(req.file.path);
      if (bytes.length < 46 || bytes.toString('ascii', 0, 4) !== 'RIFF' || bytes.toString('ascii', 8, 12) !== 'WAVE' || bytes.readUInt16LE(20) !== 1 || bytes.readUInt16LE(22) !== 1 || bytes.readUInt32LE(24) !== 16000 || bytes.readUInt16LE(34) !== 16 || bytes.readUInt32LE(40) !== bytes.length - 44) throw fail('Expected exact captured 16 kHz mono PCM16 WAV.');
      const id = hash(req.body.idempotency_key).slice(0, 32); const dir = directory(req.user.id, id);
      const identity = hash(JSON.stringify([hash(bytes), words, req.body.model, hash(credential)]));
      await fs.mkdir(path.dirname(dir), { recursive: true, mode: 0o700 });
      try {
        await fs.mkdir(dir, { mode: 0o700 });
        await fs.writeFile(path.join(dir, 'input.wav'), bytes, { mode: 0o600 });
        await save(path.join(dir, 'request.json'), { id, identity, words, asr_model: req.body.model,
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
module.exports = { installRoutes };
