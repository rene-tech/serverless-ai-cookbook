// Bounds orchestration, never scientific execution. No job APIs, credentials,
// provider routing or customer-global state belong in this module.
'use strict';

const { createHash } = require('node:crypto');
const { performance } = require('node:perf_hooks');
const { isHostBudgetNotice } = require('./scientific-study-admission.cjs');
const budgets = new WeakMap();
const type = (message) => message?.getType?.() ?? message?._getType?.() ?? message?.type;

function positiveInteger(env, name, fallback) {
  const value = env[name] === undefined ? fallback : Number(env[name]);
  if (!Number.isSafeInteger(value) || value < 1 || value > 2147483647) {
    throw new Error(`${name} must be a positive integer (milliseconds or rounds); zero does not disable the limit`);
  }
  return value;
}

function settings(env = process.env) {
  return {
    callMs: positiveInteger(env, 'SCIENTIFIC_AGENT_MODEL_DEADLINE_MS', 90000),
    turnMs: positiveInteger(env, 'SCIENTIFIC_AGENT_MODEL_TIME_MS', 300000),
    repeatRounds: positiveInteger(env, 'SCIENTIFIC_AGENT_REPEAT_ROUNDS', 2),
  };
}

class AgentBudgetStop extends Error {
  constructor(reason) {
    super(`Scientific agent paused: ${reason}`);
    this.name = 'AgentBudgetStop';
    this.code = 'SCIENTIFIC_AGENT_BUDGET';
    this.reason = reason;
  }
}

function currentTurn(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (type(messages[i]) === 'human' && !isHostBudgetNotice(messages[i])) return messages.slice(i + 1);
  }
  return messages;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(
    Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  return value;
}

function parseContent(content) {
  if (Array.isArray(content) && content.length === 1 && content[0]?.type === 'text') content = content[0].text;
  if (typeof content === 'string') {
    try { return JSON.parse(content); } catch { return content; }
  }
  return content;
}

// Deliberately conservative: exact tool name + arguments + result, not an LLM
// verdict on progress. New state, output, arguments or errors remain evidence.
// Only transport observation timestamps on known poll receipts are ignored;
// scientific time series and arbitrary tool payloads are never rewritten.
function fingerprint(call, result) {
  let content = parseContent(result.content);
  if (/^(read_execution|read_scientific_workflow)_mcp_environment-execution$/.test(call.name) &&
      content && !Array.isArray(content) && typeof content === 'object') {
    content = { ...content };
    for (const field of ['observed_at', 'checked_at', 'poll_after_ms', 'elapsed_ms']) delete content[field];
  }
  return createHash('sha256').update(JSON.stringify(canonical({
    name: call.name, args: call.args, status: result.status, content,
  }))).digest('hex');
}

function isBoundedJobObservation(call, result) {
  // An unchanged RUNNING receipt after a real bounded wait is normal for a
  // queued GPU operation or a long simulation, not repeated failed reasoning.
  // Exclude only this exact trusted helper contract. Completed jobs, errors,
  // zero-wait busy polling and arbitrary tools still count toward loop limits.
  if (call.name !== 'read_execution_mcp_environment-execution' || result.status === 'error') return false;
  const receipt = parseContent(result.content);
  const jobId = call.args?.job_id;
  const wait = call.args?.wait_seconds ?? 15;
  return typeof jobId === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(jobId) &&
    receipt?.job_id === jobId && ['pending', 'running'].includes(receipt.status) &&
    receipt.exit_code == null && !receipt.isError && !receipt.error &&
    Number.isInteger(wait) && wait > 0 && wait <= 30 &&
    receipt.requested_wait_seconds === wait &&
    Number.isFinite(receipt.effective_wait_seconds) && receipt.effective_wait_seconds > 0 &&
    receipt.effective_wait_seconds <= Math.min(wait, 25);
}

function repeatedRounds(messages) {
  const seen = new Set();
  let repeats = 0;
  let pending = null;
  for (const message of currentTurn(messages)) {
    if (type(message) === 'ai') {
      pending = message.tool_calls?.length ? { calls: message.tool_calls, results: new Map() } : null;
    } else if (type(message) === 'tool' && pending) {
      if (!pending.calls.some((call) => call.id === message.tool_call_id && call.name === message.name)) continue;
      pending.results.set(message.tool_call_id, message);
      if (pending.calls.every((call) => pending.results.has(call.id))) {
        const hashes = pending.calls
          .filter((call) => !isBoundedJobObservation(call, pending.results.get(call.id)))
          .map((call) => fingerprint(call, pending.results.get(call.id)));
        repeats = hashes.length && hashes.every((hash) => seen.has(hash)) ? repeats + 1 : 0;
        for (const hash of hashes) seen.add(hash);
        pending = null;
      }
    }
  }
  return repeats;
}

