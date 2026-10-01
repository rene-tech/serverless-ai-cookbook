const test = require('node:test');
const assert = require('node:assert/strict');
const { targets, targetCredential, socketUrl, issueTicket, consumeTicket, installRoutes, verifyMedicalIdentity, verifyRuntimeIdentity, liveDiarization } = require('./relay.cjs');
const PARENT = '2a2b1cae8e96d62e83a82351f7d483df01fc28d1d64793ce45a5de514a6c3b5f';
test('shared platform offers three ordered choices with identical tuned weights and post-stop speaker analysis', () => {
  const choices = targets({ SCIENTIFIC_MODELS_API_BASE_URL: 'https://gateway.test/v1',
    SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'platform', SCIENTIFIC_MEDICAL_SPEECH_EXPECTED_CHECKPOINT_SHA256: PARENT });
  assert.deepEqual(Object.keys(choices), ['english', 'medical', 'medical-speakers']);
  assert.equal(choices.english.url, 'https://gateway.test/v1/audio/stream');
  assert.equal(choices.medical.id, 'nemotron-speech-en-medical-0-6b');
  assert.equal(choices.medical.url, choices.english.url);
  assert.equal(targetCredential(choices.medical, 'ordinary-key'), 'ordinary-key');
  for (const name of ['medical', 'medical-speakers']) {
    assert.equal(choices[name].expectedCheckpoint, PARENT);
    assert.equal(choices[name].id, choices.medical.id);
  }
  assert.equal(choices['medical-speakers'].diarization.timing, 'post-stop');
  assert.equal(liveDiarization(choices['medical-speakers']), false);
  assert.throws(() => targets({ SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'platform', SCIENTIFIC_MEDICAL_SPEECH_API_KEY: 'legacy' }), /Remove dedicated/);
  assert.throws(() => targets({ SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'fallback' }), /Unknown/);
});
test('shared loaded-weight attestation fails closed before PCM, including missing identity or base substitution', async () => {
  const target = { attestRuntime: true, expectedCheckpoint: PARENT };
  await verifyMedicalIdentity(target, () => { throw new Error('Must not discover dedicated endpoint'); });
  const identity = { checkpoint_sha256: PARENT, checkpoint_kind: 'fine_tuned', ignored: 'not-forwarded' };
  assert.deepEqual(verifyRuntimeIdentity(target, { runtime_identity: identity }), { checkpoint_sha256: PARENT, checkpoint_kind: 'fine_tuned' });
  for (const event of [{}, { runtime_identity: {} }, { runtime_identity: { checkpoint_sha256: 'a'.repeat(64) } }]) {
    assert.throws(() => verifyRuntimeIdentity(target, event), /does not match/);
  }
  await assert.rejects(verifyMedicalIdentity({ attestRuntime: true }), /checkpoint SHA/);
});
test('ordinary medical and Sortformer grants are independently required, not substituted by English access', async () => {
  const names = ['SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE', 'SCIENTIFIC_MEDICAL_SPEECH_EXPECTED_CHECKPOINT_SHA256', 'SCIENTIFIC_MEDICAL_SPEECH_URL', 'SCIENTIFIC_MEDICAL_SPEECH_API_KEY'];
  const before = Object.fromEntries(names.map(name => [name, process.env[name]]));
  process.env.SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE = 'platform';
  process.env.SCIENTIFIC_MEDICAL_SPEECH_EXPECTED_CHECKPOINT_SHA256 = PARENT;
  delete process.env.SCIENTIFIC_MEDICAL_SPEECH_URL; delete process.env.SCIENTIFIC_MEDICAL_SPEECH_API_KEY;
  let handler, grants = ['nemotron-speech-en-0-6b'];
  installRoutes({ get() {}, post(_path, action) { handler = action; } }, { key: async () => 'ordinary-key', platform: async () => ({ data: grants.map(id => ({ id })) }) });
  const invoke = model => new Promise((resolve, reject) => handler({ body: { model }, user: { id: 'platform-grant-test' }, get: () => 'https://client.test' }, { json: resolve }, reject));
  try {
    await assert.rejects(invoke('medical'), /does not grant/);
    grants.push('nemotron-speech-en-medical-0-6b');
    await assert.rejects(invoke('medical-speakers'), /does not grant Sortformer/);
    const admitted = await invoke('medical');
    const ticket = consumeTicket(admitted.ticket, 'https://client.test');
    assert.equal(ticket.credential, 'ordinary-key');
    assert.equal(ticket.target.expectedCheckpoint, PARENT);
  } finally {
    for (const name of names) if (before[name] === undefined) delete process.env[name]; else process.env[name] = before[name];
  }
});
test('qualified medical checkpoint is checked against exact nested runtime identity with no fallback', async () => {
  const target = { id: 'nemotron-clinical-en', expectedCheckpoint: 'a'.repeat(64), url: 'https://medical.test/v1/audio/stream', credential: 'private-test' };
  const model = { id: target.id, checkpoint_sha256: 'a'.repeat(64), base_revision: 'base', unexpected_secret: 'omit' };
  const request = async (url, options) => {
    assert.equal(String(url), 'https://medical.test/v1/models'); assert.equal(options.headers.Authorization, 'Bearer private-test');
    return { ok: true, json: async () => ({ data: [{ model }] }) };
  };
  assert.deepEqual(await verifyMedicalIdentity(target, request), { id: target.id, checkpoint_sha256: model.checkpoint_sha256, base_revision: 'base' });
  await assert.rejects(verifyMedicalIdentity({ ...target, expectedCheckpoint: 'b'.repeat(64) }, request), /differs/);
  await assert.rejects(verifyMedicalIdentity(target, async () => { throw new Error('secret provider body'); }), /Cannot verify/);
});
test('English default and medical selectable only if explicitly configured', () => {
  assert.deepEqual(Object.keys(targets({})), ['english']);
  assert.equal(targets({ SCIENTIFIC_MEDICAL_SPEECH_URL: 'https://medical.example/v1/audio/stream' }).medical.id, 'nemotron-clinical-en');
  assert.equal(targets({ SCIENTIFIC_MEDICAL_SPEECH_URL: 'https://medical.example/v1/audio/stream', SCIENTIFIC_MEDICAL_SPEECH_LABEL: 'Medical Nemotron 3.5 · PILOT checkpoint' }).medical.label, 'Medical Nemotron 3.5 · PILOT checkpoint');
});
test('isolated English changes wire model/auth only, never grant identity or implicit fallback', () => {
  const ordinary=targets({}).english;
  assert.equal(ordinary.id,'nemotron-speech-en-0-6b');
  assert.equal(targetCredential(ordinary,'ordinary-key'),'ordinary-key');
  const isolated=targets({SCIENTIFIC_ENGLISH_SPEECH_URL:'https://english.test/v1/audio/stream'}).english;
  assert.equal(isolated.id,ordinary.id); assert.equal(isolated.wireModel,'nemotron-speech-en-0.6b');
  assert.throws(()=>targetCredential(isolated,'ordinary-key'),/dedicated speech credential/);
  isolated.credential='dedicated-key'; assert.equal(targetCredential(isolated,'ordinary-key'),'dedicated-key');
});
test('isolated English still requires the ordinary caller English grant', async()=>{
  const prior=process.env.SCIENTIFIC_ENGLISH_SPEECH_URL;
  process.env.SCIENTIFIC_ENGLISH_SPEECH_URL='https://english.test/v1/audio/stream';
  let handler;
  installRoutes({get(){},post(_path,action){handler=action;}},{key:async()=> 'ordinary-key',platform:async()=>({data:[]})});
  try {
    await assert.rejects(new Promise((resolve,reject)=>handler({body:{model:'english'},user:{id:'test'},get:()=> 'https://client.test'}, {json:resolve}, reject)),/does not grant/);
  } finally { if(prior===undefined)delete process.env.SCIENTIFIC_ENGLISH_SPEECH_URL;else process.env.SCIENTIFIC_ENGLISH_SPEECH_URL=prior; }
});
test('only pinned TLS destinations, never URL credentials or query keys', () => {
  assert.equal(socketUrl('https://example.test/v1/audio/stream'), 'wss://example.test/v1/audio/stream');
  for (const value of ['http://example.test', 'https://key@example.test', 'https://example.test?key=bad']) assert.throws(() => socketUrl(value));
});
test('tickets are single-use, short-lived and bound to browser origin', () => {
  const value = issueTicket('user-test', 'https://client.test', { id: 'english' }, 'private-test', 100);
  assert.equal(consumeTicket(value.ticket, 'https://client.test', 101).owner, 'user-test');
  assert.throws(() => consumeTicket(value.ticket, 'https://client.test', 102));
  const expired = issueTicket('user-test', 'https://client.test', {}, 'private-test', 100);
  assert.throws(() => consumeTicket(expired.ticket, 'https://client.test', 30100));
  const wrongOrigin = issueTicket('user-test', 'https://client.test', {}, 'private-test', 100);
  assert.throws(() => consumeTicket(wrongOrigin.ticket, 'https://attacker.test', 102));
});
test('bounded tickets per user', () => {
  for (let i = 0; i < 4; i++) issueTicket('rate-test', 'https://client.test', {}, 'private-test', 100);
  assert.throws(() => issueTicket('rate-test', 'https://client.test', {}, 'private-test', 100), /Too many/);
});
