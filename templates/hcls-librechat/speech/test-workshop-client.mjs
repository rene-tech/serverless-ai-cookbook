import test from 'node:test';
import assert from 'node:assert/strict';
import { File } from 'node:buffer';
import { createHash, randomUUID } from 'node:crypto';
import { bindAudioConversation, getAudioAttachment, isSpeechWorkshop, removeAudioAttachment,
  selectAudioAttachment, submitWithWorkshopAudio, uploadAudio, visibleWorkshopPrompt } from './workshop-client.js';
const file = () => new File(['synthetic audio'], 'Doctor patient.wav', { type: 'audio/wav' });
const conversation = id => ({ conversationId: id, agent_id: 'agent_audio_transcription_tutorial' });
const receipt = text => JSON.parse(text.split('[Uploaded audio]\n')[1].split('\n[/Uploaded audio]')[0]);
function api() {
  const calls = [];
  return { calls, async postMultiPart(url, body) {
    calls.push({ url, body }); const audio = body.get('file');
    return { path: body.get('path'), size_bytes: audio.size,
      sha256: createHash('sha256').update(Buffer.from(await audio.arrayBuffer())).digest('hex') };
  } };
}
test('selection uploads exact bytes to a fresh verified path, and never calls ASR/LLM', async () => {
  const request = api(), audio = file();
  const a = await uploadAudio(audio, request), b = await uploadAudio(audio, request);
  assert.equal(request.calls.length, 2);
  assert.ok(request.calls.every(call => call.url === '/api/scientific-demos/workspace'));
  assert.equal(a.sha256, b.sha256); assert.notEqual(a.workspace_path, b.workspace_path);
  assert.match(a.workspace_path, /^\/workspace\/workshop-audio\/[\da-f-]+\/Doctor_patient.wav$/);
});
test('three short chat prompts use same audio with unique request IDs and preserve general data', async () => {
  const id = randomUUID(), request = api(), output = [];
  const attachment = selectAudioAttachment(id, file(), request); await attachment.ready;
  for (const text of ['Nemotron', 'finetuned', 'with speakers']) {
    await submitWithWorkshopAudio({ text, overrideFiles: ['document'] }, conversation(id), value => output.push(value));
  }
  assert.equal(request.calls.length, 1); assert.equal(output.length, 3);
  assert.deepEqual(output.map(value => value.text.split('\n')[0]), ['Nemotron', 'finetuned', 'with speakers']);
  assert.ok(output.every(value => value.overrideFiles[0] === 'document'));
  const metadata = output.map(value => receipt(value.text));
  assert.deepEqual(metadata.map(value => value.display_attachment), [true, false, false]);
  assert.equal(attachment.sent, true);
  assert.equal(new Set(metadata.map(value => value.workspace_path)).size, 1);
  assert.equal(new Set(metadata.map(value => value.request_id)).size, 3);
  removeAudioAttachment(id);
});
test('speaker prompt alone adds an anonymous-turn presentation hint without changing attachment state', async () => {
  const id = randomUUID(), output = [], attachment = selectAudioAttachment(id, file(), api()); await attachment.ready;
  for (const text of ['Transcribe this with Nemotron', 'Now transcribe it with the fine-tuned Nemotron', 'Now add speaker detection']) {
    await submitWithWorkshopAudio({ text }, conversation(id), value => output.push(value));
  }
  assert.equal(receipt(output[0].text).response_instruction, undefined);
  assert.equal(receipt(output[1].text).response_instruction, undefined);
  assert.equal(receipt(output[2].text).response_instruction, 'For speaker detection, reproduce each returned turn as speaker label: verbatim text, including uncertain; do not infer doctor/patient roles.');
  assert.equal(visibleWorkshopPrompt(output[2].text), 'Now add speaker detection');
  assert.equal(attachment.metadata.response_instruction, undefined);
  assert.equal(new Set(output.map(value => receipt(value.text).workspace_path)).size, 1);
  assert.equal(new Set(output.map(value => receipt(value.text).request_id)).size, 3);
  removeAudioAttachment(id);
});
test('new chat transfers only to the conversation containing its own actual user receipt', async () => {
  const request = api(), output = [];
  const attachment = selectAudioAttachment('new', file(), request); await attachment.ready;
  await submitWithWorkshopAudio({ text: 'Nemotron' }, conversation('new'), value => output.push(value));
  assert.equal(getAudioAttachment('new'), null);
  assert.equal(bindAudioConversation('unrelated', []), null);
  assert.equal(bindAudioConversation('not-user', [{ text: output[0].text, isCreatedByUser: false }]), null);
  assert.equal(bindAudioConversation('saved', [{ text: output[0].text, isCreatedByUser: true }]), attachment);
  removeAudioAttachment('saved');
});
test('other agents and chats keep their ordinary submission untouched', async () => {
  const id = randomUUID(), request = api(), output = [], data = { text: 'ordinary question' };
  const attachment = selectAudioAttachment(id, file(), request); await attachment.ready;
  await submitWithWorkshopAudio(data, { conversationId: id, agent_id: 'another-agent' }, value => output.push(value));
  await submitWithWorkshopAudio(data, conversation('another-chat'), value => output.push(value));
  assert.equal(output[0], data); assert.equal(output[1], data);
  assert.equal(isSpeechWorkshop({ spec: 'speech-workshop' }), true);
  removeAudioAttachment(id);
});
test('reload restores only own current-conversation receipt and issues a new request ID', async () => {
  const request = api(), metadata = { ...await uploadAudio(file(), request), request_id: 'previous-run' };
  const text = `Nemotron\n\n[Uploaded audio]\n${JSON.stringify(metadata)}\n[/Uploaded audio]`;
  assert.equal(bindAudioConversation(randomUUID(), [{ text, isCreatedByUser: false }]), null);
  const id = randomUUID(), messages = [{ text, isCreatedByUser: true }], output = [];
  const restored = bindAudioConversation(id, messages); assert.equal(restored.file, null);
  assert.equal(restored.sent, true);
  await submitWithWorkshopAudio({ text: 'finetuned' }, conversation(id), value => output.push(value));
  assert.equal(receipt(output[0].text).workspace_path, metadata.workspace_path);
  assert.notEqual(receipt(output[0].text).request_id, metadata.request_id);
  removeAudioAttachment(id); assert.equal(bindAudioConversation(id, messages), null);
});
test('rejected async submission keeps the selected attachment and exposes the error', async () => {
  const id = randomUUID(), attachment = selectAudioAttachment(id, file(), api()); await attachment.ready;
  assert.equal(await submitWithWorkshopAudio({ text: 'Nemotron' }, conversation(id), async () => { throw new Error('Send rejected'); }), false);
  assert.equal(getAudioAttachment(id), attachment); assert.match(attachment.error, /Send rejected/);
  removeAudioAttachment(id);
});
test('uploading and verification failure block submission, preserve errors, and do not retry', async () => {
  const id = randomUUID(), request = api(), output = [];
  const attachment = selectAudioAttachment(id, file(), request);
  assert.equal(await submitWithWorkshopAudio({ text: 'Nemotron' }, conversation(id), value => output.push(value)), false);
  await attachment.ready;
  const failed = selectAudioAttachment(id, file(), { postMultiPart: async () => ({ path: 'wrong' }) }); await failed.ready;
  assert.equal(await submitWithWorkshopAudio({ text: 'Nemotron' }, conversation(id), value => output.push(value)), false);
  assert.match(failed.error, /verification failed/); assert.equal(output.length, 0);
  assert.equal(request.calls.length, 1); removeAudioAttachment(id);
});
test('display hides only a valid automatic receipt while original prompt/context stay complete', async () => {
  const id = randomUUID(), output = [], attachment = selectAudioAttachment(id, file(), api()); await attachment.ready;
  const prompt = 'Transcribe this with Nemotron';
  await submitWithWorkshopAudio({ text: prompt }, conversation(id), value => output.push(value));
  const original = output[0].text;
  assert.equal(visibleWorkshopPrompt(original), prompt);
  assert.equal(receipt(original).workspace_path, attachment.metadata.workspace_path);
  assert.match(original, /\[Uploaded audio\]/);
  assert.equal(visibleWorkshopPrompt('Ordinary text'), 'Ordinary text');
  const malformed = prompt + '\n\n[Uploaded audio]\n{"workspace_path":"unverified"}\n[/Uploaded audio]';
  assert.equal(visibleWorkshopPrompt(malformed), malformed);
  removeAudioAttachment(id);
});
test('saved browser route with stale new ChatContext keeps the same file for all three prompts', async () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'location');
  const location = { pathname: '/c/new' }, request = api(), output = [], id = randomUUID();
  Object.defineProperty(globalThis, 'location', { configurable: true, value: location });
  try {
    const attachment = selectAudioAttachment('new', file(), request); await attachment.ready;
    await submitWithWorkshopAudio({ text: 'Nemotron' }, conversation('new'), value => {
      output.push(value); location.pathname = `/c/${id}`;
    });
    const messages = [{ ...output[0], isCreatedByUser: true }];
    assert.equal(bindAudioConversation('new', messages), attachment);
    assert.equal(getAudioAttachment('new')?.file, attachment.file);
    for (const text of ['finetuned', 'with speakers']) {
      await submitWithWorkshopAudio({ text }, conversation('new'), value => output.push(value));
    }
    assert.equal(request.calls.length, 1);
    assert.equal(new Set(output.map(value => receipt(value.text).workspace_path)).size, 1);
    assert.equal(new Set(output.map(value => receipt(value.text).request_id)).size, 3);
    location.pathname = '/c/new';
    assert.equal(getAudioAttachment('new'), null);
    removeAudioAttachment(id);
  } finally {
    if (previous) Object.defineProperty(globalThis, 'location', previous); else delete globalThis.location;
  }
});