function stopText(stop, messages) {
  const reason = {
    model_deadline: 'The model exceeded its response-time budget.',
    turn_model_time: 'This turn reached its accumulated model-time budget.',
    repeated_tools: 'Repeated tool rounds returned no new evidence.',
  }[stop.reason];
  const ids = new Set();
  for (const message of currentTurn(messages)) {
    if (type(message) !== 'tool') continue;
    const receipt = parseContent(message.content);
    if (!receipt || typeof receipt !== 'object') continue;
    for (const value of [receipt.operation_id, receipt.job_id, receipt.study_id, receipt.execution_id]) {
      if (typeof value === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value)) ids.add(value);
    }
  }
  const retained = ids.size ? '\n\nPreviously reported work IDs: ' + [...ids].slice(0, 12).map((id) => `\`${id}\``).join(', ') + '.' : '';
  return `Agent paused — this request is incomplete. ${reason}\n\n` +
    'This limit stops model reasoning only. It does not cancel or resubmit scientific jobs. ' +
    'Existing tool results and files are retained; any already-submitted work keeps its own lifecycle. ' +
    'Check [Runs](/demos?tab=runs) for current status before retrying. ' +
    'To continue, ask to resume from the existing results and work IDs, not to launch the work again.' + retained;
}

class AgentBudget {
  constructor(options = settings(), clock = () => performance.now()) {
    this.options = options;
    this.clock = clock;
    this.usedMs = 0;
    this.halted = null;
  }

  check(messages) {
    if (this.halted) return this.halted;
    if (this.usedMs >= this.options.turnMs) this.halted = new AgentBudgetStop('turn_model_time');
    else if (repeatedRounds(messages) >= this.options.repeatRounds) this.halted = new AgentBudgetStop('repeated_tools');
    return this.halted;
  }

  // One lease spans the primary generation, empty-response recovery and any
  // existing provider-error handling. It never spans a ToolNode execution.
  start(parentSignal) {
    const controller = new AbortController();
    const started = this.clock();
    const remaining = Math.max(0, this.options.turnMs - this.usedMs);
    const allowance = Math.min(this.options.callMs, remaining);
    const reason = remaining <= this.options.callMs ? 'turn_model_time' : 'model_deadline';
    let closed = false;
    const expire = () => {
      this.halted ??= new AgentBudgetStop(reason);
      controller.abort(this.halted);
    };
    const parentAbort = () => controller.abort(parentSignal.reason);
    if (parentSignal?.aborted) parentAbort();
    else parentSignal?.addEventListener('abort', parentAbort, { once: true });
    if (this.halted) controller.abort(this.halted);
    else if (allowance === 0) expire();
    const timer = setTimeout(expire, allowance);

    return {
      signal: controller.signal,
      run: (invoke) => new Promise((resolve, reject) => {
        if (closed) return reject(new Error('Model-time lease is closed'));
        if (this.clock() - started >= allowance) expire();
        if (controller.signal.aborted) return reject(controller.signal.reason);
        const abort = () => { cleanup(); reject(controller.signal.reason); };
        const cleanup = () => controller.signal.removeEventListener('abort', abort);
        controller.signal.addEventListener('abort', abort, { once: true });
        // The deadline does not depend on the provider respecting cancellation.
        // Both fulfillment/rejection handlers remain attached to late work.
        Promise.resolve().then(() => {
          controller.signal.throwIfAborted();
          return invoke();
        }).then((value) => {
          if (this.clock() - started >= allowance) expire();
          cleanup();
          if (controller.signal.aborted) reject(controller.signal.reason);
          else resolve(value);
        }, (error) => {
          cleanup();
          reject(controller.signal.aborted ? controller.signal.reason : error);
        });
      }),
      close: () => {
        if (closed) return;
        closed = true;
        clearTimeout(timer);
        parentSignal?.removeEventListener('abort', parentAbort);
        this.usedMs += Math.max(0, this.clock() - started);
      },
    };
  }
}

function forRun(graph) {
  let entry = budgets.get(graph);
  if (!entry || entry.runId !== graph.runId) {
    entry = { runId: graph.runId, budget: new AgentBudget() };
    budgets.set(graph, entry);
  }
  return entry.budget;
}

module.exports = { AgentBudget, AgentBudgetStop, forRun, settings, repeatedRounds, stopText,
  isBudgetStop: (error) => error instanceof AgentBudgetStop,
  release: (graph) => budgets.delete(graph) };
