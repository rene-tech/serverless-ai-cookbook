/* One captured PCM stream, two explicit models. No fallback, replay or second diarization. */
const crypto = require('node:crypto');
const receipts = require('./stream-receipt.cjs');
const AUDIO = { encoding: 'pcm_s16le', sample_rate_hz: 16000, channels: 1 };
function connect(client, session, WebSocket, { send, fail, release }, saveReceipt = receipts.save) {
  const states = { asr: { ready: false, done: false }, diar: { ready: false, done: false } };
  const pcmHash = crypto.createHash('sha256');
  let bytes = 0, stopped = false, released = false, finishing = false, activityFrames = 0, activityEvents = 0;
  let asrReady = {}, asrCompleted = {}, diarOperation, lastFrameEnd = 0;
  const sockets = {};
  const close = () => {
    if (released) return; released = true;
    for (const [name, ws] of Object.entries(sockets)) {
      if (ws.readyState === WebSocket.OPEN) {
        if (!states[name].done) ws.send('{"type":"session.cancel"}');
        ws.close();
      } else ws.terminate();
    }
  };
  const reject = code => { if (!released) fail(code); };
  async function complete() {
    if (!states.asr.done || !states.diar.done || finishing || released) return;
    finishing = true;
    if (!stopped || !bytes || !diarOperation || !activityFrames) return reject('paired_stream_incomplete');
    try {
      const receipt = await saveReceipt(session.owner, { schema: 'scientific-clinical/paired-stream/v1',
        asr_model: session.target.id, asr_model_revision: asrReady.model_revision || asrCompleted.model_revision || null,
        asr_runtime: session.target.modelIdentity || null,
        asr_runtime_identity_origin: session.target.modelIdentity ? 'Authenticated /v1/models immediately before session; not a WS runtime attestation' : 'unavailable',
        asr_session_id: asrReady.session_id || asrCompleted.session_id || null,
        diarization_model: session.target.diarization.id, operation_id: diarOperation,
        key_hash: receipts.hash(session.target.diarization.credential),
        pcm_sha256: pcmHash.digest('hex'), pcm_bytes: bytes, audio_seconds: bytes / 32000 });
      if (released) return;
      send({ ...asrCompleted, type: 'session.completed', speaker_stream_receipt: receipt, diarization_operation_id: diarOperation });
      client.close(1000); release();
    } catch { reject('paired_receipt_save_failed'); }
  }
  for (const name of ['asr', 'diar']) {
    const target = name === 'asr' ? session.target : session.target.diarization;
    const url = new URL(target.url); url.protocol = 'wss:';
    if (name === 'asr' && url.pathname === '/') url.pathname = '/v1/audio/stream';
    const ws = new WebSocket(url.toString(), { headers: { Authorization: `Bearer ${name === 'asr' ? session.credential : target.credential}` },
      handshakeTimeout: 15000, maxPayload: 1024 * 1024, perMessageDeflate: false });
    sockets[name] = ws;
    ws.on('open', () => ws.send(JSON.stringify(name === 'asr'
      ? { type: 'session.start', options: { model: target.wireModel || target.id, output_granularity: 'word' }, audio: AUDIO }
      : { type: 'session.start', model: target.id, audio: AUDIO })));
    ws.on('message', (raw, binary) => {
      if (released) return;
      try {
        if (binary || client.bufferedAmount > 1024 * 1024) return reject('paired_stream_backpressure');
        const event = JSON.parse(raw.toString());
        if (name === 'diar' && event.operation_id) {
          if (!/^[a-f0-9-]{36}$/.test(event.operation_id) || (diarOperation && diarOperation !== event.operation_id)) return reject('diarization_operation_mismatch');
          diarOperation = event.operation_id;
        }
        if (event.type === 'session.ready') {
          if (states[name].ready) return reject('paired_duplicate_ready');
          states[name].ready = true;
          if (name === 'asr') asrReady = event;
          else send({ type: 'diarization.ready', diarization_operation_id: diarOperation });
          if (states.asr.ready && states.diar.ready) send({ ...asrReady, type: 'session.ready', diarization_operation_id: diarOperation,
            ...(session.target.modelIdentity ? { model_identity: session.target.modelIdentity } : {}) });
        } else if ((name === 'asr' && event.type === 'session.queued') || (name === 'diar' && event.type === 'operation.queued')) {
          send({ type: 'session.queued', component: name, ...(name === 'diar' ? { diarization_operation_id: diarOperation } : { operation_id: event.operation_id }) });
        } else if (name === 'asr' && ['transcript.partial', 'transcript.final'].includes(event.type)) {
          if (!states.asr.ready || states.asr.done) return reject('asr_event_out_of_order');
          send(event);
        } else if (name === 'diar' && event.type === 'speaker.activity') {
          const step = event.frame_duration_seconds, start = event.start_seconds, probabilities = event.probabilities;
          if (!states.diar.ready || states.diar.done || !Number.isFinite(start) || start < lastFrameEnd - 0.001 || !Number.isFinite(step) || step <= 0 || step > 1 || !Array.isArray(probabilities) || probabilities.some(row => !Array.isArray(row) || row.length !== 4 || row.some(p => !Number.isFinite(p) || p < 0 || p > 1))) return reject('invalid_speaker_activity');
          activityFrames += probabilities.length; activityEvents++; lastFrameEnd = start + probabilities.length * step;
          if (activityEvents > 10000 || activityFrames > 10000 || lastFrameEnd > 602) return reject('speaker_activity_limit');
          send({ type: 'speaker.activity', start_seconds: start, frame_duration_seconds: step, probabilities });
        } else if ((name === 'asr' && event.type === 'session.completed') || (name === 'diar' && event.type === 'session.done')) {
          if (!stopped || states[name].done) return reject('paired_completion_out_of_order');
          states[name].done = true;
          if (name === 'asr') { asrCompleted = event; send({ type: 'asr.completed', model_revision: event.model_revision }); }
          else send({ type: 'diarization.completed', diarization_operation_id: diarOperation });
          void complete();
        } else if (['error', 'session.error', 'session.cancelled'].includes(event.type)) reject(name + '_stream_failed');
        else reject('paired_upstream_protocol');
      } catch { reject('paired_upstream_protocol'); }
    });
    ws.on('error', () => reject(name + '_stream_unavailable'));
    ws.on('close', () => { if (!states[name].done) reject(name + '_stream_disconnected'); });
  }
  return { release: close, handle(data, binary) {
    if (released) return;
    if (binary) {
      if (stopped || !states.asr.ready || !states.diar.ready || !data.length || data.length % 2 || data.length > 32000 || bytes + data.length > 600 * 32000 || Object.values(sockets).some(ws => ws.readyState !== WebSocket.OPEN || ws.bufferedAmount > 256000)) return reject('paired_audio_limit');
      bytes += data.length; pcmHash.update(data);
      for (const ws of Object.values(sockets)) ws.send(data, { binary: true });
      return;
    }
    if (data.length > 4096) return reject('paired_control_limit');
    const control = JSON.parse(data.toString());
    if (control.type === 'session.cancel') { close(); send({ type: 'session.cancelled' }); client.close(); release(); return; }
    if (control.type !== 'input.finish' || stopped || !states.asr.ready || !states.diar.ready) return reject('paired_control_invalid');
    stopped = true; sockets.asr.send('{"type":"input.finish"}'); sockets.diar.send('{"type":"session.finish"}');
  } };
}
module.exports = { connect };
