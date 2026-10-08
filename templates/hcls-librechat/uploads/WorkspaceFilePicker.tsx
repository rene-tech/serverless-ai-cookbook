import { useEffect, useRef, useState } from 'react';
import { request } from 'librechat-data-provider';

type Entry = { name: string; path: string; kind: 'directory' | 'file'; size_bytes?: number; updated_at: string };
type Page = { data: Entry[]; prefix: string; next_offset?: number | null; info: { team_bucket_name?: string } };

/** The picker reads the same mounted bucket as the agent, including S3 uploads.
 * Selecting a file only attaches its path/metadata, never its contents to an LLM. */
export default function WorkspaceFilePicker({ onSelect }: { onSelect: (entries: Entry[]) => void }) {
  const [path, setPath] = useState(''), [offset, setOffset] = useState(0), [revision, refresh] = useState(0);
  const [page, setPage] = useState<Page | null>(null), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const [selected, setSelected] = useState<Map<string, Entry>>(new Map());
  const upload = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(''); setPage(null);
    request.get<Page>('/api/scientific-demos/workspace?' + new URLSearchParams({ path, offset: String(offset), limit: '100' }))
      .then(value => { if (active) setPage(value); })
      .catch(() => { if (active) setError('Could not list Workspace files. Refresh to retry.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, offset, revision]);
  const directory = (next: string) => { setPath(next); setOffset(0); };
  const attach = () => {
    try { onSelect([...selected.values()]); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not attach files.'); }
  };
  const uploadFiles = async (files: File[]) => {
    if (files.some(file => file.size > 512 * 1024 * 1024)) { setError('Browser uploads support 512 MiB per file. Use S3 for larger files, then select them here.'); return; }
    setLoading(true); setError('');
    try {
      for (const file of files) {
        const name = file.name.replace(/[\\/\u0000-\u001f\u007f]/g, '_').slice(-180) || 'file';
        const target = [path, 'chat-uploads', crypto.randomUUID(), name].filter(Boolean).join('/');
        const body = new FormData(); body.append('file', file); body.append('path', target);
        const receipt = await request.postMultiPart<{path: string; size_bytes: number; updated_at: string}>('/api/scientific-demos/workspace', body);
        if (receipt.path !== target || receipt.size_bytes !== file.size) throw new Error('Upload verification failed. Refresh Workspace before retrying.');
        setSelected(previous => new Map(previous).set(target, {path: target, name: file.name, kind: 'file', size_bytes: file.size, updated_at: receipt.updated_at}));
      }
      refresh(value => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Upload failed.'); }
    finally { setLoading(false); }
  };
  return <section aria-label="Bucket files" className="flex min-h-0 flex-col gap-3">
    <p className="text-sm text-text-secondary">Files in your shared Workspace bucket, including uploads made with S3. All file types are accepted. Attaching a file does not run a model.</p>
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <button type="button" className="rounded border border-border-medium px-3 py-2" disabled={loading} onClick={() => upload.current?.click()}>Upload to Workspace</button>
      <input ref={upload} type="file" multiple className="hidden" aria-label="Upload any files to Workspace" onChange={event => { void uploadFiles(Array.from(event.target.files || [])); event.target.value = ''; }} />
      <button type="button" className="underline" disabled={loading} onClick={() => refresh(value => value + 1)}>Refresh files</button>
      <button type="button" className="underline" disabled={!path || loading} onClick={() => directory(path.split('/').slice(0, -1).join('/'))}>Parent folder</button>
      <button type="button" className="underline" disabled={!path || loading} onClick={() => directory('')}>Bucket root</button>
      <a className="underline" href={'/demos?' + new URLSearchParams({tab: 'workspace', path})}>Open Workspace</a>
    </div>
    <p className="break-all text-xs">{page?.info.team_bucket_name} /{path}</p>
    {error && <p role="alert" className="text-sm text-status-error">{error}</p>}
    {loading && <p role="status">Loading Workspace…</p>}
    <div className="max-h-[45vh] overflow-auto"><table className="w-full text-left text-sm"><thead><tr><th>Select</th><th>Name</th><th>Bytes</th></tr></thead><tbody>
      {(page?.data || []).map(entry => <tr key={entry.path} className="border-t border-border-light">
        <td className="p-2">{entry.kind === 'file' && <input type="checkbox" aria-label={'Select ' + entry.name} checked={selected.has(entry.path)} onChange={event => setSelected(previous => {
          const next = new Map(previous); if (event.target.checked) next.set(entry.path, entry); else next.delete(entry.path); return next;
        })} />}</td>
        <td className="break-all p-2">{entry.kind === 'directory' ? <button type="button" className="underline" onClick={() => directory(entry.path)}>{entry.name}/</button> : entry.name}</td>
        <td className="p-2">{entry.size_bytes?.toLocaleString() ?? '—'}</td>
      </tr>)}
    </tbody></table></div>
    {!loading && page?.data.length === 0 && <p>No files in this folder.</p>}
    <div className="flex items-center justify-between gap-3 text-sm">
      <div className="flex gap-3"><button type="button" className="underline" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous page</button><button type="button" className="underline" disabled={loading || page?.next_offset == null} onClick={() => setOffset(page!.next_offset!)}>Next page</button></div>
      <button type="button" className="rounded bg-black px-4 py-2 text-white disabled:opacity-50" disabled={!selected.size || loading} onClick={attach}>Attach {selected.size || ''} selected files</button>
    </div>
  </section>;
}
