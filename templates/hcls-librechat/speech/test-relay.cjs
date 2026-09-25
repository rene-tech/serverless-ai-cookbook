const test = require('node:test');
const assert = require('node:assert/strict');
const { targets, targetCredential, socketUrl, issueTicket, consumeTicket, installRoutes, verifyMedicalIdentity } = require('./relay.cjs');
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
