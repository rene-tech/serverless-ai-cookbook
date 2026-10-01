/* Loopback fixture: real UI, worklet and paired relay; deterministic fake models. */
const path = require('node:path'), fs = require('node:fs/promises'), os = require('node:os');
const express = require('/app/node_modules/express'), multer = require('/app/node_modules/multer');
const http = require('node:http'), crypto = require('node:crypto'), WebSocket = require('/app/node_modules/ws');
async function main() {
  const shared = process.env.SHARED_PLATFORM_FIXTURE === '1';
  const parent = '2a2b1cae8e96d62e83a82351f7d483df01fc28d1d64793ce45a5de514a6c3b5f';
  const base = '283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd';
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'three-mode-browser-'));
  process.env.SCIENTIFIC_SPEECH_JOBS_DIR = root;
  process.env.SCIENTIFIC_MODELS_API_BASE_URL = 'https://127.0.0.1:4100/v1';
  process.env.SCIENTIFIC_ENGLISH_SPEECH_URL = 'https://127.0.0.1:4100/asr';
  process.env.SCIENTIFIC_ENGLISH_SPEECH_API_KEY = 'english-fixture';
  process.env.SCIENTIFIC_MEDICAL_SPEECH_URL = 'https://127.0.0.1:4100/asr';
  process.env.SCIENTIFIC_MEDICAL_SPEECH_API_KEY = 'medical-fixture';
  if (shared) {
    for (const key of ['SCIENTIFIC_ENGLISH_SPEECH_URL', 'SCIENTIFIC_ENGLISH_SPEECH_API_KEY', 'SCIENTIFIC_MEDICAL_SPEECH_URL', 'SCIENTIFIC_MEDICAL_SPEECH_API_KEY']) delete process.env[key];
    process.env.SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE = 'platform';
    process.env.SCIENTIFIC_MEDICAL_SPEECH_EXPECTED_CHECKPOINT_SHA256 = parent;
    process.env.SCIENTIFIC_ENGLISH_SPEECH_EXPECTED_CHECKPOINT_SHA256 = base;
  }
  const relay = require('./relay.cjs'), receipts = require('./stream-receipt.cjs');
  const helpers = await import('./speech-state.js');
  const { build } = await import('/app/node_modules/vite/dist/node/index.js');
  const react = (await import('/app/client/node_modules/@vitejs/plugin-react/dist/index.js')).default;
  await build({ configFile: false, root, plugins: [react()], define: { 'process.env.NODE_ENV': '"development"' },
    resolve: { alias: { 'librechat-data-provider': path.join(__dirname, 'browser-request-fixture.js'),
      '~/components/LiveSpeech': path.join(__dirname, 'LiveSpeech.tsx'), '~/components/speech-state': path.join(__dirname, 'speech-state.js'),
      'react-router-dom': '/app/node_modules/react-router-dom', 'lucide-react': '/app/node_modules/lucide-react',
      'react-dom': '/app/node_modules/react-dom', 'react': '/app/node_modules/react' } },
    build: { outDir: path.join(root, 'built'), lib: { entry: path.join(__dirname, 'browser-fixture.tsx'), name: 'Fixture', formats: ['iife'], fileName: () => 'bundle.js' } } });
  const app = express(); app.use(express.json()); app.use((req, _res, next) => { req.user = { id: 'fixture-owner' }; next(); });
  const operations = new Map(), jobs = new Map(), evidence = { asr_models: [], stream_starts: 0, speaker_submissions: 0, tracked: [], controls: [], draft_submissions: 0, post_stop_submissions: 0 };
  let scenario = 'success';
  app.post('/fixture/scenario', (req, res) => { scenario = req.body.scenario; res.json({ scenario }); });
  app.get('/fixture/evidence', (_req, res) => res.json(evidence));
  const platform = async (_key, _method, resource) => {
    if (resource === '/v1/models') return { data: [{ id: 'nemotron-speech-en-0-6b' }, { id: 'nemotron-speech-en-medical-0-6b' }, { id: 'diar-streaming-sortformer-4spk-v2-1' }] };
    const id = resource.split('/')[3], operation = operations.get(id);
    if (!operation) throw new Error('Unknown fixture operation');
    return resource.endsWith('/result') ? operation.result : { id, status: operation.done ? 'succeeded' : 'running', model_id: 'diar-streaming-sortformer-4spk-v2-1' };
  };
  const router = express.Router(); relay.installRoutes(router, { key: async () => 'ordinary-fixture', platform });
  router.post('/runs', (req, res) => { evidence.tracked.push(req.body.operation_id); res.json({ id: req.body.operation_id }); });
  router.post('/clinical', multer().single('file'), (req, res) => { evidence.draft_submissions++; res.json({ id: 'a'.repeat(32) }); });
  router.post('/speech/diarization', multer().single('file'), async (req, res, next) => {
    try {
      evidence.speaker_submissions++;
      let resolved;
      if (shared) {
        if (req.body.stream_receipt || evidence.controls.at(-1)?.type !== 'input.finish') throw new Error('Post-stop fixture requires completed ASR without live speaker receipt');
        evidence.post_stop_submissions++;
        if (scenario === 'diar-failure') throw new Error('Fixture speaker operation failed after ASR completion');
        resolved = { receipt: { operation_id: crypto.randomUUID() }, result: { events: [{ type: 'speaker.activity', start_seconds: 0, frame_duration_seconds: .1,
          probabilities: Array.from({ length: 20 }, (_, i) => i < 4 ? [.9, .02, 0, 0] : [.02, .9, 0, 0]) }] } };
      } else {
        if (!req.body.stream_receipt) throw new Error('Browser fixture allows retained stream only; no second inference');
        resolved = await receipts.resolve(req.user.id, req.body.stream_receipt, 'ordinary-fixture', req.file.buffer, req.body.model, platform);
      }
      const source = require('./diarization.cjs').sourceReceipt(JSON.parse(req.body.source_receipt));
      const words = JSON.parse(req.body.words), id = receipts.hash(req.body.idempotency_key).slice(0, 32);
      if (!words.length) throw new Error('No acoustic words');
      const segments = new Map([['all', { final: true, text: source.raw_transcript }]]);
      const turns = helpers.liveSpeakerTurns(segments, new Map([['all', words]]), resolved.result.events);
      const job = { id, state: 'completed', result: { turns, operation_id: resolved.receipt.operation_id, limitations: ['Deterministic fixture only'] } };
      jobs.set(id, job); res.status(202).json(job);
    } catch (error) { next(error); }
  });
  router.get('/speech/diarization/:id', (req, res) => res.json(jobs.get(req.params.id)));
  app.use('/api/scientific-demos', router);
  app.get('/bundle.js', (_req, res) => res.sendFile(path.join(root, 'built', 'bundle.js')));
  app.get('/scientific-speech/pcm-worklet.js', (_req, res) => res.sendFile(path.join(__dirname, 'pcm-worklet.js')));
  app.get(/.*/, (_req, res) => res.type('html').send('<!doctype html><html><body><div id="root"></div><script src="/bundle.js"></script></body></html>'));
  app.use((error, _req, res, _next) => res.status(400).json({ error: error.message }));
  const server = http.createServer(app), upstream = new WebSocket.WebSocketServer({ noServer: true });
  class LocalWebSocket extends WebSocket { constructor(url, options) { super(url.replace('wss://', 'ws://'), options); } }
  relay.attach(server, LocalWebSocket);
  server.on('upgrade', (req, socket, head) => {
    if (!['/asr', '/v1/audio/stream', '/v1/voice/stream'].includes(req.url)) return;
    upstream.handleUpgrade(req, socket, head, ws => upstream.emit('connection', ws, req));
  });
  upstream.on('connection', (ws, req) => {
    const diar = req.url === '/v1/voice/stream', operation = crypto.randomUUID();
    let bytes = 0, part = 0, frame = 0; const activity = [], fixtureMode = scenario;
    const send = event => ws.send(JSON.stringify(event));
    ws.on('message', (raw, binary) => {
      if (binary) {
        bytes += raw.length;
        if (diar) {
          const count = raw.length / 3200;
          const event = { type: 'speaker.activity', start_seconds: frame * .1, frame_duration_seconds: .1,
            probabilities: Array.from({ length: Math.floor(count) }, () => frame < 4 ? [.9, .02, 0, 0] : [.02, .9, 0, 0]) };
          frame += Math.floor(count); activity.push(event); send(event);
        } else if (part === 0) { part++; send({ type: 'transcript.partial', segment_id: '0', revision: 0, text: 'No' }); }
        else if (part === 1 && bytes >= 12800) { part++; send({ type: 'transcript.final', segment_id: '0', revision: 1, text: 'No fever.',
          ...(fixtureMode === 'missing-words' ? {} : { items: [{ text: 'No', start_seconds: 0, end_seconds: .15 }, { text: 'fever.', start_seconds: .15, end_seconds: .35 }] }) }); }
        else if (part === 2 && bytes >= 25600) { part++; send({ type: 'transcript.final', segment_id: '1', revision: 1, text: ' Avoid aspirin.',
          ...(fixtureMode === 'missing-words' ? {} : { items: [{ text: 'Avoid', start_seconds: .45, end_seconds: .6 }, { text: 'aspirin.', start_seconds: .6, end_seconds: .75 }] }) }); }
        return;
      }
      const e = JSON.parse(raw); evidence.controls.push({ component: diar ? 'diar' : 'asr', type: e.type });
      if (e.type === 'session.start') {
        if (diar) { evidence.stream_starts++; operations.set(operation, { done: false }); send({ type: 'operation.queued', operation_id: operation }); }
        else evidence.asr_models.push(e.options.model);
        send({ type: 'session.ready', session_id: diar ? operation : 'fixture-native', model_revision: 'fixture-checkpoint',
          ...(shared && !diar ? { runtime_identity: { checkpoint_sha256: e.options.model === 'nemotron-speech-en-0-6b' ? base : parent,
            checkpoint_kind: e.options.model === 'nemotron-speech-en-0-6b' ? 'base' : 'fine_tuned' } } : {}) });
      }
      if (e.type === 'input.finish') send({ type: 'session.completed' });
      if (e.type === 'session.finish') {
        operations.set(operation, { done: true, result: { model: 'diar-streaming-sortformer-4spk-v2-1', audio_seconds: bytes / 32000, events: activity } });
        if (fixtureMode === 'diar-failure') send({ type: 'error', code: 'worker_lost' });
        else send({ type: 'session.done', operation_id: operation });
      }
    });
  });
  server.listen(4100, '0.0.0.0', () => console.log('Local deterministic speech fixture on 4100; no real model inference'));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
