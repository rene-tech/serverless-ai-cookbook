import { useEffect, useRef, useState } from 'react';
import { request } from 'librechat-data-provider';
import { useSearchParams } from 'react-router-dom';
import { Mic, Square, X } from 'lucide-react';
import { transcriptEvent, wavBlob } from './speech-state';

type Model = { key: string; id: string; label: string };
type Event = { type: string; text?: string; segment_id?: string; sequence?: number; revision?: number;
  code?: string; operation_id?: string; model_revision?: string; items?: Word[] };
type Word = { text: string; start_seconds: number; end_seconds: number };
type SpeakerJob = { id: string; state: string; error?: string; result?: {
  turns: (Word & { speaker: string; flag?: string })[]; operation_id?: string; limitations: string[] } };
const BASE = '/api/scientific-demos/speech';
type Props = { compact?: boolean; disabled?: boolean; onTranscript?: (text: string) => void; onStart?: () => void };

export default function LiveSpeech({ compact = false, disabled = false, onTranscript, onStart }: Props) {
  const [params, setParams] = useSearchParams();
  const [models, setModels] = useState<Model[]>([]);
  const [model, setModel] = useState('english');
  const [state, setState] = useState('idle');
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [metrics, setMetrics] = useState<{ first?: number; final?: number; operation?: string }>({});
  const [reviewed, setReviewed] = useState(false);
  const [report, setReport] = useState('');
  const [draftBusy, setDraftBusy] = useState(false);
  const [draftJob, setDraftJob] = useState('');
  const draftId = useRef(crypto.randomUUID());
  const speakerId = useRef(crypto.randomUUID());
  const [speaker, setSpeaker] = useState<SpeakerJob | null>(null);
  const [speakerBusy, setSpeakerBusy] = useState(false);
  const [roles, setRoles] = useState<Record<string, string>>({});
  const segments = useRef(new Map());
  const transcript = useRef('');
  const current = useRef<{ ws?: WebSocket; context?: AudioContext; node?: AudioWorkletNode;
    source?: AudioBufferSourceNode | MediaStreamAudioSourceNode; stream?: MediaStream; chunks: ArrayBuffer[];
    model?: string; words: Map<string, Word[]>;
    started: number; first?: number; stopped?: number; closed?: boolean; finalTimer?: ReturnType<typeof setTimeout> }>({ chunks: [], words: new Map(), started: 0 });
  const handlers = useRef({ onTranscript, onStart }); handlers.current = { onTranscript, onStart };
  const busy = !['idle', 'completed', 'cancelled', 'failed'].includes(state);
  useEffect(() => {
    request.get<{ data: Model[] }>(`${BASE}/models`).then((value) => setModels(value.data))
      .catch(() => setError('Sign in to configure speech.'));
    const previous = params.get('speech_job');
    if (!compact && previous && /^[a-f0-9]{32}$/.test(previous)) {
      request.get<SpeakerJob>(`${BASE}/diarization/${previous}`).then((value) => {
        setSpeaker(value); setState('completed');
        if (value.result) setText(value.result.turns.map((turn) => `[${turn.speaker}] ${turn.text}`).join('\n'));
      }).catch(() => setError('Saved speaker job could not be loaded for this account.'));
    }
    return () => cleanup(true);
  }, []);
  useEffect(() => {
    if (!speaker?.id || !['running', 'prepared'].includes(speaker.state)) return;
    const timer = setInterval(() => {
      request.get<SpeakerJob>(`${BASE}/diarization/${speaker.id}`).then((value) => {
        setSpeaker(value);
        if (value.state === 'completed' && value.result) {
          const transcript = value.result.turns.map((turn) => `[${turn.speaker}] ${turn.text}`).join('\n');
          setText(transcript); setReviewed(false); setDraftJob(''); draftId.current = crypto.randomUUID();
        }
      }).catch(() => setError('Speaker job status unavailable. The saved job may still be running; resume its status, not a new recording.'));
    }, 3000);
    return () => clearInterval(timer);
  }, [speaker?.id, speaker?.state]);

  function cleanup(cancel = false) {
    const run = current.current;
    run.closed = true;
    clearTimeout(run.finalTimer);
    run.stream?.getTracks().forEach((track) => track.stop());
    if (run.source instanceof AudioBufferSourceNode) { run.source.onended = null; try { run.source.stop(); } catch { /* already ended */ } }
    run.source?.disconnect(); run.node?.disconnect();
    void run.context?.close().catch(() => {});
    if (run.ws?.readyState === WebSocket.OPEN) {
      if (cancel) run.ws.send(JSON.stringify({ type: 'session.cancel' }));
      run.ws.close();
    }
  }
  async function finish() {
    const run = current.current;
    if (run.closed || run.stopped) return;
    run.stopped = performance.now(); setState('finalizing');
    run.source?.disconnect(); run.stream?.getTracks().forEach((track) => track.stop());
    if (run.source instanceof AudioBufferSourceNode) { run.source.onended = null; try { run.source.stop(); } catch { /* ended */ } }
    const node = run.node;
    if (node) {
      await new Promise<void>((resolve) => {
        const timeout = setTimeout(resolve, 500);
        const listener = (event: MessageEvent) => {
          if (event.data?.flushed) { clearTimeout(timeout); node.port.removeEventListener('message', listener); resolve(); }
        };
        node.port.addEventListener('message', listener); node.port.postMessage('flush');
      });
    }
    if (run.closed) return;
    if (run.ws?.readyState === WebSocket.OPEN) run.ws.send(JSON.stringify({ type: 'input.finish' }));
    run.finalTimer = setTimeout(() => { setError('Final transcript timed out. Partial text is unverified; start a new session.'); setState('failed'); cleanup(true); }, 60000);
  }
  async function start(input?: File) {
    cleanup(true);
    const run = { chunks: [] as ArrayBuffer[], words: new Map(), model: models.find((item) => item.key === model)?.id, started: performance.now(), closed: false } as typeof current.current;
    current.current = run; segments.current = new Map(); transcript.current = '';
    setText(''); setAudio(null); setError(''); setMetrics({}); setReport(''); setDraftJob(''); draftId.current = crypto.randomUUID(); setReviewed(false); setState('connecting');
    setSpeaker(null); setRoles({}); speakerId.current = crypto.randomUUID();
    if (!compact && params.has('speech_job')) { const updated = new URLSearchParams(params); updated.delete('speech_job'); setParams(updated, { replace: true }); }
    handlers.current.onStart?.();
    try {
      // Acquire microphone permission only as the direct consequence of a click.
      if (!input) run.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: false }, video: false });
      if (run.closed) { run.stream?.getTracks().forEach((track) => track.stop()); return; }
      run.context = new AudioContext({ sampleRate: 16000 });
      await run.context.resume();
      await run.context.audioWorklet.addModule('/scientific-speech/pcm-worklet.js');
      if (run.closed) return;
      let decoded: AudioBuffer | undefined;
      if (input) {
        if (input.size > 64 * 1024 * 1024) throw new Error('Live playback is limited to 64 MiB / 10 minutes; use batch for longer audio.');
        decoded = await run.context.decodeAudioData(await input.arrayBuffer());
        if (decoded.duration > 600) throw new Error('Live playback is limited to 10 minutes.');
      }
      const authorization = await request.post<{ ticket: string; path: string }>(`${BASE}/tickets`, { model });
      if (run.closed) return;
      const url = new URL(authorization.path, window.location.href); url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(url); run.ws = ws;
      ws.onopen = () => { if (!run.closed) ws.send(JSON.stringify({ type: 'relay.attach', ticket: authorization.ticket })); };
      ws.onerror = () => { if (!run.closed) { setError('Speech connection failed. Verify the selected endpoint and your platform key.'); setState('failed'); cleanup(true); } };
      ws.onclose = () => { if (!run.closed) { setError('Speech connection closed before completion. Partial text is not a final transcript.'); setState('failed'); cleanup(); } };
      ws.onmessage = (message) => {
        if (run.closed) return;
        try {
          const event: Event = JSON.parse(message.data);
          if (event.operation_id) setMetrics((value) => ({ ...value, operation: event.operation_id }));
          if (event.type === 'session.queued') setState('queued');
          if (event.type === 'session.ready') {
            if (run.node) return;
            run.node = new AudioWorkletNode(run.context!, 'scientific-pcm');
            run.node.port.onmessage = (packet) => {
              if (!(packet.data instanceof ArrayBuffer) || run.closed) return;
              if (ws.bufferedAmount > 256000) { setError('Audio upload could not keep pace; session stopped without replay.'); setState('failed'); cleanup(true); return; }
              run.chunks.push(packet.data); ws.send(packet.data);
            };
            run.node.connect(run.context!.destination); // The worklet outputs silence.
            if (decoded) {
              const source = run.context!.createBufferSource(); source.buffer = decoded;
              source.connect(run.node); source.connect(run.context!.destination);
              source.onended = () => void finish(); run.source = source; source.start();
            } else {
              run.source = run.context!.createMediaStreamSource(run.stream!); run.source.connect(run.node);
            }
            run.started = performance.now(); setState('listening');
          }
          if (event.type === 'transcript.partial' || event.type === 'transcript.final') {
            const value = transcriptEvent(segments.current, event);
            transcript.current = value; setText(value); handlers.current.onTranscript?.(value);
            if (event.type === 'transcript.final' && event.items) run.words.set(String(event.segment_id ?? event.sequence), event.items);
            if (value && run.first === undefined) { run.first = performance.now() - run.started; setMetrics((old) => ({ ...old, first: run.first })); }
          }
          if (event.type === 'session.completed') {
            if ([...segments.current.values()].some((segment) => !segment.final && segment.text)) {
              setError('The endpoint completed with unfinalized partial text. Review the retained text; it is not a complete transcript.'); setState('failed'); cleanup(); return;
            }
            setMetrics((old) => ({ ...old, final: performance.now() - (run.stopped || run.started) }));
            setAudio(wavBlob(run.chunks)); setState('completed'); cleanup();
          }
          if (event.type === 'session.cancelled') { setState('cancelled'); cleanup(); }
          if (event.type === 'session.error') { setError(`Speech stopped: ${event.code || 'unknown error'}. Partial text is unverified.`); setState('failed'); cleanup(); }
        } catch { setError('Invalid speech response; session stopped.'); setState('failed'); cleanup(true); }
      };
    } catch (problem) {
      if (!run.closed) { setError(problem instanceof Error ? problem.message : 'Could not start speech.'); setState('failed'); cleanup(true); }
    }
  }
  async function generateDraft() {
    if (draftBusy || draftJob) return;
    setDraftBusy(true); setReport('Submitting reviewed transcript…');
    try {
      const data = new FormData();
      data.append('file', new File([text], 'reviewed-live-transcript.txt', { type: 'text/plain' }));
      data.append('kind', 'transcript'); data.append('language', 'en'); data.append('idempotency_key', draftId.current);
      const job = await request.postMultiPart('/api/scientific-demos/clinical', data) as { id: string };
      setDraftJob(job.id);
      setReport(`Draft admitted: ${job.id}. See Your report jobs below; a clinician must review its source citations and withheld facts.`);
    } catch { setReport('Draft admission failed. Retry unchanged text with the same request ID; check existing report jobs first.'); }
    finally { setDraftBusy(false); }
  }
  async function identifySpeakers() {
    if ((!audio && !speaker?.id) || speakerBusy) return;
    setSpeakerBusy(true); setError('');
    try {
      if (speaker?.id) {
        setSpeaker(await request.post<SpeakerJob>(`${BASE}/diarization/${speaker.id}/resume`));
      } else {
        const words = [...current.current.words.values()].flat();
        if (!words.length) throw new Error('This endpoint returned no acoustic word timestamps. Speaker-attributed text cannot be produced without alignment.');
        const data = new FormData(); data.append('file', new File([audio!], 'live.wav', { type: 'audio/wav' }));
        data.append('words', JSON.stringify(words)); data.append('model', current.current.model || 'unknown'); data.append('idempotency_key', speakerId.current);
        const accepted = await request.postMultiPart(`${BASE}/diarization`, data) as SpeakerJob;
        setSpeaker(accepted); const updated = new URLSearchParams(params); updated.set('speech_job', accepted.id); setParams(updated, { replace: true });
      }
    } catch (problem) { setError(problem instanceof Error ? problem.message : 'Speaker job submission failed.'); }
    finally { setSpeakerBusy(false); }
  }
  const controls = <>
    <select aria-label="Speech model" value={model} disabled={busy} onChange={(event) => setModel(event.target.value)} className="max-w-48 rounded border border-border-medium bg-surface-primary p-1 text-xs">
      {models.length ? models.map((item) => <option key={item.key} value={item.key}>{item.label}</option>) : <option value="english">Nemotron English · default</option>}
    </select>
    <button id={compact ? 'audio-recorder' : 'clinical-microphone'} type="button" aria-label={state === 'listening' ? 'Stop microphone and finalize' : 'Start Nemotron microphone'}
      disabled={disabled || (busy && state !== 'listening')} aria-pressed={state === 'listening'} className="rounded p-2 hover:bg-surface-hover"
      onClick={() => state === 'listening' ? void finish() : void start()}>{state === 'listening' ? <Square size={18} /> : <Mic size={18} />}</button>
    {busy && <button type="button" aria-label="Cancel speech" onClick={() => { cleanup(true); setState('cancelled'); }} className="rounded p-2"><X size={18} /></button>}
    <span role="status" className="text-xs">{state}</span>
  </>;
  if (compact) return <div className="flex flex-wrap items-center gap-1" aria-label="Live Nemotron speech">{controls}{error && <span role="alert" className="max-w-64 text-xs text-status-error">{error}</span>}</div>;
  return <section className="my-4 rounded-xl border border-border-medium p-4" aria-label="Clinical live transcription">
    <h3 className="font-semibold">Live speech · synthetic / de-identified demo only</h3>
    <p className="my-2 text-sm">Partials can change. Stop to finalize, run speaker analysis, correct the transcript, then explicitly send it for a clinician-reviewed draft. Speaker analysis uses a separate Sortformer model and the ASR's actual word times.</p>
    <div className="flex flex-wrap items-center gap-2">{controls}</div>
    <div className="my-3 flex flex-wrap items-center gap-2"><label className="text-sm">Play a recorded consultation through the live pipeline <input type="file" accept="audio/*" disabled={busy} onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
      <button type="button" disabled={busy || !file} onClick={() => file && void start(file)} className="rounded border p-2">Play and transcribe live</button></div>
    {error && <p role="alert" className="my-2 text-status-error">{error}</p>}
    <textarea aria-label="Live transcript for review" value={text} readOnly={busy || draftBusy} onChange={(event) => { setText(event.target.value); setReviewed(false); setDraftJob(''); draftId.current = crypto.randomUUID(); }} rows={6} className="w-full rounded border border-border-medium bg-surface-primary p-3" />
    <p className="text-xs">First partial: {metrics.first === undefined ? '—' : `${(metrics.first / 1000).toFixed(2)}s`} · final after stop: {metrics.final === undefined ? '—' : `${(metrics.final / 1000).toFixed(2)}s`}{metrics.operation ? ` · operation ${metrics.operation}` : ''}</p>
    <p className="my-2 text-xs">Raw audio is buffered in your browser, not saved by the relay. Upstream inference receives the audio; endpoint isolation, retention and logging depend on the deployed configuration. This demo is not a HIPAA compliance claim.</p>
    {state === 'completed' && <div className="my-3 flex flex-wrap items-center gap-3">
      <button type="button" disabled={speakerBusy || speaker?.state === 'running' || speaker?.state === 'completed'} onClick={() => void identifySpeakers()} className="rounded border p-2">{speaker?.id ? 'Resume speaker analysis' : 'Identify anonymous speakers'}</button>
      <label className="text-sm"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} /> I reviewed the transcript, terminology, doses and negation</label>
      <button type="button" disabled={!reviewed || !text || draftBusy || Boolean(draftJob)} onClick={() => void generateDraft()} className="rounded border p-2">Generate clinical draft</button>
      {audio && <button type="button" onClick={() => { const url = URL.createObjectURL(audio); const a = document.createElement('a'); a.href = url; a.download = 'live-consultation.wav'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }} className="rounded border p-2">Save captured audio for diarization</button>}
    </div>}
    {speaker && <div className="my-3 rounded border border-border-medium p-3">
      <p role="status">Speaker job: {speaker.state} · {speaker.id}{speaker.error ? ` · ${speaker.error}` : ''}</p>
      {speaker.result && <>
        <p className="my-2 text-xs">Model speaker channels are anonymous, not identities. Assign roles only after listening; ambiguous/overlapping speech remains flagged. This is not clinically validated.</p>
        <div className="flex flex-wrap gap-2">{[...new Set(speaker.result.turns.map((turn) => turn.speaker))].filter((id) => /^speaker_\d$/.test(id)).map((id) => <label key={id} className="text-sm">{id} role <select className="rounded border bg-surface-primary p-1" value={roles[id] || ''} onChange={(event) => setRoles({ ...roles, [id]: event.target.value })}><option value="">Unassigned</option><option value="Clinician">Clinician (reviewer assigned)</option><option value="Patient">Patient (reviewer assigned)</option><option value="Other">Other (reviewer assigned)</option></select></label>)}</div>
        <button type="button" className="my-2 rounded border p-2" onClick={() => { setText(speaker.result!.turns.map((turn) => `[${roles[turn.speaker] || turn.speaker}${turn.flag ? `; ${turn.flag}` : ''}] ${turn.text}`).join('\n')); setReviewed(false); setDraftJob(''); draftId.current = crypto.randomUUID(); }}>Apply reviewed role labels to transcript</button>
        <details><summary>Timing and uncertainty evidence</summary><pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(speaker.result.turns, null, 2)}</pre></details>
      </>}
      <p className="mt-2 text-xs">This explicit speaker job saves captured audio and receipts on the demo server and uploads the audio to the platform's tenant-scoped artifact store.</p>
    </div>}
    {report && <p role="status" className="text-sm">{report}</p>}
  </section>;
}
