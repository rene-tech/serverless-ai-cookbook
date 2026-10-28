import { AppStreamer, EventStatus, StreamType } from '@nvidia/ov-web-rtc';
import { StartupError, StartupUnavailable, waitForStartup, type StartupDescriptor } from './startup';

// The owner-authenticated parent exchanges a one-use ticket for an HttpOnly
// session cookie, then posts this noncredential descriptor from the SAME origin.
// No API key, TURN secret or browser token is persisted in local/session storage.
type Descriptor = StartupDescriptor & {
  session_id: string; signaling_path: string;
  ice_servers: RTCIceServer[]; width?: number; height?: number; fps?: number; startup_timeout_s: number;
  mode?: 'portable'; access_token?: string; ice_transport_policy?: RTCIceTransportPolicy; media_host?: string; media_port?: number;
};
const status = document.querySelector<HTMLParagraphElement>('#status')!;
const video = document.querySelector<HTMLVideoElement>('#remote-video')!;
const stream = new AppStreamer();
let attached = false;
let streamStarted = false;
const attachment = new AbortController();
const attachForm = document.querySelector<HTMLFormElement>('#attach-form')!;
const expectedParent = window.opener ?? (window.parent !== window ? window.parent : null);
async function attach(d: Descriptor) {
  if (attached || attachment.signal.aborted) return;
  if (!d || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(d.session_id)) return;
  const signaling = new URL(d.signaling_path, location.origin);
  if (signaling.origin !== location.origin || signaling.search || signaling.hash ||
      !(signaling.pathname.endsWith(`/${d.session_id}/signaling`) || (d.mode === 'portable' && signaling.pathname === '/signaling'))) return;
  if (!Array.isArray(d.ice_servers) || (!d.ice_servers.length && d.mode !== 'portable') ||
      d.ice_servers.some(s => !s.username || !s.credential ||
        (Array.isArray(s.urls) ? s.urls : [s.urls]).some(u => !/^turns:[^?]+\?transport=tcp$/.test(u)))) return;
  attached = true;
  status.textContent = 'Starting the existing session; waiting for runtime readiness.';
  try {
    const descriptorPath = d.mode === 'portable' ? '/descriptor' : signaling.pathname.replace(/signaling$/, 'descriptor');
    const capability = d.access_token;
    d = await waitForStartup(d, async signal => {
      let response: Response;
      try {
        response = await fetch(descriptorPath, {credentials: 'same-origin', cache: 'no-store', signal,
          ...(d.mode === 'portable' ? {headers: {Authorization: `Bearer ${capability}`}} : {})});
      } catch (error) {
        if (signal.aborted) throw signal.reason;
        if (error instanceof TypeError) throw new StartupUnavailable();
        throw error;
      }
      if ([502, 503, 504].includes(response.status)) throw new StartupUnavailable();
      if (!response.ok) throw new Error('Session readiness is unavailable or attachment is no longer authorized.');
      const next = await response.json();
      if (next.signaling_path !== d.signaling_path || next.mode !== d.mode) throw new Error('Session descriptor changed.');
      return {...next, ...(d.mode === 'portable' ? {access_token: capability} : {})};
    }, attachment.signal);
    attachment.signal.throwIfAborted();
    status.textContent = 'Connecting. Media readiness is unknown until a video frame is decoded.';
    streamStarted = true;
    // Native session creation belongs to the App. The SDK must never ask a
    // streaming backend to allocate a second session or reconnect automatically.
    await stream.connect({streamSource: StreamType.DIRECT, streamConfig: {
      sessionId: d.session_id, newSession: false, maxReconnects: 0,
      signalingServer: location.hostname, signalingPort: Number(location.port || 443),
      signalingPath: signaling.pathname, forceWSS: true,
      connectivityTimeout: d.startup_timeout_s * 1000,
      ...(d.mode === 'portable' ? {authenticate: true, accessToken: d.access_token,
        mediaServer: d.media_host, mediaPort: d.media_port} : {}),
      iceServerConfiguration: {iceTransportPolicy: d.mode === 'portable' ? d.ice_transport_policy : 'relay', iceServers: d.ice_servers},
      videoElementId: 'remote-video', audioElementId: 'remote-audio',
      width: d.width ?? 1920, height: d.height ?? 1080, fps: d.fps ?? 60,
      // SDK6.7 invokes onStart for failed and intermediate states as well.
      // A callback alone is neither a connected stream nor a decoded frame.
      onStart: event => {
        if (attachment.signal.aborted) return;
        if (event.status === EventStatus.SUCCESS) {
          if (!video.videoWidth || video.readyState < 2)
            status.textContent = 'Stream connected; waiting for decoded media.';
        } else if (event.status === EventStatus.ERROR) {
          status.textContent = 'Streaming failed. The authenticated session status contains the actionable failure.';
        } else if (event.status === EventStatus.CANCELED) {
          status.textContent = 'Viewer connection stopped. Check the session status for native resource release.';
        } else {
          status.textContent = 'Connecting. Media readiness is unknown until a video frame is decoded.';
        }
      },
      onStop: () => { if (!attachment.signal.aborted) status.textContent = 'Stream stopped. Check the session status for native resource release.'; },
    }});
    attachment.signal.throwIfAborted();
    video.requestVideoFrameCallback(() => {
      if (attachment.signal.aborted) return;
      status.textContent = `Media decoded (${video.videoWidth} × ${video.videoHeight}). Click the viewport for keyboard and pointer control.`;
      if (d.mode !== 'portable') void fetch(signaling.pathname.replace(/signaling$/, 'media'), {method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({width: video.videoWidth, height: video.videoHeight})}).catch(() => {});
      expectedParent?.postMessage({type: 'isaac.media.decoded', session_id: d.session_id,
        width: video.videoWidth, height: video.videoHeight}, location.origin);
    });
  } catch (error) {
    if (attachment.signal.aborted) return;
    status.textContent = error instanceof StartupError
      ? ({terminal: 'This session has ended. No new session was started.',
          expired: 'The existing session deadline has elapsed.',
          startup_timeout: 'Runtime startup did not complete within the existing startup deadline. Check this session status.',
          invalid_descriptor: 'Runtime readiness is unavailable. Check this session status.',
          identity_changed: 'The session readiness identity changed; attachment stopped.'})[error.code]
      : 'Streaming failed. The authenticated session status contains the actionable failure.';
  }
}
window.addEventListener('message', async (event: MessageEvent<Descriptor>) => {
  if (event.origin !== location.origin || event.source !== expectedParent || !expectedParent) return;
  await attach(event.data);
});
// Standalone page opened by the same-origin App after authenticated creation.
// Its encrypted HttpOnly cookie is sent automatically; there is no token URL.
if (/\/[A-Za-z0-9_-]+\/viewer\/$/.test(location.pathname)) {
  fetch(location.pathname.replace(/viewer\/$/, 'descriptor'), {credentials: 'same-origin', cache: 'no-store', signal: attachment.signal})
    .then(r => { if (!r.ok) throw new Error('session authorization required'); return r.json(); })
    .then(attach).catch(() => { if (attachment.signal.aborted) return; status.textContent = 'Authenticate the same owner to reattach to this session.'; attachForm.hidden = false; });
} else if (/\/v1\/isaac\/interactive\/$/.test(location.pathname)) {
  attachForm.hidden = false;
  const ids = new URLSearchParams(location.hash.slice(1));
  (attachForm.elements.namedItem('session') as HTMLInputElement).value = ids.get('session_id') ?? '';
  (attachForm.elements.namedItem('handoff') as HTMLInputElement).value = ids.get('handoff_id') ?? '';
  history.replaceState(null, '', location.pathname);
} else if (location.pathname === '/') {
  attachForm.hidden = false;
  (attachForm.elements.namedItem('session') as HTMLInputElement).required = false;
  (attachForm.elements.namedItem('session') as HTMLInputElement).closest('label')!.hidden = true;
  (attachForm.elements.namedItem('handoff') as HTMLInputElement).closest('label')!.hidden = true;
  const keyLabel = (attachForm.elements.namedItem('key') as HTMLInputElement).closest('label')!;
  keyLabel.firstChild!.textContent = 'Your private session capability ';
  status.textContent = 'Attach to this on-premises session. No Scientific AI account is required.';
}
attachForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (location.protocol !== 'https:') { status.textContent = 'HTTPS is required.'; return; }
  const values = new FormData(attachForm);
  const sid = String(values.get('session') ?? '');
  const handoff = String(values.get('handoff') ?? '');
  const key = String(values.get('key') ?? '');
  (attachForm.elements.namedItem('key') as HTMLInputElement).value = '';
  if (location.pathname === '/') {
    try {
      const response = await fetch('/descriptor', {headers: {Authorization: `Bearer ${key}`}, cache: 'no-store', signal: attachment.signal});
      if (!response.ok) throw new Error('attachment refused');
      await attach({...await response.json(), access_token: key});
      attachForm.hidden = true;
    } catch { if (!attachment.signal.aborted) status.textContent = 'Session capability rejected or runtime unavailable.'; }
    return;
  }
  if (!/^ses-[0-9a-f]{16}$/.test(sid)) { status.textContent = 'Enter the native session ID from the create result.'; return; }
  const marker = location.pathname.indexOf('/v1/isaac/');
  if (marker < 0) return;
  try {
    const response = await fetch(`${location.pathname.slice(0, marker)}/v1/isaac/sessions/${sid}/attach`, {
      method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'Authorization': `Bearer ${key}`},
      body: JSON.stringify(handoff ? {handoff_id: handoff} : {}),
    });
    if (!response.ok) throw new Error('attachment refused');
    const value = await response.json();
    const target = new URL(value.viewer_path, location.origin);
    if (target.origin !== location.origin || !target.pathname.endsWith(`/${sid}/viewer/`)) throw new Error('invalid target');
    location.assign(target.href);
  } catch { status.textContent = 'Attachment was refused. Check the session ID, owner identity and native session status.'; }
});
document.querySelector('#disconnect')!.addEventListener('click', async () => {
  attachment.abort();
  if (streamStarted) await stream.terminate(false);
  status.textContent = 'Disconnected. Resource release is confirmed by the native session status.';
});

window.addEventListener('pagehide', () => {
  attachment.abort();
  if (streamStarted) void stream.terminate(false);
});
