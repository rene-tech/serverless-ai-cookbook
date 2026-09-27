/* File-over-native-WebSocket ASR. This is unpaced batch transport, not live latency. */
const fs = require('node:fs/promises');
const { createReadStream } = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
// Detached report workers have a deliberately minimal environment: do not
// depend on an interactive NODE_PATH for the exact installed LibreChat SDK.
const WebSocket = require('/app/node_modules/ws');
const { socketUrl } = require('./relay.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const failure = code => Object.assign(new Error(code), { code });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function digestFile(file) {
  const result = crypto.createHash('sha256');
  for await (const bytes of createReadStream(file)) result.update(bytes);
  return result.digest('hex');
}
async function exclusive(file, value) {
  await fs.writeFile(file, JSON.stringify(value, null, 2), { flag: 'wx', mode: 0o600 });
}
async function transcribeFile({ source, directory, backend, credential, signal,
  connect = (url, options) => new WebSocket(url, options), deadlineMs = 1800000 }) {
  const url = socketUrl(backend.url);
  if (!credential || /\s/.test(credential)) throw failure('native_asr_credential_missing');
  const sourceHash = await digestFile(source);
  const config = { schema: 'native-file-asr/v1', source_sha256: sourceHash,
    source_bytes: (await fs.stat(source)).size, ...backend,
    transport: 'unpaced-file-over-native-websocket', max_audio_seconds: 1800,
    audio: { encoding: 'pcm_s16le', sample_rate_hz: 16000, channels: 1 } };
  await fs.mkdir(directory, { recursive: true, mode: 0o700 });
  const requestPath = path.join(directory, 'request.json');
  const resultPath = path.join(directory, 'result.json');
  const receiptPath = path.join(directory, 'receipt.json');
  try {
    await exclusive(requestPath, { config, started_at: new Date().toISOString(), admission: 'unknown_until_terminal_receipt', automatic_replay: false });
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const previous = JSON.parse(await fs.readFile(requestPath, 'utf8'));
    if (JSON.stringify(previous.config) !== JSON.stringify(config)) throw failure('native_asr_source_or_backend_changed');
    try {
      const receipt = JSON.parse(await fs.readFile(receiptPath, 'utf8'));
      const bytes = await fs.readFile(resultPath);
      if (receipt.status !== 'completed' || hash(bytes) !== receipt.result_sha256) throw failure('native_asr_saved_result_invalid');
      return { path: resultPath, receipt, cached: true };
    } catch { throw failure('native_asr_admission_unknown_no_automatic_replay'); }
  }
  const { transcriptEvent, transcriptText, acousticWords } = await import('./speech-state.js');
  const segments = new Map(), words = new Map();
  let ws, decoder, session, completed, audioBytes = 0, eventBytes = 0, eventCount = 0;
  const eventFile = path.join(directory, 'events.jsonl');
  const events = await fs.open(eventFile, 'wx', 0o600);
  let recording = Promise.resolve();
  const record = event => {
    const line = JSON.stringify({ observed_at: new Date().toISOString(), event }) + '\n';
    eventBytes += Buffer.byteLength(line); eventCount++;
    if (eventBytes > 32 * 1024 * 1024 || eventCount > 75000) throw failure('native_asr_event_limit');
    recording = recording.then(() => events.write(line));
  };
  const send = bytes => new Promise((resolve, reject) => {
    if (ws.readyState !== WebSocket.OPEN) return reject(failure('native_asr_socket_closed'));
    ws.send(bytes, error => error ? reject(failure('native_asr_send_failed')) : resolve());
  });
  try {
    await new Promise((resolve, reject) => {
      let settled = false, ready = false;
      const finish = error => { if (!settled) { settled = true; clearTimeout(timer); signal?.removeEventListener('abort', abort); error ? reject(error) : resolve(); } };
      const abort = () => finish(failure('native_asr_cancelled_admission_unknown'));
      const timer = setTimeout(() => finish(failure('native_asr_deadline_admission_unknown')), deadlineMs);
      signal?.addEventListener('abort', abort, { once: true });
      if (signal?.aborted) return abort();
      ws = connect(url, { headers: { Authorization: 'Bearer ' + credential }, maxPayload: 65536, handshakeTimeout: 20000, followRedirects: false });
      ws.on('error', () => finish(failure('native_asr_transport_error_admission_unknown')));
      ws.on('close', () => { if (!completed) finish(failure('native_asr_disconnect_admission_unknown')); });
      ws.on('open', () => send(JSON.stringify({ type: 'session.start', options: { model: backend.model,
        language: 'en-US', output_granularity: 'word' }, audio: config.audio })).catch(finish));
      ws.on('message', data => {
        if (settled) return;
        try {
          const event = JSON.parse(data.toString()); record(event);
          if (event.session_id) session = event.session_id;
          if (event.type === 'session.error') throw failure('native_asr_' + (event.code || 'runtime_error'));
          if (event.type === 'transcript.partial' || event.type === 'transcript.final') {
            transcriptEvent(segments, event);
            if (event.type === 'transcript.final') words.set(String(event.segment_id ?? event.sequence), acousticWords(event));
          }
          if (event.type === 'session.ready') {
            if (ready) throw failure('native_asr_duplicate_ready');
            ready = true;
            void (async () => {
              decoder = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe',
                '-i', source, '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', 'pipe:1'], { stdio: ['ignore', 'pipe', 'ignore'] });
              const exit = new Promise((yes, no) => { decoder.once('error', () => no(failure('native_asr_decode_failed'))); decoder.once('close', yes); });
              void exit.catch(() => {});
              let carry = Buffer.alloc(0);
              for await (const chunk of decoder.stdout) {
                const joined = Buffer.concat([carry, chunk]);
                const pcm = joined.subarray(0, joined.length - joined.length % 2);
                carry = joined.subarray(pcm.length);
                for (let offset = 0; offset < pcm.length; offset += 3200) {
                  if (settled) throw failure('native_asr_stopped');
                  const frame = pcm.subarray(offset, offset + 3200);
                  audioBytes += frame.length;
                  if (audioBytes > 1800 * 32000) throw failure('native_asr_audio_limit');
                  while (ws.bufferedAmount > 256000 && !settled) await pause(5);
                  await send(frame);
                }
              }
              if (await exit !== 0 || !audioBytes || carry.length) throw failure('native_asr_decode_failed');
              record({ type: 'client.input.finish', audio_bytes: audioBytes });
              await send(JSON.stringify({ type: 'input.finish' }));
            })().catch(finish);
          }
          if (event.type === 'session.completed') {
            if (!ready || !audioBytes || Math.abs(event.audio_seconds - audioBytes / 32000) > 0.001) throw failure('native_asr_duration_mismatch');
            if ([...segments.values()].some(value => !value.final && value.text)) throw failure('native_asr_unfinalized_partial');
            completed = event; finish();
          }
        } catch (error) { finish(error); }
      });
    });
    await recording;
    await events.close();
    const result = { text: transcriptText(segments.values()),
      words: [...words.values()].flat(), audio_seconds: completed.audio_seconds,
      runtime_session_id: session, platform_operation_id: null,
      provenance: { ...config, events_sha256: await digestFile(eventFile), clinical_validation: false } };
    await exclusive(resultPath, result);
    const receipt = { status: 'completed', completed_at: new Date().toISOString(), config,
      runtime_session_id: session, platform_operation_id: null, audio_seconds: completed.audio_seconds,
      result_sha256: await digestFile(resultPath), events_sha256: result.provenance.events_sha256,
      automatic_replay: false, clinical_validation: false };
    await exclusive(receiptPath, receipt);
    return { path: resultPath, receipt, cached: false };
  } catch (error) {
    await recording.catch(() => {}); await events.close().catch(() => {});
    await exclusive(path.join(directory, 'failure.json'), { status: 'incomplete', code: error.code || 'native_asr_failed',
      runtime_session_id: session, automatic_replay: false, admission: 'unknown', recorded_at: new Date().toISOString() }).catch(() => {});
    throw failure(error.code || 'native_asr_failed');
  } finally {
    decoder?.kill('SIGTERM');
    if (ws?.readyState === WebSocket.OPEN) {
      if (!completed) ws.send(JSON.stringify({ type: 'session.cancel' }));
      ws.close();
    } else if (ws?.readyState === WebSocket.CONNECTING) ws.terminate();
  }
}
module.exports = { transcribeFile, digestFile };
