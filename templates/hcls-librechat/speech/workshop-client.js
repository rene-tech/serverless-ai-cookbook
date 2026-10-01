/* Audio attachments for the ordinary chat/MCP path. Selection only uploads;
 * only an explicit chat submission can ask the agent to run a model. */
const attachments = new Map();
const submittedDrafts = new Map();
const dismissed = new Set();
const listeners = new Set();
// The pinned client can update browser history before its ChatContext leaves
// "new". Use that saved route only for this transition, never another chat's file.
const conversationKey = id => id && id !== 'new' ? id
  : /^\/c\/([0-9a-f-]{36})$/.exec(globalThis.location?.pathname || '')?.[1] || 'new';
const notify = () => listeners.forEach(listener => listener());
export const isAudio = file => file?.type?.startsWith('audio/') || /\.(wav|mp3|m4a|ogg|flac|webm)$/i.test(file?.name || '');
export const isSpeechWorkshop = conversation => conversation?.agent_id === 'agent_audio_transcription_tutorial' || conversation?.spec === 'speech-workshop';
export const subscribeAudio = listener => { listeners.add(listener); return () => listeners.delete(listener); };
export const getAudioAttachment = id => attachments.get(conversationKey(id)) || null;
export function removeAudioAttachment(id) { const key = conversationKey(id); attachments.delete(key); dismissed.add(key); notify(); }

/** Display only. The original message and its receipt still go to the agent and history. */
export function audioReceiptFromMessage(text) {
  if (typeof text !== 'string') return null;
  const match = text.match(/\n\n\[Uploaded audio\]\n(\{[^\n]+\})\n\[\/Uploaded audio\]$/);
  if (!match) return null;
  try {
    const value = JSON.parse(match[1]);
    if (!/^\/workspace\/workshop-audio\/[0-9a-f-]{36}\/[a-zA-Z0-9._-]+$/.test(value.workspace_path)
      || !/^[0-9a-f]{64}$/.test(value.sha256) || !/^[0-9a-f-]{36}$/.test(value.request_id)
      || typeof value.audio_name !== 'string') return null;
    return { value, index: match.index };
  } catch { return null; }
}
export function visibleWorkshopPrompt(text) {
  const receipt = audioReceiptFromMessage(text);
  return receipt ? text.slice(0, receipt.index) : text;
}

export async function uploadAudio(file, request) {
  if (!isAudio(file)) throw new Error('Choose one WAV, MP3, M4A, OGG, FLAC or WebM audio file.');
  if (!file.size || file.size > 64 * 1024 * 1024) throw new Error('Choose a non-empty audio file up to 64 MiB.');
  const sha256 = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))]
    .map(value => value.toString(16).padStart(2, '0')).join('');
  const name = file.name.replace(/[^a-zA-Z0-9._-]/g, '_').slice(-100) || 'audio.wav';
  const path = `workshop-audio/${crypto.randomUUID()}/${name}`;
  const body = new FormData(); body.append('file', file); body.append('path', path);
  const receipt = await request.postMultiPart('/api/scientific-demos/workspace', body);
  if (receipt.path !== path || receipt.size_bytes !== file.size || receipt.sha256 !== sha256) {
    throw new Error('Audio upload verification failed. No transcription was requested. Choose the file again.');
  }
  return { workspace_path: `/workspace/${path}`, sha256, audio_name: file.name, size_bytes: file.size };
}

export function selectAudioAttachment(id, file, request) {
  if (!isAudio(file)) throw new Error('Choose one WAV, MP3, M4A, OGG, FLAC or WebM audio file.');
  if (!file.size || file.size > 64 * 1024 * 1024) throw new Error('Choose a non-empty audio file up to 64 MiB.');
  const key = conversationKey(id);
  dismissed.delete(key);
  const attachment = { file, status: 'uploading', metadata: null, error: '', submitting: false, sent: false, ready: null };
  attachments.set(key, attachment); notify();
  // Keep failures on the attachment, without unhandled promises or auto-retries.
  attachment.ready = uploadAudio(file, request).then(metadata => {
    attachment.metadata = metadata; attachment.status = 'ready'; attachment.error = ''; notify(); return attachment;
  }, error => {
    attachment.status = 'failed'; attachment.error = error instanceof Error ? error.message : 'Audio upload failed. Choose the file again.';
    notify(); return attachment;
  });
  return attachment;
}

