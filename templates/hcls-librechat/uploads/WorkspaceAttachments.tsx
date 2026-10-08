import { useEffect, useRef, useState } from 'react';
import { request } from 'librechat-data-provider';
import { useChatContext } from '~/Providers';
import { bindWorkspaceFiles, removeWorkspaceFile, selectExistingWorkspaceFiles, selectWorkspaceFiles, subscribeWorkspaceFiles } from './workspace-files';
import { bindAudioConversation, getAudioAttachment, removeAudioAttachment, subscribeAudio } from './workshop-client';

export default function WorkspaceAttachments({ disabled = false }: { disabled?: boolean }) {
  const { conversation, getMessages } = useChatContext();
  const id = conversation?.conversationId || 'new';
  const [, refresh] = useState(0);
  const [uploadError, setUploadError] = useState('');
  const latest = useRef({ conversation, disabled }); latest.current = { conversation, disabled };
  useEffect(() => subscribeWorkspaceFiles(() => refresh(value => value + 1)), []);
  useEffect(() => subscribeAudio(() => refresh(value => value + 1)), []);
  useEffect(() => { setUploadError(''); }, [id]);
  useEffect(() => {
    const select = (event: Event) => {
      if (latest.current.disabled) return;
      try { selectExistingWorkspaceFiles(latest.current.conversation, (event as CustomEvent).detail); event.preventDefault(); setUploadError(''); }
      catch (error) { setUploadError(error instanceof Error ? error.message : 'Could not attach files.'); }
    };
    const drop = (event: DragEvent) => {
      const files = Array.from(event.dataTransfer?.files || []);
      if (!files.length) return;
      event.preventDefault(); event.stopImmediatePropagation();
      if (latest.current.disabled) return;
      try { selectWorkspaceFiles(latest.current.conversation, files, request); setUploadError(''); }
      catch (error) { setUploadError(error instanceof Error ? error.message : 'Could not upload files.'); }
    };
    const drag = (event: DragEvent) => {
      if (Array.from(event.dataTransfer?.items || []).some(item => item.kind === 'file')) {
        event.preventDefault(); event.stopImmediatePropagation();
      }
    };
    document.addEventListener('scientific-workspace-select', select);
    document.addEventListener('drop', drop, true); document.addEventListener('dragenter', drag, true); document.addEventListener('dragover', drag, true);
    return () => { document.removeEventListener('scientific-workspace-select', select); document.removeEventListener('drop', drop, true); document.removeEventListener('dragenter', drag, true); document.removeEventListener('dragover', drag, true); };
  }, []);
  const draft = bindWorkspaceFiles(id, getMessages() || []);
  const audio = bindAudioConversation(id, getMessages() || []) || getAudioAttachment(id);
  const pendingAudio = audio && !audio.sent ? audio : null;
  const pendingFiles = (draft?.files || []).filter(file => !file.sent);
  if (!pendingFiles.length && !pendingAudio && !uploadError) return null;
  return <section aria-label="Workspace attachments" className="my-2 w-full basis-full text-xs">
    <div className="flex flex-wrap gap-2">{pendingFiles.map(file => <div key={file.id} className="max-w-full rounded border border-border-medium px-2 py-1">
      <span className="break-all">{file.name}</span>{' · '}
      <span role="status">{file.status === 'ready' ? (file.metadata?.source === 'workspace' ? 'In Workspace' : 'Uploaded') : file.status === 'uploading' ? 'Uploading…' : 'Upload failed'}</span>
      <button type="button" aria-label={`Remove ${file.name}`} className="ml-2 underline" disabled={disabled || draft.submitting} onClick={() => removeWorkspaceFile(id, file.id)}>Remove</button>
      {file.error && <p role="alert" className="text-status-error">{file.error}</p>}
    </div>)}{pendingAudio && <div className="max-w-full rounded border border-border-medium px-2 py-1">
      <span className="break-all">{pendingAudio.file?.name || pendingAudio.metadata?.audio_name}</span>{' · '}
      <span role="status">{pendingAudio.status === 'ready' ? 'Uploaded' : pendingAudio.status === 'uploading' ? 'Uploading…' : 'Upload failed'}</span>
      <button type="button" aria-label={`Remove ${pendingAudio.file?.name || pendingAudio.metadata?.audio_name}`} className="ml-2 underline" disabled={disabled || pendingAudio.submitting} onClick={() => removeAudioAttachment(id)}>Remove</button>
    </div>}</div>
    {(uploadError || draft?.error || pendingAudio?.error) && <p role="alert" className="text-status-error">{uploadError || draft?.error || pendingAudio?.error}</p>}
  </section>;
}
