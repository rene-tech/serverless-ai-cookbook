export type StartupDescriptor = {
  session_id: string; startup_ready: boolean; terminal: boolean;
  deadline_at: number; startup_timeout_s: number;
};

export class StartupUnavailable extends Error {}

export class StartupError extends Error {
  constructor(public readonly code: 'invalid_descriptor' | 'identity_changed' | 'terminal' | 'expired' | 'startup_timeout') {
    super(code);
  }
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const aborted = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', aborted); resolve(); }, ms);
    signal.addEventListener('abort', aborted, {once: true});
  });
}

// Polling observes the existing authenticated session; it neither admits work
// nor consumes the one-use signaling ticket. The supplied deadline never moves.
export async function waitForStartup<T extends StartupDescriptor>(
  initial: T, read: (signal: AbortSignal) => Promise<T>, signal: AbortSignal,
  clock = Date.now, sleep = pause,
): Promise<T> {
  const started = clock();
  const until = Math.min(initial.deadline_at * 1000, started + initial.startup_timeout_s * 1000);
  let value = initial;
  while (true) {
    signal.throwIfAborted();
    if (typeof value.startup_ready !== 'boolean' || typeof value.terminal !== 'boolean' ||
        !Number.isFinite(value.deadline_at) || !Number.isFinite(value.startup_timeout_s) || value.startup_timeout_s <= 0)
      throw new StartupError('invalid_descriptor');
    if (value.session_id !== initial.session_id || value.deadline_at !== initial.deadline_at)
      throw new StartupError('identity_changed');
    if (value.terminal) throw new StartupError('terminal');
    if (clock() >= initial.deadline_at * 1000) throw new StartupError('expired');
    if (clock() >= until) throw new StartupError('startup_timeout');
    if (value.startup_ready) return value;
    await sleep(Math.min(1000, until - clock()), signal);
    signal.throwIfAborted();
    const request = new AbortController();
    const aborted = () => request.abort(signal.reason);
    signal.addEventListener('abort', aborted, {once: true});
    const timeout = setTimeout(() => request.abort(new StartupError(
      until === initial.deadline_at * 1000 ? 'expired' : 'startup_timeout',
    )), Math.max(0, until - clock()));
    try { value = await read(request.signal); }
    catch (error) {
      if (request.signal.aborted) throw request.signal.reason;
      if (!(error instanceof StartupUnavailable)) throw error;
    } finally { clearTimeout(timeout); signal.removeEventListener('abort', aborted); }
  }
}
