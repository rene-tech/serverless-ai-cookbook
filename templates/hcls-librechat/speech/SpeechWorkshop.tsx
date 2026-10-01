import { useEffect, useRef, useState } from 'react';
import { request } from 'librechat-data-provider';
import { useChatContext } from '~/Providers';
import { bindAudioConversation, getAudioAttachment, isAudio, isSpeechWorkshop,
  removeAudioAttachment, selectAudioAttachment, subscribeAudio } from './workshop-client';

/** Upload/play are independent of inference. Short user prompts run the real agent. */
export default function SpeechWorkshop({ disabled = false }: { disabled?: boolean }) {
  const { conversation, getMessages } = useChatContext();
  const conversationId = conversation?.conversationId || 'new';
  const enabled = isSpeechWorkshop(conversation);
  const [, refresh] = useState(0);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const latest = useRef({ disabled, enabled, conversationId }); latest.current = { disabled, enabled, conversationId };
  const attachment = bindAudioConversation(conversationId, getMessages() || []) || getAudioAttachment(conversationId);
  const file = attachment?.file as File | undefined;

  function choose(files: File[]) {
    if (latest.current.disabled || !latest.current.enabled) return;
    if (files.length !== 1) { setError('Choose one audio file at a time. Other files still use the regular chat attachment button.'); return; }
    try { selectAudioAttachment(latest.current.conversationId, files[0], request); setError(''); }
    catch (problem) { setError(problem instanceof Error ? problem.message : 'Could not attach audio.'); }
  }
  useEffect(() => subscribeAudio(() => refresh(value => value + 1)), []);
  useEffect(() => { setError(''); }, [conversationId]);
  useEffect(() => {
    if (!file) { setUrl(''); return; }
    const next = URL.createObjectURL(file); setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  useEffect(() => {
    // Audio belongs to the speech agent; generic files and all other chat modes
    // keep LibreChat's normal uploader. Drag/play never requests transcription.
    const drop = (event: DragEvent) => {
      if (!latest.current.enabled) return;
      const files = Array.from(event.dataTransfer?.files || []);
      if (!files.some(isAudio)) return;
      event.preventDefault(); event.stopImmediatePropagation(); choose(files);
    };
    const drag = (event: DragEvent) => {
      if (latest.current.enabled && Array.from(event.dataTransfer?.items || []).some(item => item.kind === 'file' && item.type.startsWith('audio/'))) {
        event.preventDefault(); event.stopImmediatePropagation();
      }
    };
    document.addEventListener('drop', drop, true); document.addEventListener('dragenter', drag, true); document.addEventListener('dragover', drag, true);
    return () => { document.removeEventListener('drop', drop, true); document.removeEventListener('dragenter', drag, true); document.removeEventListener('dragover', drag, true); };
  }, []);
  if (!enabled) return null;
  return <section aria-label="Speech workshop" className="basis-full my-2 w-full rounded-lg border border-border-medium p-3">
    <div className="flex flex-wrap items-center gap-2">
      <strong className="text-sm">Workshop audio</strong>
      <span className="text-xs">Drop audio (up to 10 min) into this chat, or</span>
      <button type="button" className="rounded border px-2 py-1 text-xs" disabled={disabled || attachment?.submitting} onClick={() => input.current?.click()}>Choose audio</button>
      <input ref={input} aria-label="Workshop audio file" type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.webm" className="hidden" disabled={disabled || attachment?.submitting} onChange={event => { choose(Array.from(event.target.files || [])); event.target.value = ''; }} />
      {attachment && <button type="button" className="ml-auto text-xs underline" disabled={disabled || attachment?.submitting} onClick={() => removeAudioAttachment(conversationId)}>Remove audio</button>}
    </div>
    {file && <div className="mt-2">
      <p className="break-all text-xs">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MiB</p>
      <audio aria-label="Play uploaded audio" controls preload="metadata" src={url} className="my-2 w-full" />
      <p role="status" className="text-xs">{attachment.status === 'uploading' ? 'Uploading audio only…' : attachment.status === 'ready' ? 'Audio attached to this conversation. No transcription has been started by the upload.' : 'Upload failed.'}</p>
    </div>}
    {attachment && !file && <p className="mt-2 break-all text-xs">{attachment.metadata.audio_name} · Attached audio restored from this conversation. Choose the file again only if you want local playback.</p>}
    <p className="mt-2 text-xs">Play the audio first. Then send these three messages, one at a time: <strong>Transcribe this with Nemotron</strong> → <strong>Now transcribe it with the fine-tuned Nemotron</strong> → <strong>Now add speaker detection</strong>. Each uses the same audio; no extra analysis is requested.</p>
    {(error || attachment?.error) && <p role="alert" className="mt-2 text-sm text-status-error">{error || attachment?.error}</p>}
  </section>;
}
