import { useEffect, useRef, useState } from 'react';
import { Button, Input } from '@librechat/client';
import { request } from 'librechat-data-provider';
import ScientificResult from './ScientificResult';

type Preview = { kind: string; image?: string; path?: string; notice?: string; shape?: number[]; index?: number;
  right?: string; up?: string; units?: string; spacing?: number[]; episodes?: string[]; cameras?: string[];
  episode?: string; camera?: string; samples?: number; task_success?: boolean; actions?: number[]; 'obs/joint_pos'?: number[] };
const modelFor = (path: string) => /\.nii(\.gz)?$/i.test(path) ? 'monai-spleen-ct' : /\.mp4$/i.test(path) ? 'holoscan-endoscopy' : 'isaac-healthcare';

export default function ScientificArtifactViewer({ path }: { path: string }) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState('/workspace/' + path);
  const [model, setModel] = useState(modelFor(path));
  const [mask, setMask] = useState('');
  const [axis, setAxis] = useState(2);
  const [position, setPosition] = useState(0);
  const [windowWidth, setWindow] = useState(400);
  const [level, setLevel] = useState(40);
  const [opacity, setOpacity] = useState(0.4);
  const [episode, setEpisode] = useState('');
  const [camera, setCamera] = useState('');
  const [preview, setPreview] = useState<Preview>();
  const [result, setResult] = useState<unknown>();
  const [video, setVideo] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const active = useRef(0);
  const url = useRef('');
  const abort = useRef<AbortController>();
  const json = /\.json$/i.test(path);
  const release = () => { active.current++; abort.current?.abort(); if (url.current) URL.revokeObjectURL(url.current); url.current = ''; };
  useEffect(() => () => release(), []);
  async function show() {
    release(); const current = active.current; const controller = new AbortController(); abort.current = controller;
    setBusy(true); setError(''); setVideo(''); setPreview(undefined); setResult(undefined);
    try {
      if (json) {
        const response = await request.getResponse<string>(`/api/scientific-demos/workspace/preview?path=${encodeURIComponent(path)}`, { responseType: 'text', signal: controller.signal });
        const parsed = typeof response.data === 'string' ? JSON.parse(response.data) : response.data;
        if (current === active.current) setResult(parsed);
      } else {
        const value = await request.post<Preview>(`/api/scientific-demos/apps/${model}/preview`, { path: source, mask, axis, index: position, window: windowWidth, level, opacity, episode, camera });
        if (current !== active.current) return;
        setPreview(value); setEpisode(value.episode || ''); setCamera(value.camera || '');
        if (value.kind === 'video') {
          const response = await request.getResponse<Blob>(`/api/scientific-demos/apps/${model}/media?path=${encodeURIComponent(value.path || '')}`, { responseType: 'blob', signal: controller.signal });
          if (current !== active.current) return;
          url.current = URL.createObjectURL(response.data); setVideo(url.current);
        }
      }
    } catch (e) { if (current === active.current) setError((e as { response?: { data?: { error?: string } }; message?: string }).response?.data?.error || (e as Error).message); }
    finally { if (current === active.current) setBusy(false); }
  }
  return <section aria-label="Scientific artifact preview" className="mt-3">
    <Button variant="outline" onClick={() => { if (open) { release(); setVideo(''); setPreview(undefined); setResult(undefined); setBusy(false); } setOpen(!open); }}> {open ? 'Close preview' : 'Inspect artifact'}</Button>
    {open && <div className="mt-3 space-y-3">
      {!json && <>
        <label>Viewer<select className="rounded border border-border-medium bg-surface-primary p-2 text-text-primary" value={model} onChange={e => { release(); setModel(e.target.value); setPreview(undefined); setVideo(''); setEpisode(''); setCamera(''); setPosition(0); setBusy(false); }}>{[['monai-spleen-ct', 'CT and mask'], ['holoscan-endoscopy', 'Video and overlays'], ['isaac-healthcare', 'Episode and scene']].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <p className="text-sm">{model === 'monai-spleen-ct' ? 'CT and mask: select the original CT and optional spleen mask. Only one original voxel plane is decoded per request.' : model === 'holoscan-endoscopy' ? 'Video and overlays: select the App’s optional annotated MP4 (up to 32 MiB). Overlay channels are already encoded in that video.' : 'Episode and scene: select an extracted demos.hdf5 recording. TAR and USD files remain downloads; a portable scene export is required for 3D.'}</p>
        <label className="block">{model === 'monai-spleen-ct' ? 'Original CT file' : 'Workspace artifact file'}<Input value={source} onChange={e => { setSource(e.target.value); setEpisode(''); setCamera(''); setPosition(0); }} /></label>
        {model === 'monai-spleen-ct' && <div className="grid gap-2 sm:grid-cols-3">
          <label>Mask file (optional)<Input value={mask} onChange={e => setMask(e.target.value)} /></label>
          <label>Voxel axis<select className="rounded border border-border-medium bg-surface-primary p-2 text-text-primary" value={axis} onChange={e => { setAxis(Number(e.target.value)); setPosition(0); }}>{[0, 1, 2].map(v => <option key={v}>{v}</option>)}</select></label>
          <label>HU window<Input type="number" min={1} value={windowWidth} onChange={e => setWindow(Number(e.target.value))} /></label>
          <label>HU level<Input type="number" value={level} onChange={e => setLevel(Number(e.target.value))} /></label>
          <label>Mask opacity<Input type="number" min={0} max={1} step={0.1} value={opacity} onChange={e => setOpacity(Number(e.target.value))} /></label>
        </div>}
        {model === 'isaac-healthcare' && <div className="flex gap-3">
          <label>Episode<select className="rounded border border-border-medium bg-surface-primary p-2 text-text-primary" value={episode} onChange={e => { setEpisode(e.target.value); setCamera(''); setPosition(0); }}>{preview?.episodes?.map(v => <option key={v}>{v}</option>)}</select></label>
          <label>Camera<select className="rounded border border-border-medium bg-surface-primary p-2 text-text-primary" value={camera} onChange={e => setCamera(e.target.value)}>{preview?.cameras?.map(v => <option key={v}>{v}</option>)}</select></label>
        </div>}
        {model !== 'holoscan-endoscopy' && <label className="block">{model === 'monai-spleen-ct' ? 'Slice index' : 'Sample index'}<Input type="number" min={0} max={(preview?.shape?.[axis] ?? preview?.samples ?? 1) - 1} value={position} onChange={e => setPosition(Number(e.target.value))} /></label>}
      </>}
      <Button disabled={busy} onClick={() => void show()}>{busy ? 'Loading preview…' : 'Load selected preview'}</Button>
      {error && <p role="alert">{error}</p>}
      {preview?.notice && <p className="text-sm">{preview.notice}</p>}
      {preview?.shape && <p>Shape {preview.shape.join(' × ')} · Right: {preview.right} · Up: {preview.up} · Units: {preview.units}</p>}
      {preview?.image && <img src={preview.image} alt={preview.kind === 'ct' ? `CT slice ${preview.index}, optional mask overlay` : `${preview.episode} ${preview.camera}, sample ${preview.index}`} className="max-h-[32rem] max-w-full" />}
      {video && <video controls preload="metadata" src={video} className="max-h-[32rem] max-w-full" onError={() => setError('This browser could not decode the video. Download the original to inspect its codec.')} />}
      {preview?.kind === 'episode' && <div className="break-words text-sm"><p>Recorded task success: {preview.task_success == null ? 'unknown' : String(preview.task_success)}</p><p>Actions: {preview.actions?.join(', ')}</p><p>Joint position: {preview['obs/joint_pos']?.join(', ')}</p>{!preview.image && <p>No RGB camera was recorded for this episode.</p>}</div>}
      {result !== undefined && <ScientificResult value={result} />}
    </div>}
  </section>;
}