/** A new chat acquires its real ID after submission. Transfer only when its own
 * actual user-message receipt is present; never attach the last file to a new chat. */
export function bindAudioConversation(id, messages = []) {
  const key = conversationKey(id);
  if (key === 'new' || attachments.has(key)) return getAudioAttachment(key);
  if (dismissed.has(key)) return null;
  for (const [path, attachment] of submittedDrafts) {
    if (messages.some(message => message.isCreatedByUser && typeof message.text === 'string'
      && message.text.includes(`"workspace_path":${JSON.stringify(path)}`)
      && message.text.includes(`"sha256":${JSON.stringify(attachment.metadata.sha256)}`))) {
      attachments.set(key, attachment); submittedDrafts.delete(path); return attachment;
    }
  }
  // Reload: only the current conversation's own explicit upload receipt is eligible.
  // The file remains in its workspace; no discovery, download or inference occurs.
  for (const message of [...messages].reverse()) {
    if (!message.isCreatedByUser || typeof message.text !== 'string') continue;
    const match = message.text.match(/\[Uploaded audio\]\n(\{[^\n]+\})\n\[\/Uploaded audio\]/);
    if (!match) continue;
    try {
      const value = JSON.parse(match[1]);
      if (!/^\/workspace\/workshop-audio\/[0-9a-f-]{36}\/[a-zA-Z0-9._-]+$/.test(value.workspace_path)
        || !/^[0-9a-f]{64}$/.test(value.sha256) || typeof value.audio_name !== 'string') return null;
      const metadata = { workspace_path: value.workspace_path, sha256: value.sha256, audio_name: value.audio_name };
      const attachment = { file: null, status: 'ready', metadata, error: '', submitting: false, sent: true, ready: Promise.resolve() };
      attachments.set(key, attachment); return attachment;
    } catch { return null; }
  }
  return null;
}

export async function submitWithWorkshopAudio(data, conversation, submit) {
  const key = conversationKey(conversation?.conversationId);
  const attachment = getAudioAttachment(key);
  if (!isSpeechWorkshop(conversation) || !attachment || (!data?.text?.trim() && !(data?.attachmentOnly && !attachment.sent))) return submit(data);
  if (attachment.submitting) return false;
  if (attachment.status === 'uploading') {
    attachment.error = 'Audio is still uploading. Send your message once it is attached.'; notify(); return false;
  }
  if (attachment.status !== 'ready') return false;
  attachment.submitting = true; attachment.error = ''; notify();
  try {
    if (getAudioAttachment(key) !== attachment) return false;
    const metadata = { ...attachment.metadata, request_id: crypto.randomUUID(), display_attachment: !attachment.sent };
    if (/\b(?:speakers?|diari[sz]ation|sortformer)\b/i.test(data.text.split('\n\n[Uploaded files]')[0])) {
      metadata.response_instruction = 'For speaker detection, reproduce each returned turn as speaker label: verbatim text, including uncertain; do not infer doctor/patient roles.';
    }
    const submitted = await submit({ ...data, text: `${data.text}\n\n[Uploaded audio]\n${JSON.stringify(metadata)}\n[/Uploaded audio]` });
    if (submitted === false) return false;
    attachment.sent = true;
    if (key === 'new') {
      attachments.delete(key); submittedDrafts.set(metadata.workspace_path, attachment);
      // A bounded hand-off cache, not shared customer state or persisted audio.
      if (submittedDrafts.size > 8) submittedDrafts.delete(submittedDrafts.keys().next().value);
    }
    return submitted;
  } catch (error) {
    attachment.error = error instanceof Error ? error.message : 'Could not send the audio attachment.';
    return false;
  } finally { attachment.submitting = false; notify(); }
}
