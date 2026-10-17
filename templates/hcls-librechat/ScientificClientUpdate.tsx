import { useEffect, useState } from 'react';

/** A deployed UI does not replace JavaScript in an already open tab. */
export default function ScientificClientUpdate() {
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    const current = document.querySelector<HTMLMetaElement>('meta[name="scientific-client-revision"]')?.content;
    if (!current) return;
    let stopped = false;
    let pending: AbortController | undefined;
    const check = async () => {
      if (stopped || pending || document.visibilityState !== 'visible') return;
      const controller = new AbortController();
      pending = controller;
      const timeout = window.setTimeout(() => controller.abort(), 10_000);
      try {
        const response = await fetch(new URL('index.html', document.baseURI), {
          method: 'HEAD', cache: 'no-store', credentials: 'same-origin', signal: controller.signal,
        });
        const revision = response.headers.get('X-Scientific-Client-Revision');
        if (!stopped && response.ok && revision && revision !== current) setAvailable(true);
      } catch { /* Offline or unavailable is not evidence of an update. */ }
      finally { window.clearTimeout(timeout); pending = undefined; }
    };
    const timer = window.setInterval(check, 60_000);
    window.addEventListener('focus', check);
    window.addEventListener('online', check);
    document.addEventListener('visibilitychange', check);
    void check();
    return () => {
      stopped = true;
      window.clearInterval(timer);
      pending?.abort();
      window.removeEventListener('focus', check);
      window.removeEventListener('online', check);
      document.removeEventListener('visibilitychange', check);
    };
  }, []);
  if (!available) return null;
  return <aside role="status" aria-label="Workspace update available"
    className="fixed left-1/2 top-2 z-[1100] w-[min(92vw,560px)] -translate-x-1/2 rounded-xl border border-border-heavy bg-surface-primary p-3 text-sm text-text-primary shadow-lg">
    <strong>A workspace update is ready.</strong>
    <p>Reload to use the latest reports and tools. Save any unsent text first; running jobs continue.</p>
    <button type="button" className="mt-2 underline" onClick={() => {
      if (window.confirm('Reload this tab? Save any unsent text first. Saved conversations and running jobs remain.')) window.location.reload();
    }}>Reload to update</button>
  </aside>;
}
