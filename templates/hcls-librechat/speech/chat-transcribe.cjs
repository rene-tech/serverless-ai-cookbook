/* Real, typed MCP speech jobs. No LLM/report inside this tool and no audio-hash
 * result cache: each new request_id owns a fresh ASR session and receipt folder. */
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, execFile } = require('node:child_process');
const { promisify } = require('node:util');
const relay = require('./relay.cjs');
const service = require('../demos/service.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const read = async file => JSON.parse(await fs.readFile(file, 'utf8'));
const fail = (message, code, status = 400) => Object.assign(new Error(message), { status, code, retryable: false, durable_admission: false });
async function save(file, value) {
  const temp = file + '.' + crypto.randomUUID();
  await fs.writeFile(temp, JSON.stringify(value), { mode: 0o600 }); await fs.rename(temp, file);
}
async function processStart(pid) { return (await fs.readFile(`/proc/${pid}/stat`, 'utf8')).split(' ')[21]; }
async function alive(row) { try { return await processStart(row.pid) === row.process_start; } catch { return false; } }
async function admissionLock(root) {
  const child = spawn('flock', ['-x', '-w', '5', path.join(root, 'admission.lock'), 'sh', '-c', 'printf "ready\\n"; cat >/dev/null'],
    { stdio: ['pipe', 'pipe', 'ignore'] });
  await new Promise((resolve, reject) => {
    child.once('error', reject); child.once('exit', () => reject(fail('Speech admission is busy.', 'speech_admission_busy', 429)));
    child.stdout.once('data', resolve);
  });
  return () => new Promise(resolve => { child.once('exit', resolve); child.stdin.end(); });
}
async function launchWorker(dir, key) {
  const env = Object.fromEntries(Object.entries(process.env).filter(([name]) =>
    ['PATH', 'LANG', 'NODE_PATH', 'SCIENTIFIC_MODELS_API_BASE_URL', 'SCIENTIFIC_MODELS_MCP_URL', 'SCIENTIFIC_MODELS_API_KEY'].includes(name)
    || /^SCIENTIFIC_(ENGLISH|MEDICAL)_SPEECH_/.test(name)));
  env.SCIENTIFIC_MODELS_API_KEY = key;
  const child = spawn(process.execPath, [__filename, '--worker', dir], { env, detached: true, stdio: 'ignore' });
  await new Promise((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
  const identity = { pid: child.pid, process_start: await processStart(child.pid) };
  child.unref(); return identity;
}
function createService({ root = process.env.SCIENTIFIC_CHAT_SPEECH_DIR || '/data/hcls-chat-speech',
  workspace = process.env.SCIENTIFIC_WORKSPACE || '/workspace', platform = service.platform,
  workspaceGet = service.workspaceGet, targets = relay.targets, verifyIdentity = relay.verifyMedicalIdentity,
  digestFile = async file => require('./native-file.cjs').digestFile(file), launch = launchWorker,
  lock = admissionLock } = {}) {
  function directory(owner, id) {
    if (typeof owner !== 'string' || !owner || !/^[a-f0-9]{32}$/.test(id)) throw fail('Unknown speech run.', 'speech_run_not_found', 404);
    return path.join(root, hash(owner), id);
  }
  async function observe(owner, key, id, waitSeconds = 0, cached = false) {
    if (!Number.isInteger(waitSeconds) || waitSeconds < 0 || waitSeconds > 20) throw fail('wait_seconds must be 0–20.', 'speech_invalid_wait');
    const dir = directory(owner, id);
    const request = await read(path.join(dir, 'request.json')).catch(() => { throw fail('Speech run not found for this user.', 'speech_run_not_found', 404); });
    if (request.key_hash !== hash(key || '')) throw fail('Use the original submitting key.', 'speech_key_mismatch', 403);
    const deadline = Date.now() + waitSeconds * 1000;
    let state;
    do {
      state = await read(path.join(dir, 'status.json')).catch(() => ({ status: 'incomplete', error: 'Admission was interrupted; no automatic replay.' }));
      if (!['running', 'queued'].includes(state.status)) break;
      if (!await alive(state)) {
        const latest = await read(path.join(dir, 'status.json'));
        state = ['running', 'queued'].includes(latest.status) ? { ...latest, status: 'incomplete', error: 'Worker stopped; no automatic replay.' } : latest;
        break;
      }
      if (Date.now() >= deadline) break;
      await pause(Math.min(100, deadline - Date.now()));
    } while (true);
    const result = state.status === 'completed' ? await read(path.join(dir, 'result.json')) : {};
    return { run_id: id, request_id: request.request_id, model: request.model, model_id: request.model_id,
      status: state.status, cached: Boolean(cached && state.status === 'completed'),
      reused_result_from_another_request: false, ...result,
      elapsed_ms: Math.max(0, (state.finished_at ? Date.parse(state.finished_at) : Date.now()) - Date.parse(request.created_at)),
      ...(state.error ? { error: state.error, error_code: state.error_code || 'speech_processing_failed' } : {}),
      ...(['running', 'queued'].includes(state.status) ? { next_action: 'Call workbench_get_transcription with this same run_id. Do not submit again.' } : {}),
      clinical_validation: false };
  }
  async function submit(owner, key, args) {
    const deadline = Date.now() + 20000;
    if (!key || /\s/.test(key)) throw fail('Configure your Scientific AI key.', 'speech_key_missing', 401);
    if (!args || Object.keys(args).some(name => !['workspace_path', 'model', 'request_id'].includes(name))
      || !['english', 'medical', 'medical-speakers'].includes(args.model)
      || !/^[A-Za-z0-9_.:-]{1,100}$/.test(args.request_id || '')
      || typeof args.workspace_path !== 'string' || !args.workspace_path || args.workspace_path.length > 1024) {
      throw fail('Supply workspace_path, selected model and a unique request_id.', 'speech_invalid_request');
    }
    const normalized = args.workspace_path.replace(/^\/workspace\//, '');
    const file = await workspaceGet(key, normalized);
    const actual = await fs.realpath(file.absolute), boundary = await fs.realpath(workspace);
    if (!actual.startsWith(boundary + path.sep)) throw fail('Audio must stay inside this workspace.', 'speech_workspace_escape', 403);
    const stat = await fs.stat(actual);
    if (!stat.isFile() || !stat.size || stat.size > 64 * 1024 * 1024 || !/\.(wav|mp3|m4a|flac|ogg|webm)$/i.test(actual)) {
      throw fail('Use one workspace audio file up to 64 MB.', 'speech_invalid_audio');
    }
    const sourceHash = await digestFile(actual), id = hash(args.request_id).slice(0, 32), dir = directory(owner, id);
    const identity = hash(JSON.stringify([normalized, sourceHash, args.model, hash(key)]));
    await fs.mkdir(path.join(root, 'slots'), { recursive: true, mode: 0o700 });
    const unlock = await lock(root);
    let existing = false;
    try {
      const previous = await read(path.join(dir, 'request.json')).catch(() => null);
      if (previous) {
        if (previous.identity !== identity) throw fail('request_id already belongs to different input. Use a new ID for a new action.', 'speech_request_conflict', 409);
        existing = true;
      } else {
        const choices = targets(), target = choices[args.model];
        if (!target) throw fail('This speech model is not configured.', 'speech_not_configured', 503);
        relay.socketUrl(target.url);
        relay.targetCredential(target, key);
        const catalog = await platform(key, 'GET', '/v1/models', undefined, undefined, 5000);
        const allowed = new Set((catalog.data || []).map(row => row.id || row.model_id));
        if ((!target.dedicated || args.model === 'english') && !allowed.has(target.id)) throw fail('Your key does not grant this speech model.', 'speech_not_authorized', 403);
        if (target.diarization && !allowed.has(target.diarization.id)) throw fail('Your key does not grant Sortformer.', 'speech_not_authorized', 403);
        await verifyIdentity(target);
        const slots = [];
        for (const name of await fs.readdir(path.join(root, 'slots'))) {
          if (!/^[a-f0-9]{64}-[a-f0-9]{32}\.json$/.test(name)) continue;
          const slot = path.join(root, 'slots', name), row = await read(slot);
          if (await alive(row)) slots.push(row); else await fs.unlink(slot);
        }
        if (slots.length >= 16 || slots.filter(row => row.owner_hash === hash(owner)).length >= 2) throw fail('Speech is busy; wait for an active run to finish.', 'speech_capacity_busy', 429);
        await fs.mkdir(path.dirname(dir), { recursive: true, mode: 0o700 }); await fs.mkdir(dir, { mode: 0o700 });
        const source = 'source' + path.extname(actual).toLowerCase();
        await fs.copyFile(actual, path.join(dir, source)); await fs.chmod(path.join(dir, source), 0o600);
        if (await digestFile(path.join(dir, source)) !== sourceHash) throw fail('Audio changed during capture; no inference was started.', 'speech_source_changed', 409);
        const request = { request_id: args.request_id, identity, key_hash: hash(key), owner_hash: hash(owner),
          source, source_sha256: sourceHash, workspace_path: normalized, model: args.model, model_id: target.id,
          expected_checkpoint: target.expectedCheckpoint || null, created_at: new Date().toISOString(),
          backend: { url: relay.socketUrl(target.url), model: target.wireModel || target.id },
          automatic_replay: false };
        await save(path.join(dir, 'request.json'), request);
        // Credentials are inherited in the detached worker environment, never
        // written into request/result files or returned to the agent.
        const worker = await launch(dir, key);
        await save(path.join(root, 'slots', `${hash(owner)}-${id}.json`), { ...worker, owner_hash: hash(owner) });
        await save(path.join(dir, 'status.json'), { ...worker, status: 'running' });
        await fs.writeFile(path.join(dir, 'launched'), '', { mode: 0o600 });
      }
    } finally { await unlock(); }
    return observe(owner, key, id, Math.max(0, Math.floor((deadline - Date.now()) / 1000)), existing);
  }
  return { submit, observe };
}

async function executeAudio(dir, request, { transcribe = options => require('./native-file.cjs').transcribeFile(options),
  convert, diarize, env = process.env } = {}) {
  const target = relay.targets(env)[request.model], credential = relay.targetCredential(target, env.SCIENTIFIC_MODELS_API_KEY);
  if (target.id !== request.model_id || relay.socketUrl(target.url) !== request.backend.url
    || (target.expectedCheckpoint || null) !== request.expected_checkpoint) throw new Error('speech_backend_changed');
  const audio = path.join(dir, 'input.wav');
  let decodedDuration;
  if (convert) {
    const measured = await convert(path.join(dir, request.source), audio);
    decodedDuration = typeof measured === 'number' ? measured : measured?.audio_seconds;
  }
  else {
    await promisify(execFile)('ffmpeg', ['-nostdin', '-hide_banner', '-loglevel', 'error', '-protocol_whitelist', 'file,pipe',
      '-i', path.join(dir, request.source), '-t', '601', '-vn', '-ac', '1', '-ar', '16000', audio], { timeout: 20000, maxBuffer: 65536 });
    const { stdout } = await promisify(execFile)('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio], { timeout: 5000 });
    decodedDuration = Number(stdout);
  }
  if (!Number.isFinite(decodedDuration) || decodedDuration <= 0 || decodedDuration > 600) throw new Error('speech_audio_duration_limit');
  const controller = new AbortController(), abort = () => controller.abort();
  process.once('SIGTERM', abort); process.once('SIGINT', abort);
  try {
    // Validate the loaded checkpoint before native-file sends any PCM.
    const WebSocket = require('/app/node_modules/ws');
    let operationId = null;
    class CheckedSocket extends WebSocket {
      emit(name, ...values) {
        if (name === 'message') {
          try {
            const event = JSON.parse(values[0]);
            if (event.operation_id) operationId = event.operation_id;
            if (event.type === 'session.ready') relay.verifyRuntimeIdentity(target, event);
          }
          catch { values = [Buffer.from('{"type":"session.error","code":"speech_checkpoint_mismatch"}')]; }
        }
        return super.emit(name, ...values);
      }
    }
    const result = await transcribe({ source: audio, directory: path.join(dir, 'asr'), backend: request.backend,
      credential, signal: controller.signal, deadlineMs: 180000, connect: (url, options) => new CheckedSocket(url, options) });
    const asr = await read(result.path);
    const runtimeDurationKnown = Number.isFinite(asr.audio_seconds);
    if (runtimeDurationKnown && Math.abs(asr.audio_seconds - decodedDuration) > .01) throw new Error('speech_audio_duration_mismatch');
    const audioSeconds = runtimeDurationKnown ? asr.audio_seconds : decodedDuration;
    const durationSource = runtimeDurationKnown ? 'runtime_checked_against_decoded_input' : 'decoded_input_ffprobe';
    let speakers;
    if (request.model === 'medical-speakers') {
      if (!asr.words?.length) throw new Error('speech_acoustic_words_missing');
      const speakerDir = path.join(dir, 'speakers'); await fs.mkdir(speakerDir, { mode: 0o700 });
      await fs.copyFile(audio, path.join(speakerDir, 'input.wav'));
      await save(path.join(speakerDir, 'request.json'), { id: path.basename(dir), words: asr.words, asr_model: request.model_id,
        audio_seconds: audioSeconds, duration_source: durationSource });
      if (diarize) speakers = await diarize(speakerDir);
      else {
        await promisify(execFile)('/opt/scientific-client/bin/python', [path.join(__dirname, 'speaker-finalize.py'), speakerDir],
          { timeout: 180000, maxBuffer: 65536, env });
        speakers = await read(path.join(speakerDir, 'result.json'));
      }
    }
    return { text: asr.text, ...(speakers ? { turns: speakers.turns, diarization_operation_id: speakers.operation_id } : {}),
      session_id: asr.runtime_session_id || null, operation_id: operationId || asr.platform_operation_id || null,
      audio_seconds: audioSeconds, duration_source: durationSource, source_sha256: request.source_sha256,
      checkpoint_sha256: request.expected_checkpoint, transport: 'fresh-file-over-native-websocket' };
  } finally { process.removeListener('SIGTERM', abort); process.removeListener('SIGINT', abort); }
}
async function worker(dir) {
  for (let i = 0; i < 100; i++) {
    if (await fs.access(path.join(dir, 'launched')).then(() => true, () => false)) break;
    if (i === 99) return;
    await pause(100);
  }
  const request = await read(path.join(dir, 'request.json'));
  const state = await read(path.join(dir, 'status.json'));
  try {
    const result = await executeAudio(dir, request);
    await save(path.join(dir, 'result.json'), result);
    await save(path.join(dir, 'status.json'), { ...state, status: 'completed', finished_at: new Date().toISOString() });
  } catch (error) {
    const safeCodes = new Set(['speech_backend_changed', 'speech_audio_duration_limit', 'speech_audio_duration_mismatch', 'speech_acoustic_words_missing',
      'native_asr_decode_failed', 'native_asr_audio_limit', 'native_asr_deadline_admission_unknown',
      'native_asr_transport_error_admission_unknown', 'native_asr_disconnect_admission_unknown',
      'native_asr_speech_checkpoint_mismatch', 'native_asr_unfinalized_partial', 'ENOENT', 'ETIMEDOUT']);
    const code = safeCodes.has(error.code) ? error.code : safeCodes.has(error.message) ? error.message : 'speech_processing_failed';
    const name = ['Error', 'TypeError', 'SyntaxError', 'RangeError', 'AbortError', 'TimeoutError'].includes(error.name) ? error.name : 'Error';
    await save(path.join(dir, 'failure.json'), { code, name, recorded_at: new Date().toISOString(),
      ...(Number.isInteger(error.code) ? { child_exit_code: error.code } : {}),
      child_killed: Boolean(error.killed), raw_message_retained: false });
    const detail = ['speech_audio_duration_limit', 'native_asr_audio_limit'].includes(code)
      ? 'Audio must be at most 10 minutes. Upload a shorter clip and submit a new request.'
      : code === 'speech_acoustic_words_missing'
        ? 'ASR returned no acoustic word timestamps. Speaker attribution cannot be produced from this run.'
        : code === 'native_asr_decode_failed'
          ? 'The audio could not be decoded. Upload a valid WAV, MP3, M4A, FLAC, OGG or WebM file.'
          : 'Speech processing did not complete. Original run retained; no automatic replay or model substitution.';
    await save(path.join(dir, 'status.json'), { ...state, status: 'failed', finished_at: new Date().toISOString(),
      error: detail, error_code: code });
  } finally {
    await fs.unlink(path.join(path.resolve(dir, '../..'), 'slots', `${request.owner_hash}-${path.basename(dir)}.json`)).catch(() => {});
  }
}
const instance = createService();
module.exports = { createService, executeAudio, submit: instance.submit, observe: instance.observe };
if (require.main === module && process.argv[2] === '--worker') worker(process.argv[3]).catch(() => { process.exitCode = 1; });
