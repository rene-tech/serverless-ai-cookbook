const test = require('node:test');
const assert = require('node:assert/strict');
const { targets, targetCredential, socketUrl, issueTicket, consumeTicket, installRoutes } = require('./relay.cjs');
test('English default and medical selectable only if explicitly configured', () => {
  assert.deepEqual(Object.keys(targets({})), ['english']);
  assert.equal(targets({ SCIENTIFIC_MEDICAL_SPEECH_URL: 'https://medical.example/v1/audio/stream' }).medical.id, 'nemotron-clinical-en');
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
