/* Live PCM relay. No API keys, recordings or transcripts are logged. */
const crypto = require('node:crypto');
const ENGLISH = 'nemotron-speech-en-0-6b';
const PATH = '/api/scientific-demos/speech/stream';
const tickets = new Map();
const active = new Map();
const failure = (message, status = 400) => Object.assign(new Error(message), { status });

function targets(env = process.env) {
  const platform = (env.SCIENTIFIC_MODELS_API_BASE_URL || 'https://89.169.99.188/v1').replace(/\/v1\/?$/, '');
  return {
    english: { id: ENGLISH, label: 'Nemotron English · default', url: platform + '/v1/audio/stream' },
    ...(env.SCIENTIFIC_MEDICAL_SPEECH_URL ? { medical: {
      id: env.SCIENTIFIC_MEDICAL_SPEECH_MODEL || 'nemotron-clinical-en',
      label: 'Medical Nemotron 3.5 · English', url: env.SCIENTIFIC_MEDICAL_SPEECH_URL,
      credential: env.SCIENTIFIC_MEDICAL_SPEECH_API_KEY,
    } } : {}),
  };
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
function installRoutes(router, { key, platform }) {
  router.get('/speech/models', (_req, res) => res.json({
    default: 'english', data: Object.entries(targets()).map(([key, value]) => ({ key, id: value.id, label: value.label })),
    audio: { encoding: 'pcm_s16le', sample_rate_hz: 16000, channels: 1 },
    retention: 'Audio stays in browser unless explicitly submitted. Server relay buffers bounded frames only; upstream policies apply.',
  }));
  router.post('/speech/tickets', (req, res, next) => Promise.resolve().then(async () => {
    const target = targets()[req.body?.model || 'english'];
    if (!target) throw failure('Selected speech model is not configured.');
    socketUrl(target.url);
    const userKey = await key(req);
    // Validate the ordinary account key even for a service-authenticated demo adapter.
    const catalog = await platform(userKey, 'GET', '/v1/models');
    if (target.id === ENGLISH && !catalog.data?.some((item) => (item.id || item.model_id) === ENGLISH)) {
      throw failure('Your Scientific AI key does not grant the English speech model.', 403);
    }
    const credential = target.credential || (target.id === ENGLISH ? userKey : '');
    const origin = req.get('origin') || `${req.protocol}://${req.get('host')}`;
    res.json(issueTicket(req.user.id, origin, target, credential));
  }).catch(next));
}

function attach(server, WebSocket = require('/app/node_modules/ws')) {
  const wss = new WebSocket.WebSocketServer({ noServer: true, maxPayload: 65536, perMessageDeflate: false });
  server.on('upgrade', (req, socket, head) => {
    if (req.url !== PATH) return;
    if (!req.headers.origin || wss.clients.size >= 64) { socket.destroy(); return; }
    wss.handleUpgrade(req, socket, head, (client) => wss.emit('connection', client, req));
  });
  wss.on('connection', (client, req) => {
    let upstream, session, ready = false, finished = false, bytes = 0, released = false;
    const send = (event) => { if (client.readyState === WebSocket.OPEN) client.send(JSON.stringify(event)); };
    const release = () => {
      if (released) return;
      released = true;
      clearTimeout(authTimer); clearTimeout(durationTimer); clearInterval(heartbeat);
      if (session) active.set(session.owner, Math.max(0, (active.get(session.owner) || 1) - 1));
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
          upstream = new WebSocket(socketUrl(session.target.url), {
            headers: { Authorization: `Bearer ${session.credential}` },
            handshakeTimeout: 15000, maxPayload: 1024 * 1024, perMessageDeflate: false,
          });
          upstream.on('open', () => upstream.send(JSON.stringify({ type: 'session.start',
            options: { model: session.target.id, output_granularity: 'word' },
            audio: { encoding: 'pcm_s16le', sample_rate_hz: 16000, channels: 1 },
          })));
          upstream.on('message', (raw, isBinary) => {
            try {
              if (isBinary || client.bufferedAmount > 1024 * 1024) return fail('relay_backpressure');
              const event = JSON.parse(raw.toString());
              if (!['session.ready', 'session.queued', 'transcript.partial', 'transcript.final', 'session.completed', 'session.cancelled', 'session.error'].includes(event.type)) {
                return fail('relay_upstream_protocol');
              }
              if (event.type === 'session.ready') ready = true;
              // Never relay arbitrary backend error bodies, which can include internal details.
              send(event.type === 'session.error' ? { type: event.type, code: /^[a-z0-9_]{1,100}$/.test(event.code || '') ? event.code : 'upstream_failed', retryable: Boolean(event.retryable) } : event);
              if (['session.completed', 'session.cancelled', 'session.error'].includes(event.type)) {
                finished = true; client.close(1000); release();
              }
            } catch { fail('relay_upstream_protocol'); }
          });
          upstream.on('error', () => fail('relay_upstream_unavailable'));
          upstream.on('close', () => { if (!released) fail('relay_upstream_disconnected'); });
          return;
        }
        if (binary) {
          bytes += data.length;
          if (!ready || finished || data.length % 2 || bytes > 10 * 60 * 32000 || upstream.bufferedAmount > 256000) return fail('relay_audio_limit');
          upstream.send(data, { binary: true });
        } else {
          if (data.length > 4096) return fail('relay_control_limit');
          const control = JSON.parse(data.toString());
          if (control.type === 'session.cancel') { upstream?.close(); send({ type: 'session.cancelled' }); client.close(); release(); return; }
          if (control.type !== 'input.finish' || !ready || finished) return fail('relay_control_invalid');
          finished = true; upstream.send('{"type":"input.finish"}');
        }
      } catch { fail('relay_request_rejected'); }
    });
  });
  return wss;
}
module.exports = { installRoutes, attach, targets, socketUrl, issueTicket, consumeTicket };
