import { useEffect, useState } from 'react';
import { request } from 'librechat-data-provider';
import { messageAttachedFiles } from './workspace-files';
import { isAudio } from './workshop-client';
import { hashFile } from './workspace-hash';

type Attachment = { workspace_path: string; sha256?: string; name: string; size_bytes?: number };
const fileUrl = (file: Attachment) => '/api/scientific-demos/workspace/file?path=' + encodeURIComponent(file.workspace_path.slice('/workspace/'.length));
const audioType = (name: string) => ({ wav: 'audio/wav', mp3: 'audio/mpeg', m4a: 'audio/mp4', ogg: 'audio/ogg', flac: 'audio/flac', webm: 'audio/webm' }[name.split('.').pop()?.toLowerCase() || ''] || 'audio/wav');

async function fileBlob(file: Attachment, signal?: AbortSignal) {
  const response = await request.getResponse<Blob>(fileUrl(file), { responseType: 'blob', signal, timeout: 300000 });
  const blob = response.data;
  if (file.size_bytes !== undefined && blob.size !== file.size_bytes) throw new Error('Attachment size changed. Select the current Workspace file again.');
  if (file.sha256 && await hashFile(blob) !== file.sha256) throw new Error('Attachment contents changed.');
  return blob;
}

function AudioAttachment({ file }: { file: Attachment }) {
  const [url, setUrl] = useState(''), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); let objectUrl = '';
    setUrl(''); setError('');
    fileBlob(file, controller.signal).then(blob => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(new Blob([blob], { type: audioType(file.name) })); setUrl(objectUrl);
    }).catch(() => { if (!controller.signal.aborted) setError('Could not load audio.'); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [file.workspace_path, file.sha256, retry]);
  return <div className="my-2 w-full max-w-md rounded-lg border border-border-medium px-3 py-2" aria-label={`Attached audio: ${file.name}`}>
    <p className="mb-1 break-all text-xs">{file.name}</p>
    {url ? <audio aria-label={`Play ${file.name}`} controls preload="metadata" src={url} className="w-full" style={{ minWidth: 'min(22rem, 80vw)' }} /> : <span role="status" className="text-xs">{error || 'Loading audio…'}</span>}
    {error && <button type="button" className="ml-2 text-xs underline" onClick={() => setRetry(x => x + 1)}>Retry</button>}
  </div>;
}

function FileAttachment({ file }: { file: Attachment }) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function download() {
    setBusy(true); setError('');
    try {
      const url = URL.createObjectURL(await fileBlob(file)), link = document.createElement('a');
      link.href = url; link.download = file.name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setError(error instanceof Error ? error.message : 'Could not download file.'); } finally { setBusy(false); }
  }
  return <div className="my-2 rounded-lg border border-border-medium px-3 py-2 text-xs">
    <button type="button" disabled={busy} className="break-all underline" onClick={() => void download()}>Download {file.name}</button>
    {error && <span role="alert" className="ml-2">{error}</span>}
  </div>;
}

export default function MessageAttachments({ text }: { text: string }) {
  const files = messageAttachedFiles(text) as Attachment[];
  if (!files.length) return null;
  return <div data-testid="message-attachments">{files.map(file => isAudio({ name: file.name })
    ? <AudioAttachment key={file.workspace_path} file={file} /> : <FileAttachment key={file.workspace_path} file={file} />)}</div>;
}
