const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { createService, executeAudio } = require('./chat-transcribe.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const write = (file, value) => fs.writeFile(file, JSON.stringify(value), { mode: 0o600 });
const read = async file => JSON.parse(await fs.readFile(file, 'utf8'));
async function fixture(t, options = {}) {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'chat-speech-'));
  t.after(() => fs.rm(temporary, { recursive: true, force: true }));
  const root = path.join(temporary, 'jobs'), workspace = path.join(temporary, 'workspace');
  await fs.mkdir(workspace); await fs.writeFile(path.join(workspace, 'clip.wav'), Buffer.alloc(64));
  const calls = [], process_start = (await fs.readFile(`/proc/${process.pid}/stat`, 'utf8')).split(' ')[21];
  const targets = () => ({ english: { id: 'base', url: 'https://invalid.test/v1/audio/stream' },
    medical: { id: 'medical', url: 'https://invalid.test/v1/audio/stream' },
    'medical-speakers': { id: 'medical', url: 'https://invalid.test/v1/audio/stream', diarization: { id: 'sort' } } });
  const service = createService({ root, workspace, targets, verifyIdentity: async () => {},
    platform: async () => ({ data: ['base', 'medical', 'sort'].map(id => ({ id })) }),
    workspaceGet: async (_key, relative) => ({ absolute: path.join(workspace, relative) }),
    digestFile: async file => hash(await fs.readFile(file)),
    launch: async (dir, key) => {
      const request = await read(path.join(dir, 'request.json')); calls.push({ dir, key, request });
      void (async () => {
        for (let n = 0; n < 100; n++) { if (await fs.access(path.join(dir, 'launched')).then(() => true, () => false)) break; await pause(5); }
        const state = await read(path.join(dir, 'status.json'));
        await write(path.join(dir, 'result.json'), { text: 'Raw met formin.', session_id: 'fresh-' + path.basename(dir) });
        await write(path.join(dir, 'status.json'), { ...state, status: 'completed', finished_at: new Date().toISOString() });
        await fs.unlink(path.join(root, 'slots', `${request.owner_hash}-${path.basename(dir)}.json`));
      })();
      return { pid: process.pid, process_start };
    }, ...options });
  const submit = (id, model = 'english', owner = 'alice') => service.submit(owner, 'private-test-key', { workspace_path: 'clip.wav', model, request_id: id });
  return { service, submit, root, workspace, calls, process_start };
}
test('fresh request IDs perform fresh inference on identical audio; exact retry reuses only its own result', async t => {
  const f = await fixture(t);
  const first = await f.submit('turn-1'), second = await f.submit('turn-2');
  assert.equal(first.status, 'completed'); assert.equal(second.status, 'completed');
  assert.equal(first.cached, false); assert.equal(second.cached, false);
  assert.notEqual(first.run_id, second.run_id); assert.notEqual(first.session_id, second.session_id);
  assert.equal(first.text, 'Raw met formin.'); assert.equal(f.calls.length, 2);
  const replay = await f.submit('turn-1'); assert.equal(replay.cached, true); assert.equal(replay.session_id, first.session_id);
  assert.equal(f.calls.length, 2);
  await assert.rejects(f.submit('turn-1', 'medical'), { status: 409, code: 'speech_request_conflict' });
  assert(!JSON.stringify(first).includes('private-test-key'));
});
test('owner and submitting-key boundaries isolate observations and equal request IDs', async t => {
  const f = await fixture(t), first = await f.submit('same-id');
  await assert.rejects(f.service.observe('bob', 'private-test-key', first.run_id), { status: 404 });
  await assert.rejects(f.service.observe('alice', 'different-key', first.run_id), { status: 403 });
  const second = await f.submit('same-id', 'english', 'bob'); assert.equal(second.cached, false);
  assert.equal(f.calls.length, 2); assert.notEqual(f.calls[0].dir, f.calls[1].dir);
});
test('two active requests per account are bounded without blocking another customer', async t => {
  const f = await fixture(t); await fs.mkdir(path.join(f.root, 'slots'), { recursive: true });
  for (const id of ['1'.repeat(32), '2'.repeat(32)]) await write(path.join(f.root, 'slots', `${hash('alice')}-${id}.json`), { owner_hash: hash('alice'), pid: process.pid, process_start: f.process_start });
  await assert.rejects(f.submit('busy'), { status: 429, code: 'speech_capacity_busy' });
  assert.equal(f.calls.length, 0); assert.equal((await f.submit('bob-turn', 'english', 'bob')).status, 'completed');
});
test('workspace symlink escape and unauthorized speech fail before worker admission', async t => {
  const f = await fixture(t); await fs.symlink('/etc/hosts', path.join(f.workspace, 'escape.wav'));
  await assert.rejects(f.service.submit('alice', 'private-test-key', { workspace_path: 'escape.wav', model: 'english', request_id: 'bad-path' }), { code: 'speech_workspace_escape' });
  assert.equal(f.calls.length, 0);
  const g = await fixture(t, { platform: async () => ({ data: [] }) });
  await assert.rejects(g.submit('no-grant'), { status: 403, code: 'speech_not_authorized' }); assert.equal(g.calls.length, 0);
});
test('observing a stopped worker does not restart inference', async t => {
  const f = await fixture(t), result = await f.submit('interrupted');
  await write(path.join(f.calls[0].dir, 'status.json'), { status: 'running', pid: -1, process_start: 'none' });
  const observed = await f.service.observe('alice', 'private-test-key', result.run_id, 20);
  assert.equal(observed.status, 'incomplete'); assert.equal(f.calls.length, 1);
});
test('pipeline uses selected medical checkpoint twice for separate medical and speaker requests, without a report or LLM', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'chat-speech-pipeline-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const env = { SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'platform', SCIENTIFIC_MODELS_API_BASE_URL: 'https://model.invalid/v1',
    SCIENTIFIC_MEDICAL_SPEECH_EXPECTED_CHECKPOINT_SHA256: 'a'.repeat(64), SCIENTIFIC_MODELS_API_KEY: 'private' };
  const calls = [], diarizations = [];
  for (const model of ['medical', 'medical-speakers']) {
    const dir = path.join(root, model); await fs.mkdir(dir);
    const request = { model, model_id: 'nemotron-speech-en-medical-0-6b', expected_checkpoint: 'a'.repeat(64), source: 'source.wav',
      source_sha256: 'b'.repeat(64), backend: { url: 'wss://model.invalid/v1/audio/stream', model: 'nemotron-speech-en-medical-0-6b' } };
    const result = await executeAudio(dir, request, { env,
      convert: async (_source, audio) => { await fs.writeFile(audio, Buffer.alloc(32044)); return { audio_seconds: 1 }; },
      transcribe: async options => {
        calls.push(options); await fs.mkdir(options.directory); const output = path.join(options.directory, 'result.json');
        await write(output, { text: 'Metformin.', words: [{ text: 'Metformin.', start_seconds: 0, end_seconds: .5 }], audio_seconds: 1, runtime_session_id: model + '-session' });
        return { path: output, cached: false };
      },
      diarize: async speakerDir => { diarizations.push(await read(path.join(speakerDir, 'request.json'))); return { turns: [{ speaker: 'speaker_0', text: 'Metformin.' }], operation_id: 'sort-operation' }; },
    });
    assert.equal(result.text, 'Metformin.'); assert.equal(result.session_id, model + '-session');
    assert.equal(result.audio_seconds, 1); assert.equal(result.duration_source, 'runtime_checked_against_decoded_input');
    assert.equal(Boolean(result.turns), model === 'medical-speakers');
  }
  assert.equal(calls.length, 2); assert.notEqual(calls[0].directory, calls[1].directory);
  assert(calls.every(call => call.backend.model === 'nemotron-speech-en-medical-0-6b'));
  assert.equal(diarizations.length, 1); assert.equal(diarizations[0].words[0].text, 'Metformin.');
});
test('missing runtime duration uses measured decoded audio for Sortformer; disagreement fails before diarization', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'chat-speech-duration-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const env = { SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'platform', SCIENTIFIC_MODELS_API_BASE_URL: 'https://model.invalid/v1',
    SCIENTIFIC_MODELS_API_KEY: 'private' };
  const request = { model: 'medical-speakers', model_id: 'nemotron-speech-en-medical-0-6b', expected_checkpoint: null,
    source: 'source.wav', source_sha256: 'b'.repeat(64), backend: { url: 'wss://model.invalid/v1/audio/stream', model: 'nemotron-speech-en-medical-0-6b' } };
  const speakerRequests = [];
  for (const [name, duration] of [['missing', undefined], ['mismatch', 2]]) {
    const dir = path.join(root, name); await fs.mkdir(dir);
    const promise = executeAudio(dir, request, { env,
      convert: async (_source, audio) => { await fs.writeFile(audio, Buffer.alloc(32044)); return { audio_seconds: 1 }; },
      transcribe: async options => {
        await fs.mkdir(options.directory); const output = path.join(options.directory, 'result.json');
        await write(output, { text: 'Metformin.', words: [{ text: 'Metformin.', start_seconds: 0, end_seconds: .5 }],
          ...(duration === undefined ? {} : { audio_seconds: duration }), runtime_session_id: name });
        return { path: output };
      },
      diarize: async speakerDir => { speakerRequests.push(await read(path.join(speakerDir, 'request.json'))); return { turns: [{ speaker: 'speaker_0', text: 'Metformin.' }], operation_id: 'sort-operation' }; },
    });
    if (name === 'mismatch') await assert.rejects(promise, /speech_audio_duration_mismatch/);
    else {
      const result = await promise;
      assert.equal(result.audio_seconds, 1); assert.equal(result.duration_source, 'decoded_input_ffprobe');
      assert.equal(result.turns[0].speaker, 'speaker_0');
    }
  }
  assert.equal(speakerRequests.length, 1);
  assert.equal(speakerRequests[0].audio_seconds, 1);
  assert.equal(speakerRequests[0].duration_source, 'decoded_input_ffprobe');
});
test('MCP exposes precisely typed submission and bounded observation contracts', () => {
  const { tools } = require('../demos/mcp.cjs');
  const submit = tools.find(tool => tool.name === 'workbench_transcribe_audio');
  const observe = tools.find(tool => tool.name === 'workbench_get_transcription');
  assert.deepEqual(submit.inputSchema.required, ['workspace_path', 'model', 'request_id']);
  assert.equal(submit.inputSchema.additionalProperties, false);
  assert.deepEqual(submit.inputSchema.properties.model.enum, ['english', 'medical', 'medical-speakers']);
  assert.equal(observe.inputSchema.properties.wait_seconds.maximum, 20);
});
