'use strict';

// Opt-in transport routing. Only an uncommitted LLM HTTP request can fall
// back; this module cannot execute tools or replay scientific operations.
const { randomUUID } = require('node:crypto');
const PUBLIC_BASE = 'https://api.tokenfactory.nebius.com/v1';
const retryable = new Set([408, 429, 500, 502, 503, 504]);

function base(value) {
  const url = new URL(value);
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('Provider base must be an HTTP(S) URL without credentials, query or fragment');
  }
  return url.href.replace(/\/$/, '');
}

function settings(env) {
  if (!env.SCIENTIFIC_CHAT_BASE_URL) {
    if (env.SCIENTIFIC_CHAT_FALLBACK_MODEL || env.SCIENTIFIC_CHAT_FALLBACK_BASE_URL) throw new Error('Fallback requires an explicit primary base URL');
    return null;
  }
  if (!env.SCIENTIFIC_CHAT_MODEL) throw new Error('Provider routing requires an explicit primary model');
  if (Boolean(env.SCIENTIFIC_CHAT_FALLBACK_MODEL) !== Boolean(env.SCIENTIFIC_CHAT_FALLBACK_BASE_URL)) throw new Error('Fallback model and base URL must be configured together');
  const firstTokenMs = Number(env.SCIENTIFIC_CHAT_PRIMARY_WAIT_MS || 20000);
  if (!Number.isInteger(firstTokenMs) || firstTokenMs < 1 || firstTokenMs > 90000) throw new Error('Primary wait must be between 1 and 90000 milliseconds');
  return { primary: base(env.SCIENTIFIC_CHAT_BASE_URL), model: env.SCIENTIFIC_CHAT_MODEL,
    catalog: base(env.SCIENTIFIC_CHAT_CATALOG_BASE_URL || PUBLIC_BASE), firstTokenMs,
    fallback: env.SCIENTIFIC_CHAT_FALLBACK_MODEL ? { base: base(env.SCIENTIFIC_CHAT_FALLBACK_BASE_URL), model: env.SCIENTIFIC_CHAT_FALLBACK_MODEL } : null };
}

// Buffer only the SSE preamble (role/keepalive). Once any text, reasoning,
// refusal or tool fragment arrives, return the stream and never switch it.
async function preamble(response, signal) {
  if (!response.ok || !response.headers.get('content-type')?.includes('text/event-stream') || !response.body) return response;
  const reader = response.body.getReader(), chunks = [], decoder = new TextDecoder();
  let pending = '', bytes = 0, ended = false;
  while (true) {
    signal.throwIfAborted();
    const next = await reader.read();
    if (next.done) { ended = true; break; }
    chunks.push(next.value); bytes += next.value.byteLength;
    pending += decoder.decode(next.value, { stream: true });
    const lines = pending.split(/\r?\n/); pending = lines.pop();
    let committed = bytes > 262144;
    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      const data = line.slice(5).trim();
      if (!data) continue;
      if (data === '[DONE]') { committed = true; continue; }
      try {
        const event = JSON.parse(data);
        if (event.error || event.choices?.some((choice) => choice.finish_reason ||
          Object.entries(choice.delta || {}).some(([key, value]) => key !== 'role' && value != null && value !== ''))) committed = true;
      } catch { committed = true; }
    }
    if (committed) break;
  }
  return new Response(new ReadableStream({
    async pull(controller) {
      try {
        if (chunks.length) { controller.enqueue(chunks.shift()); return; }
        if (ended) { controller.close(); return; }
        const next = await reader.read();
        if (next.done) controller.close(); else controller.enqueue(next.value);
      } catch (error) { controller.error(error); }
    },
    cancel(reason) { return reader.cancel(reason); },
  }), { status: response.status, statusText: response.statusText, headers: response.headers });
}

function noSdkRetry(response) {
  const headers = new Headers(response.headers); headers.set('x-should-retry', 'false');
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

function createRoutingFetch(fetchImpl, config, observe = () => {}) {
  return async function routingFetch(input, init) {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const method = init?.method || input?.method || 'GET';
    if (method.toUpperCase() !== 'POST' || url !== config.primary + '/chat/completions' || typeof init?.body !== 'string') return fetchImpl(input, init);
    let body;
    try { body = JSON.parse(init.body); } catch { return fetchImpl(input, init); }
    if (body.model !== config.model) return fetchImpl(config.catalog + '/chat/completions', init);
    const callerSignal = init.signal; callerSignal?.throwIfAborted();
    const id = randomUUID(), started = Date.now();
    const emit = (event, fields = {}) => observe({ event, request_id: id, elapsed_ms: Date.now() - started, ...fields });
    const controller = new AbortController();
    const signal = callerSignal ? AbortSignal.any([callerSignal, controller.signal]) : controller.signal;
    const timer = setTimeout(() => controller.abort(new DOMException('Primary provider wait elapsed', 'TimeoutError')), config.firstTokenMs);
    let response, reason;
    try {
      response = await preamble(await fetchImpl(url, { ...init, signal }), signal);
      if (!retryable.has(response.status)) {
        emit('provider_selected', { provider: 'primary', model: config.model, status: response.status });
        return noSdkRetry(response);
      }
      reason = 'http_' + response.status;
      if (!config.fallback) {
        emit('provider_failed', { provider: 'primary', reason });
        return noSdkRetry(response);
      }
      await response.body?.cancel();
    } catch (error) {
      if (callerSignal?.aborted) throw callerSignal.reason;
      if (!(error instanceof TypeError) && !['TimeoutError', 'AbortError'].includes(error?.name)) throw error;
      reason = controller.signal.aborted ? 'initial_response_timeout' : 'connection_error';
    } finally { clearTimeout(timer); }
    callerSignal?.throwIfAborted();
    if (!config.fallback) {
      emit('provider_failed', { provider: 'primary', reason });
      if (response) return noSdkRetry(response);
      return unavailable();
    }
    emit('provider_fallback', { provider: 'fallback', model: config.fallback.model, reason });
    try {
      const result = await fetchImpl(config.fallback.base + '/chat/completions', {
        ...init, body: JSON.stringify({ ...body, model: config.fallback.model }), signal: callerSignal,
      });
      emit('provider_selected', { provider: 'fallback', model: config.fallback.model, status: result.status });
      return noSdkRetry(result);
    } catch (error) {
      if (callerSignal?.aborted) throw callerSignal.reason;
      emit('provider_failed', { provider: 'fallback', reason: 'connection_error' });
      return unavailable();
    }
  };
}

function unavailable() {
  return new Response(JSON.stringify({ error: { message: 'Configured conversational providers are unavailable. No tool or scientific work was replayed.', type: 'provider_unavailable' } }),
    { status: 503, headers: { 'content-type': 'application/json', 'x-should-retry': 'false' } });
}

const config = settings(process.env);
if (config) globalThis.fetch = createRoutingFetch(globalThis.fetch.bind(globalThis), config,
  (event) => process.stderr.write(JSON.stringify({ component: 'scientific-provider-routing', ...event }) + '\n'));
module.exports = { settings, createRoutingFetch, preamble };
