/* Live PCM relay. No API keys, recordings or transcripts are logged. */
const crypto = require('node:crypto');
const ENGLISH = 'nemotron-speech-en-0-6b';
const SORTFORMER = 'diar-streaming-sortformer-4spk-v2-1';
const PATH = '/api/scientific-demos/speech/stream';
const tickets = new Map();
const active = new Map();
const failure = (message, status = 400) => Object.assign(new Error(message), { status });

function targets(env = process.env) {
  const platform = (env.SCIENTIFIC_MODELS_API_BASE_URL || 'https://89.169.99.188/v1').replace(/\/v1\/?$/, '');
  const platformMedical = env.SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE === 'platform';
  if (env.SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE && !['platform', 'dedicated'].includes(env.SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE)) throw failure('Unknown medical speech authentication mode.', 503);
  if (platformMedical && (env.SCIENTIFIC_MEDICAL_SPEECH_URL || env.SCIENTIFIC_MEDICAL_SPEECH_API_KEY)) throw failure('Remove dedicated speech URL/key when using the shared platform App.', 503);
  const medical = { id: env.SCIENTIFIC_MEDICAL_SPEECH_MODEL || (platformMedical ? 'nemotron-speech-en-medical-0-6b' : 'nemotron-clinical-en'),
    label: env.SCIENTIFIC_MEDICAL_SPEECH_LABEL || 'Fine-tuned Nemotron · medical English',
    url: platformMedical ? platform + '/v1/audio/stream' : env.SCIENTIFIC_MEDICAL_SPEECH_URL,
    credential: platformMedical ? undefined : env.SCIENTIFIC_MEDICAL_SPEECH_API_KEY, dedicated: !platformMedical,
    attestRuntime: platformMedical,
    expectedCheckpoint: env.SCIENTIFIC_MEDICAL_SPEECH_EXPECTED_CHECKPOINT_SHA256 };
  return {
    english: { id: ENGLISH, label: env.SCIENTIFIC_ENGLISH_SPEECH_URL ? 'Nemotron English · legacy isolated runtime (capacity unqualified)' : 'Nemotron English · default',
      url: env.SCIENTIFIC_ENGLISH_SPEECH_URL || platform + '/v1/audio/stream',
      expectedCheckpoint: env.SCIENTIFIC_ENGLISH_SPEECH_EXPECTED_CHECKPOINT_SHA256,
      attestRuntime: Boolean(env.SCIENTIFIC_ENGLISH_SPEECH_EXPECTED_CHECKPOINT_SHA256),
      ...(env.SCIENTIFIC_ENGLISH_SPEECH_URL ? { dedicated: true,
        wireModel: env.SCIENTIFIC_ENGLISH_SPEECH_UPSTREAM_MODEL || 'nemotron-speech-en-0.6b',
        credential: env.SCIENTIFIC_ENGLISH_SPEECH_API_KEY } : {}) },
    ...(platformMedical || env.SCIENTIFIC_MEDICAL_SPEECH_URL ? { medical,
      'medical-speakers': { ...medical, label: medical.label + (platformMedical ? ' + Sortformer · speakers after Stop' : ' + Sortformer · legacy live speakers'),
        diarization: { id: SORTFORMER, url: platform + '/v1/voice/stream', timing: platformMedical ? 'post-stop' : 'live-activity-with-final-acoustic-words' } } } : {}),
  };
}
function targetCredential(target, userKey) {
  if (target.dedicated) {
    if (!target.credential) throw failure('The operator must configure the dedicated speech credential.', 503);
    return target.credential;
  }
  return userKey;
}
function socketUrl(value) {
  const url = new URL(value);
  if (url.username || url.password || url.search || url.hash || !['https:', 'wss:'].includes(url.protocol)) {
    throw failure('Speech endpoint must use TLS without embedded credentials.', 503);
  }
  url.protocol = 'wss:';
  if (url.pathname === '/') url.pathname = '/v1/audio/stream';
  return url.toString();
}
function issueTicket(owner, origin, target, credential, now = Date.now()) {
  for (const [id, item] of tickets) if (item.expires <= now) tickets.delete(id);
  if (!owner || !credential || /\s/.test(credential)) throw failure('Configure your Scientific AI API key first.', 401);
  if (!/^https?:\/\//.test(origin || '')) throw failure('A browser origin is required.', 403);
  if ([...tickets.values()].filter((item) => item.owner === owner).length >= 4 || tickets.size >= 128) {
    throw failure('Too many pending speech connections. Retry in 30 seconds.', 429);
  }
  const ticket = crypto.randomBytes(32).toString('base64url');
  tickets.set(ticket, { owner, origin, target, credential, expires: now + 30000 });
  return { ticket, expires_in: 30, path: PATH };
}
function consumeTicket(ticket, origin, now = Date.now()) {
  const item = tickets.get(ticket);
  tickets.delete(ticket);
  if (!item || item.expires <= now || item.origin !== origin) throw failure('Speech session authorization expired.', 401);
  if ((active.get(item.owner) || 0) >= 2) throw failure('Two speech sessions are already active.', 429);
  return item;
}
async function verifyMedicalIdentity(target, request = fetch) {
  if (target.attestRuntime) {
    if (!/^[a-f0-9]{64}$/.test(target.expectedCheckpoint || '')) throw failure('Configure the selected checkpoint SHA-256 before using this App.', 503);
    return undefined; // The authenticated live session must attest loaded weights before PCM.
  }
  if (!target.expectedCheckpoint) return undefined; // Historical configurations remain explicit, unpinned.
  if (!/^[a-f0-9]{64}$/.test(target.expectedCheckpoint)) throw failure('Configure the qualified medical checkpoint SHA-256.', 503);
  let value;
  try {
    const response = await request(new URL('/v1/models', target.url), { headers: { Authorization: `Bearer ${target.credential}` },
      redirect: 'error', signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error('Discovery failed');
    value = (await response.json()).data?.map(row => row.model || row).find(model => model.id === target.id);
  } catch { throw failure('Cannot verify the selected medical checkpoint. No speech inference was started.', 503); }
  if (!value || value.checkpoint_sha256 !== target.expectedCheckpoint) throw failure('Medical checkpoint differs from the qualified deployment. No speech inference was started.', 503);
  return Object.fromEntries(['id', 'checkpoint_sha256', 'base_model', 'base_revision', 'nemo_revision', 'precision', 'chunk_size_ms', 'language']
    .filter(field => value[field] !== undefined).map(field => [field, value[field]]));
}
function verifyRuntimeIdentity(target, event) {
  if (!target.attestRuntime) return undefined;
  const identity = event.runtime_identity;
  if (!identity || identity.checkpoint_sha256 !== target.expectedCheckpoint) throw failure('Loaded speech checkpoint does not match the selected model.', 503);
  return Object.fromEntries(['checkpoint_sha256', 'checkpoint_kind', 'parent_repository', 'parent_revision']
    .filter(field => identity[field] !== undefined).map(field => [field, identity[field]]));
}
function liveDiarization(target) { return Boolean(target.diarization && target.diarization.timing !== 'post-stop'); }
function installRoutes(router, { key, platform, fetchModels = fetch }) {
  router.get('/speech/models', (_req, res) => res.json({
    default: 'english', data: Object.entries(targets()).map(([key, value]) => ({ key, id: value.id, label: value.label,
      ...(value.expectedCheckpoint ? { expected_checkpoint_sha256: value.expectedCheckpoint } : {}),
      ...(value.diarization ? { diarization: { model: value.diarization.id, timing: value.diarization.timing } } : {}) })),
    audio: { encoding: 'pcm_s16le', sample_rate_hz: 16000, channels: 1 },
    retention: 'Audio stays in browser unless explicitly submitted. Server relay buffers bounded frames only; upstream policies apply.',
  }));
  router.post('/speech/tickets', (req, res, next) => Promise.resolve().then(async () => {
    const available = targets(), selected = req.body?.model || 'english';
    const target = Object.hasOwn(available, selected) ? available[selected] : undefined;
    if (!target) throw failure('Selected speech model is not configured.');
    socketUrl(target.url);
    const userKey = await key(req);
    // Validate the ordinary account key even for a service-authenticated demo adapter.
    const catalog = await platform(userKey, 'GET', '/v1/models');
    if ((!target.dedicated || target.id === ENGLISH) && !catalog.data?.some((item) => (item.id || item.model_id) === target.id)) {
      throw failure('Your Scientific AI key does not grant the selected speech App.', 403);
    }
    if (target.diarization) {
      if (!catalog.data?.some((item) => (item.id || item.model_id) === SORTFORMER)) throw failure('Your Scientific AI key does not grant Sortformer. Choose ASR-only or request the grant.', 403);
      target.diarization = { ...target.diarization, credential: userKey };
      socketUrl(target.diarization.url);
    }
    const credential = targetCredential(target, userKey);
    target.modelIdentity = await verifyMedicalIdentity(target, fetchModels);
    const origin = req.get('origin') || `${req.protocol}://${req.get('host')}`;
    res.json(issueTicket(req.user.id, origin, target, credential));
  }).catch(next));
}

function attach(server, WebSocket = require('/app/node_modules/ws'), { saveStreamReceipt } = {}) {
  const wss = new WebSocket.WebSocketServer({ noServer: true, maxPayload: 65536, perMessageDeflate: false });
  server.on('upgrade', (req, socket, head) => {
    if (req.url !== PATH) return;
    if (!req.headers.origin || wss.clients.size >= 64) { socket.destroy(); return; }
    wss.handleUpgrade(req, socket, head, (client) => wss.emit('connection', client, req));
  });
  wss.on('connection', (client, req) => {
    let upstream, dual, session, ready = false, finished = false, bytes = 0, released = false;
    const send = (event) => { if (client.readyState === WebSocket.OPEN) client.send(JSON.stringify(event)); };
    const release = () => {
      if (released) return;
      released = true;
      clearTimeout(authTimer); clearTimeout(durationTimer); clearInterval(heartbeat);
      if (session) active.set(session.owner, Math.max(0, (active.get(session.owner) || 1) - 1));
      dual?.release();
      if (upstream?.readyState === WebSocket.OPEN) {
        if (!finished) upstream.send('{"type":"session.cancel"}');
        upstream.close();
      } else if (upstream) upstream.terminate();
    };
    const fail = (code) => { send({ type: 'session.error', code, retryable: false }); client.close(1008); release(); };
    const authTimer = setTimeout(() => fail('relay_auth_timeout'), 5000);
    const durationTimer = setTimeout(() => fail('relay_duration_limit'), 15 * 60 * 1000);
    let alive = true;
    const heartbeat = setInterval(() => {
      if (!alive) { client.terminate(); release(); return; }
      alive = false; client.ping();
    }, 20000);
    client.on('pong', () => { alive = true; });
    client.on('close', release);
    client.on('error', release);
    client.on('message', (data, binary) => {
      try {
        if (!session) {
          if (binary || data.length > 4096) return fail('relay_auth_invalid');
          const first = JSON.parse(data.toString());
          if (first.type !== 'relay.attach') return fail('relay_auth_invalid');
          session = consumeTicket(first.ticket, req.headers.origin);
          active.set(session.owner, (active.get(session.owner) || 0) + 1);
          clearTimeout(authTimer);
          if (liveDiarization(session.target)) {
            dual = require('./dual-stream.cjs').connect(client, session, WebSocket, { send, fail, release }, saveStreamReceipt);
            return;
          }
          upstream = new WebSocket(socketUrl(session.target.url), {
            headers: { Authorization: `Bearer ${session.credential}` },
            handshakeTimeout: 15000, maxPayload: 1024 * 1024, perMessageDeflate: false,
          });
          upstream.on('open', () => upstream.send(JSON.stringify({ type: 'session.start',
            options: { model: session.target.wireModel || session.target.id, output_granularity: 'word' },
            audio: { encoding: 'pcm_s16le', sample_rate_hz: 16000, channels: 1 },
          })));
          upstream.on('message', (raw, isBinary) => {
            try {
              if (isBinary || client.bufferedAmount > 1024 * 1024) return fail('relay_backpressure');
              const event = JSON.parse(raw.toString());
              if (!['session.ready', 'session.queued', 'transcript.partial', 'transcript.final', 'session.completed', 'session.cancelled', 'session.error'].includes(event.type)) {
                return fail('relay_upstream_protocol');
              }
              if (event.type === 'session.ready') {
                if (ready) return fail('relay_duplicate_ready');
                try { session.target.modelIdentity = verifyRuntimeIdentity(session.target, event) || session.target.modelIdentity; }
                catch { return fail('speech_checkpoint_mismatch'); }
                ready = true;
              }
              // Never relay arbitrary backend error bodies, which can include internal details.
              send(event.type === 'session.error' ? { type: event.type, code: /^[a-z0-9_]{1,100}$/.test(event.code || '') ? event.code : 'upstream_failed', retryable: Boolean(event.retryable) }
                : event.type === 'session.ready' && session.target.modelIdentity ? { ...event, model_identity: session.target.modelIdentity } : event);
              if (['session.completed', 'session.cancelled', 'session.error'].includes(event.type)) {
                finished = true; client.close(1000); release();
              }
            } catch { fail('relay_upstream_protocol'); }
          });
          upstream.on('error', () => fail('relay_upstream_unavailable'));
          upstream.on('close', () => { if (!released) fail('relay_upstream_disconnected'); });
          return;
        }
        if (dual) return dual.handle(data, binary);
        if (binary) {
          bytes += data.length;
          if (!ready || finished || data.length % 2 || bytes > 10 * 60 * 32000 || upstream.bufferedAmount > 256000) return fail('relay_audio_limit');
          upstream.send(data, { binary: true });
        } else {
          if (data.length > 4096) return fail('relay_control_limit');
          const control = JSON.parse(data.toString());
          if (control.type === 'session.cancel') {
            // Send the cancellation control before the closing frame. Closing
            // first used to rely solely on the platform's disconnect cleanup.
            if (upstream?.readyState === WebSocket.OPEN) upstream.send('{"type":"session.cancel"}');
            finished = true; send({ type: 'session.cancelled' }); client.close(); release(); return;
          }
          if (control.type !== 'input.finish' || !ready || finished) return fail('relay_control_invalid');
          finished = true; upstream.send('{"type":"input.finish"}');
        }
      } catch { fail('relay_request_rejected'); }
    });
  });
  return wss;
}
module.exports = { installRoutes, attach, targets, targetCredential, socketUrl, issueTicket, consumeTicket, verifyMedicalIdentity, verifyRuntimeIdentity, liveDiarization };
