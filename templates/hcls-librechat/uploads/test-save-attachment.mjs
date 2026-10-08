import test from 'node:test';
import assert from 'node:assert/strict';
import { saveAttachmentMessage } from './save-attachment.js';

test('file-only new chat uses native persistence, retains agent, and never requests inference', async () => {
  const calls = [], conversation = { conversationId: 'new', endpoint: 'agents', agent_id: 'agent_audio_transcription_tutorial', spec: 'speech-workshop' };
  const tx = { messageId: 'draft-message', importTitle: 'Upload test-uuid' };
  const saved = { conversationId: 'native-id', messageId: 'native-message', text: 'audio receipt', isCreatedByUser: true };
  const request = {
    async postMultiPart(url, body) {
      calls.push(url); const imported = JSON.parse(await body.get('file').text());
      assert.deepEqual(imported.options, conversation);
      assert.equal(imported.messages.length, 1); assert.equal(imported.messages[0].isCreatedByUser, true);
    },
    async get(url) { calls.push(url); return url.startsWith('/api/convos?')
      ? { conversations: [{ title: tx.importTitle, conversationId: 'native-id' }] } : [saved]; },
    async post(url, body) { calls.push(url); assert.equal(body.arg.title, 'demo.wav'); },
  };
  assert.equal(await saveAttachmentMessage(request, tx, conversation, saved.text, [], 'demo.wav'), saved);
  assert.deepEqual(calls, ['/api/convos/import', '/api/convos?limit=100', '/api/messages/native-id', '/api/convos/update']);
});

test('uncertain import is not repeated; explicit retry resolves the same receipt', async () => {
  let imports = 0;
  const tx = { messageId: 'draft-message', importTitle: 'Upload test-uuid' };
  const saved = { conversationId: 'native-id', messageId: 'native-message', text: 'first receipt', isCreatedByUser: true };
  const request = {
    async postMultiPart() { imports++; throw new Error('Connection interrupted'); },
    async get(url) { return url.startsWith('/api/convos?') ? { conversations: [{ title: tx.importTitle, conversationId: 'native-id' }] } : [saved]; },
    async post() {},
  };
  await assert.rejects(saveAttachmentMessage(request, tx, { conversationId: 'new' }, saved.text, [], 'demo.wav'), /interrupted/);
  assert.equal(await saveAttachmentMessage(request, tx, { conversationId: 'new' }, 'changed receipt', [], 'demo.wav'), saved);
  assert.equal(imports, 1);
});

test('existing conversation stores only a user message with a stable ID and correct parent', async () => {
  let captured;
  const tx = { messageId: 'stable-message' };
  const request = { async post(url, body) { captured = { url, body }; return body; } };
  await saveAttachmentMessage(request, tx, { conversationId: 'saved-id', endpoint: 'agents' }, 'receipt', [{ messageId: 'previous' }], 'demo.wav');
  assert.equal(captured.url, '/api/messages/saved-id');
  assert.equal(captured.body.parentMessageId, 'previous');
  assert.equal(captured.body.messageId, 'stable-message');
  assert.equal(captured.body.isCreatedByUser, true);
});
