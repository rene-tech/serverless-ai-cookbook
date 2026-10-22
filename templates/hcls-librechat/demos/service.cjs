/* Shared application service for the authenticated UI and per-user MCP. */
const fs = require('node:fs/promises');
const { createReadStream, constants } = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const ROOT = process.env.SCIENTIFIC_DEMOS_DIR || '/data/hcls-demos';
const PLATFORM = (process.env.SCIENTIFIC_MODELS_API_BASE_URL || 'https://89.169.99.188/v1').replace(/\/v1\/?$/, '');
const REPORT_MODEL = 'Qwen/Qwen3-235B-A22B-Instruct-2507';
const REPORT_PROVIDER = 'https://api.tokenfactory.nebius.com/v1';
const FILES = ['report.md', 'transcript.txt', 'follow-up.md', 'review.md', 'document.json', 'review.json', 'run.json'];
const WORKSPACE = process.env.SCIENTIFIC_WORKSPACE || '/workspace';
const RUN_ID = /^[a-f0-9-]{36}$/i;
const OPERATION_ID = /^(?:op-[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?|ses-[a-f0-9]{16}|sync-[a-z0-9](?:[a-z0-9-]{0,56}[a-z0-9])?)$/;
const TERMINAL_STATES = new Set(['succeeded', 'completed', 'failed', 'cancelled', 'preempted', 'expired']);
const hash = (text) => crypto.createHash('sha256').update(text).digest('hex');
const failure = (message, status = 400) => Object.assign(new Error(message), { status });
function publicError(error) {
  return { error: error.status === 500 || !error.status
    ? 'Workbench request failed. Refresh existing runs before submitting again.' : error.message,
  ...(error.code ? { code: error.code } : {}),
  ...(typeof error.retryable === 'boolean' ? { retryable: error.retryable } : {}),
  ...(typeof error.durable_admission === 'boolean' ? { durable_admission: error.durable_admission } : {}),
  ...(error.operation_id ? { operation_id: error.operation_id } : {}),
  ...(error.retry_after_seconds !== undefined ? { retry_after_seconds: error.retry_after_seconds } : {}) };
}
async function fileHash(filename) {
  const value = crypto.createHash('sha256');
  for await (const chunk of createReadStream(filename)) value.update(chunk);
  return value.digest('hex');
}

async function save(filename, value) {
  const temporary = `${filename}.${crypto.randomUUID()}.tmp`;
  await fs.writeFile(temporary, JSON.stringify(value, null, 2), { mode: 0o600 });
  await fs.rename(temporary, filename);
}
async function read(filename) { return JSON.parse(await fs.readFile(filename, 'utf8')); }
function directory(owner, id) {
  if (!owner || !/^[a-f0-9]{32}$/.test(id)) throw failure('Invalid job identity');
  return path.join(ROOT, hash(owner), id);
}
function privateKey(key) {
  if (!key || /\s/.test(key)) throw failure('Configure your Scientific AI API key in demo settings.', 401);
  return key;
}

const pickFields = (value, names) => value && typeof value === 'object' && !Array.isArray(value)
  ? Object.fromEntries(names.filter((name) => Object.prototype.hasOwnProperty.call(value, name)).map((name) => [name, value[name]])) : {};
const PROGRESS_FIELDS = ['schema', 'available', 'updated_at', 'stale', 'stale_after_seconds', 'current_step_id'];
const PROGRESS_STEP_FIELDS = ['step_id', 'state', 'unit', 'completed_units', 'durable_completed_units', 'target_units',
  'rate', 'rate_unit', 'rate_source', 'rate_window_seconds', 'initial_step', 'target_step', 'observed_step', 'durable_step', 'timestep_ps',
  'observed_at', 'durable_at', 'rate_updated_at', 'stale'];
function customerProgress(value) {
  if (!value || value.schema !== 'scientific-ai/progress/v1') return undefined;
  const scalars = (row, fields) => Object.fromEntries(Object.entries(pickFields(row, fields))
    .filter(([, item]) => item === null || ['string', 'boolean'].includes(typeof item)
      || (typeof item === 'number' && Number.isFinite(item))));
  return { ...scalars(value, PROGRESS_FIELDS), steps: (Array.isArray(value.steps) ? value.steps : [])
    .map((step) => scalars(step, PROGRESS_STEP_FIELDS)) };
}
// Status is a public scientific contract, not a dump of the execution backend.
function customerOperation(value) {
  const result = pickFields(value, ['id', 'operation_id', 'model_id', 'protocol', 'status', 'state', 'display_name',
    'created_at', 'accepted_at', 'activation_started_at', 'ready_at', 'started_at', 'completed_at', 'updated_at',
    'cancelled_at', 'duration_seconds', 'cold_start_seconds', 'queue_seconds', 'estimated_wait_seconds',
    'result_available', 'attempt', 'max_attempts', 'error_code', 'error_detail']);
  if (typeof value?.operation === 'string') result.operation = value.operation;
  const progress = customerProgress(value?.progress);
  if (progress) result.progress = progress;
  return result;
}
function normalizedOperation(envelope, expectedId) {
  const nested = envelope?.operation && typeof envelope.operation === 'object' ? envelope.operation : null;
  const sources = nested ? [envelope, nested] : [envelope];
  const ids = sources.flatMap(value => [value?.id, value?.operation_id]).filter(value => value !== undefined);
  if (!ids.length || ids.some(id => !OPERATION_ID.test(id) || id !== (expectedId || ids[0]))) {
    throw failure('Platform returned a mismatched operation.', 502);
  }
  // Status envelopes may be nested; every identity must name the same native execution.
  return customerOperation({ ...envelope, ...nested, id: ids[0], operation_id: ids[0] });
}
function customerCatalogItem(value) {
  return pickFields(value, ['id', 'model_id', 'display_name', 'description', 'enabled', 'capabilities', 'protocols',
    'license', 'operations', 'service_classes', 'mcp_tool_name', 'mcp_tool_description']);
}
async function platform(key, method, resource, body, idempotencyKey, timeoutMs = 45000) {
  privateKey(key);
  const allowed = resource === '/v1/models' || resource === '/v1/scientific-models' || resource === '/v1/storage'
    || resource === '/v1/storage/credentials'
    || /^\/v1\/operations\?limit=\d{1,3}(?:&cursor=[A-Za-z0-9_-]{1,256})?$/.test(resource)
    || /^\/v1\/operations\/[^/:?]+(?::cancel|\/(?:events|result))?$/.test(resource)
      && OPERATION_ID.test(resource.slice('/v1/operations/'.length).split(/[:/]/)[0])
    || /^\/v1\/workshop\/(catalog|runs(?:\/[a-f0-9-]{36}(?:\/(?:interventions|report|events))?)?)$/.test(resource);
  if (!allowed || !['GET', 'POST'].includes(method)) throw failure('Unsupported platform operation');
  let response;
  try {
    response = await fetch(PLATFORM + resource, { method, redirect: 'error', signal: AbortSignal.timeout(timeoutMs),
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json',
        ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  } catch (cause) {
    const error = failure('Platform connection interrupted. Check existing runs before retrying with the same request ID.', 503);
    // Private discriminator for an observation deadline, not an HTTP/backend
    // failure or caller cancellation. Never expose the raw transport error.
    error.platformTimeout = cause?.name === 'TimeoutError';
    throw error;
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = result.error && typeof result.error === 'object' ? result.error
      : result.detail && typeof result.detail === 'object' ? result.detail : result;
    const message = typeof result.detail === 'string' ? result.detail
      : detail.message || detail.detail || `Platform returned HTTP ${response.status}`;
    const error = failure(typeof message === 'string' ? message : `Platform returned HTTP ${response.status}`, response.status);
    error.code = detail.code || detail.error_code;
    error.retryable = typeof detail.retryable === 'boolean' ? detail.retryable : undefined;
    error.durable_admission = typeof detail.durable_admission === 'boolean' ? detail.durable_admission : undefined;
    error.operation_id = OPERATION_ID.test(detail.operation_id || '') ? detail.operation_id : undefined;
    const retryAfter = Number(response.headers.get('retry-after') ?? detail.retry_after_seconds);
    if (Number.isFinite(retryAfter) && retryAfter >= 0) error.retry_after_seconds = retryAfter;
    throw error;
  }
  return result;
}

async function platformBytes(key, resource) {
  privateKey(key);
  if (!/^\/v1\/artifacts\/[a-f0-9-]{36}\/content$/.test(resource)) throw failure('Unsupported platform artifact operation');
  let response;
  try {
    response = await fetch(PLATFORM + resource, { method: 'GET', redirect: 'error', signal: AbortSignal.timeout(45000),
      headers: { Authorization: `Bearer ${key}` } });
  } catch { throw failure('Artifact download interrupted. Retry the same result lookup; do not resubmit compute.', 503); }
  if (!response.ok) throw failure(`Platform artifact returned HTTP ${response.status}`, response.status);
  return Buffer.from(await response.arrayBuffer());
}

const USE_CASE_ORDER = [
  'Protein structures & complexes', 'Protein design & engineering',
  'Molecular design & docking', 'Molecular dynamics', 'Biomedical imaging & segmentation',
  'Speech & audio', 'Physical AI & robotics', 'Generative media',
  'Genomics', 'Aging & clinical biomarkers', 'Single-cell analysis',
  'General-purpose chat', 'Other',
];
const DEMO_PATTERNS = {
  'Protein structures & complexes': 'Open the returned structure in the 3D viewer and use model-reported confidence coloring only when the result actually contains confidence evidence.',
  'Protein design & engineering': 'Show the returned design artifacts and a 3D structure comparison after the live schema confirms those outputs.',
  'Molecular design & docking': 'Show the returned ranked poses and a synchronized receptor/ligand overlay after verifying the exact result contract.',
  'Molecular dynamics': 'Show the returned trajectory, energies and native checkpoint with the exact engine and input protocol. A short run does not establish equilibration or scientific convergence.',
  'Biomedical imaging & segmentation': 'Show the source beside the returned image or mask overlay; keep research-only limitations visible.',
  'Speech & audio': 'Show a synchronized transcript or speaker timeline from the returned artifact.',
  'Physical AI & robotics': 'Show source and returned video or dataset artifacts side by side, preserving the source action/data provenance.',
  'Generative media': 'Show the returned media artifact with its exact prompt and operation receipt.',
  Genomics: 'Plot only the sequence or summary values actually returned by the selected App.',
  'Aging & clinical biomarkers': 'Plot returned age estimates against a declared reference only when one was supplied.',
  'Single-cell analysis': 'Show the returned embedding or labels only when the result contract provides them.',
  'General-purpose chat': 'Show one bounded response with the exact model and request receipt.',
  Other: 'Show one returned artifact or metric supported by the App\'s live schema.',
};
const DEMO_OPERATION_PRIORITY = {
  'Protein structures & complexes': ['predict-structure', 'predict-protein-structure', 'predict-complex-structure'],
  'Protein design & engineering': ['design-backbone', 'scaffold-motif', 'design-binder', 'design-binders', 'design-protein'],
  'Molecular design & docking': ['dock', 'generate-molecule'],
  'Molecular dynamics': ['run-workflow'],
  'Biomedical imaging & segmentation': ['segment-cells', 'segment-ct', 'segment-track-media', 'analyze-image'],
  'Speech & audio': ['diarize', 'transcribe', 'synthesize'],
  'Physical AI & robotics': ['transfer-video', 'augment-lerobot-dataset', 'generate-media'],
  'Generative media': ['generate-video', 'generate-image', 'generate-music'],
};

function catalogContractError() {
  return Object.assign(failure('The authorized App catalog returned an unsupported response format. '
    + 'Contact support; do not interpret this as missing model access or a transient service failure.', 502),
  { code: 'CATALOG_CONTRACT_INVALID', retryable: false });
}

function appContract(item) {
  if (item.execution_mode === 'scientific-batch') return 'scientific-batch';
  if (item.protocol === 'native') return item.operations.includes('chat') ? 'chat' : 'native';
  if (item.protocol === 'openai-chat') return item.operations.includes('chat') ? 'chat' : 'openai-chat';
  throw catalogContractError();
}

function appUseCase(item) {
  const id = String(item.id || item.model_id || '').toLowerCase();
  const operations = (item.operations || []).map((value) => String(value).toLowerCase());
  const has = (...values) => values.some((value) => operations.includes(value));
  if (id === 'mdprecheck' && has('check-md-inputs')) return 'Molecular dynamics';
  // Native workflow engines do not all include "molecular dynamics" in their
  // display name (notably AMBER26 and distributed GROMACS). Classify their
  // stable App IDs before text search, without granting or inventing Apps.
  if (has('run-workflow') && ['amber', 'gromacs', 'gromacs-mpi', 'lammps', 'namd', 'openmm'].includes(id)) return 'Molecular dynamics';
  if (has('predict-structure', 'predict-protein-structure', 'predict-complex-structure', 'search-msa')
      || (has('predict') && /(?:fold|boltz)/.test(id))) return 'Protein structures & complexes';
  if (has('design-protein', 'design-binder', 'design-binders', 'design-backbone', 'scaffold-motif')) return 'Protein design & engineering';
  if (has('dock', 'generate-molecule')) return 'Molecular design & docking';
  if (has('analyze-image', 'segment-ct', 'segment-cells', 'segment-track-media')) return 'Biomedical imaging & segmentation';
  if (has('transcribe', 'diarize', 'synthesize')) return 'Speech & audio';
  if (has('transfer-video', 'augment-lerobot-dataset', 'generate-media') || id.includes('cosmos')) return 'Physical AI & robotics';
  if (has('generate-image', 'generate-video', 'generate-music')) return 'Generative media';
  if (has('generate-sequence')) return 'Genomics';
  if (has('predict-age')) return 'Aging & clinical biomarkers';
  if (has('fit-transform')) return 'Single-cell analysis';
  if (has('chat')) return 'General-purpose chat';
  return 'Other';
}

function recommendedApp(group) {
  const priorities = DEMO_OPERATION_PRIORITY[group.use_case] || [];
  for (const operation of priorities) {
    const app = group.apps.find((item) => item.operations?.includes(operation));
    if (app) return { app, operation };
  }
  const app = group.apps[0];
  return { app, operation: app.operations?.[0] || null };
}

async function listApps(key, query = '') {
  if (typeof query !== 'string' || query.length > 200) throw failure('Supply a short App name or capability.');
  // The current catalog includes both native Apps and scientific batches.
  // Capabilities are a structured object, not a list of protocol names.
  const catalog = await platform(key, 'GET', '/v1/models');
  if (catalog?.object !== 'list' || !Array.isArray(catalog.data)) throw catalogContractError();
  const apps = new Map();
  for (const item of catalog.data) {
    if (!item || typeof item.model_id !== 'string' || !item.model_id.trim() || item.id !== item.model_id
        || apps.has(item.model_id) || !Array.isArray(item.operations)
        || item.operations.some(operation => typeof operation !== 'string')
        || (item.display_name !== undefined && typeof item.display_name !== 'string')
        || (item.tool_name != null && typeof item.tool_name !== 'string')
        || (item.description !== undefined && typeof item.description !== 'string')) throw catalogContractError();
    const contractKind = appContract(item);
    apps.set(item.model_id, { model_id: item.model_id, display_name: item.display_name || item.model_id,
      use_case: appUseCase(item), contract_kind: contractKind, contract_kinds: [contractKind],
      operations: item.operations,
      ...(item.protocol ? { protocol: item.protocol } : {}),
      ...(item.tool_name ? { tool_name: item.tool_name } : {}),
      ...(item.description ? { description: item.description.slice(0, 500) } : {}),
    });
  }
  const normalizeSearch = (value) => value.toLowerCase().replace(/[-_]+/g, ' ').trim();
  const normalized = normalizeSearch(query);
  // Common requests for the whole catalog are not literal model-name filters.
  const search = /^(all|all apps|all models|everything|\*)$/.test(normalized) ? '' : normalized;
  const data = [...apps.values()].filter((item) => !search || normalizeSearch(JSON.stringify(item)).includes(search));
  const groups = USE_CASE_ORDER.map((useCase) => ({
    use_case: useCase,
    apps: data.filter((item) => item.use_case === useCase),
  })).filter((group) => group.apps.length).map((group) => {
    const selected = recommendedApp(group);
    return { ...group, recommended_demo: {
      model_id: selected.app.model_id,
      operation: selected.operation,
      presentation: DEMO_PATTERNS[group.use_case],
    } };
  });
  return { data, groups, count: data.length, total_authorized_count: apps.size,
    catalog_scope: search ? 'search_matches' : 'full_authorized_catalog',
    filter_applied: search || null, discovery_only: true,
    answer_rules: 'Name every returned App exactly once under its supplied use_case and contract_kind. '
      + (search ? 'These are literal phrase search matches, NOT the full authorization list. An empty search does not establish missing access. ' : 'This is the complete authorized catalog; do not probe additional domains to discover more Apps. ')
      + 'Recommend only the supplied recommended_demo for each group. Do not invent Apps, capabilities, artifacts, cross-App chains, runtime readiness, or scientific validity.',
    next_step: search
      ? 'For the complete catalog call workbench_list_apps with {} once. Do not retry synonyms to infer permissions. For a selected App, read get_model_schema.'
      : 'Answer from this complete catalog. Read get_model_schema only for a subsequently chosen App. Authorization is not runtime readiness or scientific validity.' };
}

async function retainResult(key, operationId, bytes) {
  return retainWorkspaceBytes(key, `.scientific-runs/${operationId}/result.json`, bytes);
}

function workspaceUrl(relative) {
  const directory = path.posix.dirname(relative);
  return '/demos?' + new URLSearchParams({ tab: 'workspace',
    path: directory === '.' ? '' : directory, file: relative }).toString();
}

async function retainWorkspaceBytes(key, relativePath, bytes) {
  if (!(await workspaceInfo(key)).mounted) return { saved: false, reason: 'No mounted workspace; use the authenticated panel download.' };
  const target = workspacePath(relativePath);
  await fs.mkdir(path.dirname(target.absolute), { recursive: true, mode: 0o700 });
  const expected = hash(bytes);
  try { await fs.writeFile(target.absolute, bytes, { mode: 0o600, flag: 'wx' }); }
  catch (error) { if (error.code !== 'EEXIST') throw error; }
  const actual = await fileHash(target.absolute);
  if (actual !== expected) throw failure('Saved result differs from the verified platform output; existing file was not overwritten.', 409);
  return { saved: true, path: target.absolute, relative_path: target.normalized,
    workspace_url: workspaceUrl(target.normalized), size_bytes: bytes.length, sha256: actual };
}

async function workshopRun(key, runId) {
  if (!RUN_ID.test(runId || '')) throw failure('Invalid consultation identity');
  const run = await platform(key, 'GET', `/v1/workshop/runs/${runId}`);
  if (run.id !== runId) throw failure('Consultation identity mismatch', 409);
  const bytes = Buffer.from(JSON.stringify(run));
  // An in-progress consultation changes. Keep content-addressed versions rather
  // than overwriting prior turns, judgments or interventions on Object Storage.
  const workspace_file = await retainWorkspaceBytes(key,
    `.scientific-workshops/${runId}/${hash(bytes)}.json`, bytes);
  return { run, workspace_file };
}

function numberSummary(values, kind, shape) {
  const finite = values.filter(Number.isFinite);
  let min; let max; let sum = 0;
  for (const value of finite) {
    min = min === undefined || value < min ? value : min;
    max = max === undefined || value > max ? value : max;
    sum += value;
  }
  return { type: kind, count: values.length, ...(shape ? { shape } : {}),
    finite_count: finite.length,
    ...(finite.length ? { min, max, mean: sum / finite.length } : {}) };
}

function summarizeResult(value, depth = 0) {
  if (value === null || ['boolean', 'number'].includes(typeof value)) return value;
  if (typeof value === 'string') {
    if (value.length <= 2048) return value;
    return { type: 'long-string', characters: value.length, sha256: hash(value), preview: value.slice(0, 320) };
  }
  if (depth >= 8) return { type: Array.isArray(value) ? 'array' : 'object', omitted_below_depth: depth };
  if (Array.isArray(value)) {
    if (value.every((item) => typeof item === 'number')) return numberSummary(value, 'numeric-array');
    if (value.length && value.every((row) => Array.isArray(row) && row.every((item) => typeof item === 'number'))) {
      return numberSummary(value.flat(), 'numeric-matrix', [value.length, ...new Set(value.map((row) => row.length))]);
    }
    if (value.length > 20) return { type: 'array', count: value.length,
      first_items: value.slice(0, 5).map((item) => summarizeResult(item, depth + 1)) };
    return value.map((item) => summarizeResult(item, depth + 1));
  }
  if (typeof value === 'object') return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, summarizeResult(item, depth + 1)]),
  );
  return String(value);
}

function evidenceGuidance(value, summary, artifact) {
  const observations = [
    `The complete JSON result artifact was verified at ${artifact.size_bytes} bytes with SHA-256 ${artifact.sha256}.`,
  ];
  const structures = Array.isArray(value?.structures_in_ranked_order) ? value.structures_in_ranked_order : [];
  if (structures.length) {
    observations.push(`${structures.length} structure record(s) are present in this result; this does not define the App's maximum output count.`);
    const first = structures[0];
    if (typeof first.relaxed === 'boolean') observations.push(`The first structure's explicit relaxed field is ${first.relaxed}.`);
    if (typeof first.runtime_origin === 'string') observations.push(`The first structure's runtime_origin is ${first.runtime_origin}; the label alone does not describe supported inputs.`);
    if (summary?.structures_in_ranked_order?.[0]?.predicted_aligned_error?.type === 'numeric-matrix') {
      observations.push('The full predicted_aligned_error matrix remains in the verified JSON artifact; chat receives only its numeric summary.');
    }
    if (summary?.structures_in_ranked_order?.[0]?.structure?.type === 'long-string') {
      observations.push('The structure text remains in the verified JSON artifact; chat receives a hash, length and preview rather than the complete coordinate string.');
    }
  }
  return {
    observations,
    interpretation_boundaries: [
      'Do not infer unsupported inputs, modalities, chain counts, ligands, batching or output cardinality from fields absent in one result.',
      'source_artifact.size_bytes is the complete result JSON artifact size, not the size of a nested PDB, SDF, image or other scientific object.',
      'Do not claim a separate downloadable nested artifact unless an explicit artifact reference is present.',
      'Confidence and scoring fields are model outputs, not experimental or clinical validation.',
      'For App-wide capabilities or constraints, consult the live model schema or an identified primary source.',
    ],
  };
}

async function operationResult(key, operationId) {
  if (!OPERATION_ID.test(operationId || '')) throw failure('Supply the native operation ID returned by submission.');
  // Scientific batch operations publish their scientific result directly;
  // endpoint and speech operations publish {operation, result}. These are
  // current execution contracts, each bound to the requested native identity.
  const [operationEnvelope, resultEnvelope] = await Promise.all([
    platform(key, 'GET', `/v1/operations/${operationId}`),
    platform(key, 'GET', `/v1/operations/${operationId}/result`),
  ]);
  const operation = normalizedOperation(operationEnvelope, operationId);
  const resultOperation = resultEnvelope.operation;
  if (resultOperation && typeof resultOperation === 'object') normalizedOperation(resultEnvelope, operationId);
  const result = resultOperation && typeof resultOperation === 'object' ? resultEnvelope.result : resultEnvelope;
  if (result?.schema !== 'fs2-serve.nebius.ai/operation-artifact-result/v1') {
    const workspace_file = await retainResult(key, operationId, Buffer.from(JSON.stringify(result)));
    return { operation, result: summarizeResult(result), workspace_file };
  }
  const artifact = result.artifact || {};
  if (result.content_type !== 'application/json' || artifact.compression !== 'none'
      || !RUN_ID.test(artifact.artifact_id || '') || !Number.isInteger(artifact.size_bytes)
      || artifact.size_bytes < 0 || artifact.size_bytes > 8 * 1024 * 1024
      || !/^[a-f0-9]{64}$/.test(artifact.sha256 || '')) {
    return { operation, result: { ...result, resolution: 'Download in Runs; this artifact is not bounded JSON.' } };
  }
  const bytes = await platformBytes(key, `/v1/artifacts/${artifact.artifact_id}/content`);
  if (bytes.length !== artifact.size_bytes || hash(bytes) !== artifact.sha256) throw failure('Result artifact failed size or SHA-256 verification.', 502);
  let parsed;
  try { parsed = JSON.parse(bytes.toString('utf8')); }
  catch { throw failure('Result artifact was declared as JSON but could not be decoded.', 502); }
  const summary = summarizeResult(parsed);
  const workspace_file = await retainResult(key, operationId, bytes);
  return { operation, workspace_file, result: {
    schema: 'fs2-serve.nebius.ai/resolved-operation-result/v1', content_type: result.content_type,
    source_artifact: artifact, summary, evidence_guidance: evidenceGuidance(parsed, summary, artifact),
    resolution: 'Downloaded with caller credentials; size and SHA-256 verified; large arrays and strings summarized.',
  } };
}

function runDirectory(owner, key) {
  if (!owner) throw failure('LibreChat user identity is missing.', 401);
  return path.join(ROOT, 'workbench', hash(owner), 'runs', hash(privateKey(key)));
}
async function optionalRead(filename, fallback) {
  try { return await read(filename); }
  catch (error) { if (error.code === 'ENOENT') return fallback; throw error; }
}
async function tracked(owner, key) {
  const folder = runDirectory(owner, key);
  let filenames;
  try { filenames = await fs.readdir(folder); }
  catch (error) { if (error.code !== 'ENOENT') throw error; filenames = []; }
  const current = await Promise.all(filenames.filter((name) => OPERATION_ID.test(name.replace(/\.json$/, ''))
    && name.endsWith('.json')).map((name) => read(path.join(folder, name))));
  // One atomic file per operation avoids lost updates when UI and MCP processes
  // save different operations concurrently.
  return { data: current };
}
async function saveRun(owner, key, entry) {
  const folder = runDirectory(owner, key);
  await fs.mkdir(folder, { recursive: true, mode: 0o700 });
  await save(path.join(folder, entry.id + '.json'), entry);
}
function runEntry(operation, previous = {}, metadata = {}) {
  operation = customerOperation(operation);
  return {
    id: operation.id, model_id: operation.model_id || previous.model_id || metadata.model_id,
    protocol: operation.protocol || previous.protocol, status: operation.status,
    source: previous.source || metadata.source || 'workbench',
    label: typeof metadata.label === 'string' ? metadata.label.slice(0, 160) : previous.label,
    first_seen_at: previous.first_seen_at || new Date().toISOString(),
    accepted_at: operation.accepted_at || operation.created_at || previous.accepted_at,
    started_at: operation.started_at, completed_at: operation.completed_at,
    updated_at: new Date().toISOString(), operation,
  };
}
async function track(owner, key, operationId, metadata = {}, timeoutMs = 45000) {
  if (!OPERATION_ID.test(operationId || '')) throw failure('Supply the native operation ID returned by submission.');
  const current = await platform(key, 'GET', `/v1/operations/${operationId}`, undefined, undefined, timeoutMs);
  const operation = normalizedOperation(current, operationId);
  const existing = await optionalRead(path.join(runDirectory(owner, key), operationId + '.json'), {});
  const entry = runEntry({ ...operation, ...(current.progress ? { progress: current.progress } : {}) }, existing, metadata);
  await saveRun(owner, key, entry);
  return entry;
}
async function waitOperation(owner, key, operationId, waitSeconds = 15) {
  if (!Number.isInteger(waitSeconds) || waitSeconds < 0 || waitSeconds > 30) throw failure('wait_seconds must be between 0 and 30.');
  const deadline = Date.now() + waitSeconds * 1000;
  const observations = [];
  let latest;
  while (true) {
    // A wakeup at the exact deadline must not launch one final 1ms request
    // which discards the valid running/queued state already observed.
    if (latest && Date.now() >= deadline) break;
    try {
      latest = await track(owner, key, operationId, { source: 'agent' }, waitSeconds ? Math.max(1, deadline - Date.now()) : 45000);
    } catch (error) {
      if (latest && waitSeconds && error.platformTimeout && Date.now() >= deadline) break;
      throw error;
    }
    if (observations.at(-1)?.status !== latest.status) observations.push({ status: latest.status, observed_at: latest.updated_at });
    if (TERMINAL_STATES.has(latest.status) || Date.now() >= deadline) break;
    await new Promise((resolve) => setTimeout(resolve, Math.min(3000, deadline - Date.now())));
  }
  return { ...latest, observations, terminal: TERMINAL_STATES.has(latest.status),
    wait_expired: Boolean(waitSeconds && !TERMINAL_STATES.has(latest.status) && Date.now() >= deadline),
    last_observed_at: latest.updated_at,
    next_step: TERMINAL_STATES.has(latest.status) ? 'Inspect the terminal state before retrieving output.'
      : 'Still accepted, not complete. Reconnect through Runs or use another bounded wait; do not resubmit or tight-loop polls.' };
}
async function runs(owner, key, { cursor, limit = 50 } = {}) {
  if (!Number.isInteger(limit) || limit < 1 || limit > 200
      || (cursor !== undefined && !/^[A-Za-z0-9_-]{1,256}$/.test(cursor))) {
    throw failure('Invalid operation history page.');
  }
  const existing = await tracked(owner, key);
  const history = await platform(key, 'GET', `/v1/operations?limit=${limit}${cursor ? `&cursor=${cursor}` : ''}`);
  if (!Array.isArray(history.data)) throw failure('Platform operation history has an invalid response.', 502);
  const byId = new Map(existing.data.map((item) => [item.id, item]));
  return { data: history.data.map((row) => {
    const operation = normalizedOperation(row);
    return runEntry(operation, byId.get(operation.id), { source: 'platform' });
  }),
    next_cursor: history.next_cursor || null, history_available: true };
}
async function studies(key, action = 'list', outputDirectory) {
  privateKey(key);
  const configured = process.env.SCIENTIFIC_MODELS_API_KEY;
  if (!configured || !crypto.timingSafeEqual(Buffer.from(hash(key)), Buffer.from(hash(configured)))) {
    throw failure('Whole studies belong to this dedicated user instance and its configured platform key. Use that original key; another account does not share its queue.', 403);
  }
  if (!['list', 'status', 'cancel'].includes(action) || (action !== 'list' &&
      (typeof outputDirectory !== 'string' || !outputDirectory.startsWith('/workspace/') ||
       outputDirectory.length > 1024 || outputDirectory.includes('\0') ||
       outputDirectory.split('/').some(part => ['.', '..'].includes(part))))) {
    throw failure('Invalid whole-study operation.');
  }
  // A saved workspace path does not substitute for the ordinary platform
  // key. workspaceInfo's mounted-folder shortcut is not a revocation check.
  await platform(key, 'GET', '/v1/storage');
  const command = process.env.SCIENTIFIC_CLIENT_PYTHON || '/opt/scientific-client/bin/python';
  const script = process.env.SCIENTIFIC_WORKFLOW_VIEW_SCRIPT || '/opt/bionemo/scientific_workflow_view.py';
  return new Promise((resolve, reject) => {
    const child = spawn(command, [script, `--${action}`, ...(action === 'list' ? [] : [outputDirectory])],
      { env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    const chunks = []; let bytes = 0; let settled = false;
    const fail = (message, code) => { if (!settled) { settled = true; reject(Object.assign(failure(message, 503), { code })); } };
    const timer = setTimeout(() => { child.kill('SIGTERM'); fail('Study storage observation timed out. The saved study continues; do not resubmit.', 'STUDY_OBSERVER_TIMEOUT'); }, 25000);
    child.stdout.on('data', (chunk) => {
      bytes += chunk.length;
      if (bytes > 4 * 1024 * 1024) { child.kill('SIGTERM'); fail('Study status is too large to display. Saved receipts and files are unchanged.', 'STUDY_OBSERVER_OUTPUT_LIMIT'); }
      else chunks.push(chunk);
    });
    // Raw tracebacks and environment details are never exposed to the browser.
    child.stderr.resume();
    child.once('error', () => { clearTimeout(timer); fail('Study observer is unavailable. Existing studies and their receipts are unchanged.', 'STUDY_OBSERVER_UNAVAILABLE'); });
    child.once('close', (code) => {
      clearTimeout(timer);
      if (settled) return;
      if (code !== 0) return fail('Study could not be observed for this user. Check its saved status; do not submit another copy.', 'STUDY_OBSERVER_EXIT');
      try { const result = JSON.parse(Buffer.concat(chunks).toString('utf8')); settled = true; resolve(result); }
      catch { fail('Study observer returned an invalid status; original work is unchanged.', 'STUDY_OBSERVER_INVALID_RESPONSE'); }
    });
  });
}

function workspacePath(relative = '') {
  if (typeof relative !== 'string' || relative.length > 1024 || relative.includes('\0')) throw failure('Invalid workspace path.');
  const normalized = relative.replace(/^\/+/, '');
  if (normalized.split('/').some((part) => part === '..')) throw failure('Workspace paths cannot escape the bucket.');
  const absolute = path.resolve(WORKSPACE, normalized);
  if (absolute !== path.resolve(WORKSPACE) && !absolute.startsWith(path.resolve(WORKSPACE) + path.sep)) throw failure('Invalid workspace path.');
  return { normalized, absolute };
}
async function workspaceInfo(key) {
  let mounted = false;
  try { mounted = (await fs.stat(WORKSPACE)).isDirectory(); } catch { /* no endpoint mount */ }
  if (mounted) return { state: 'ready', mode: 'deployment', mounted: true, mount_path: WORKSPACE,
    team_id: process.env.TEAM_ID, team_bucket_name: process.env.TEAM_BUCKET_NAME };
  const storage = await platform(key, 'GET', '/v1/storage').catch((error) => ({ state: 'unavailable', error: error.message }));
  return { ...storage, mounted: false };
}
async function workspaceList(key, relative = '', { offset = 0, limit = 500 } = {}) {
  if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(limit) || limit < 1 || limit > 500) throw failure('Invalid workspace page.');
  const info = await workspaceInfo(key);
  if (!info.mounted) throw failure('This deployment has no mounted workspace. Use the platform bucket credentials from your account until the shared-workbench S3 bridge is enabled.', 503);
  const target = workspacePath(relative);
  let entries;
  try { entries = await fs.readdir(target.absolute, { withFileTypes: true }); }
  catch (error) { if (error.code === 'ENOENT') throw failure('Workspace folder not found.', 404); throw error; }
  entries.sort((a, b) => Number(b.isDirectory()) - Number(a.isDirectory()) || a.name.localeCompare(b.name));
  const data = await Promise.all(entries.slice(offset, offset + limit).map(async (entry) => {
    const stat = await fs.stat(path.join(target.absolute, entry.name));
    return { name: entry.name, path: [target.normalized, entry.name].filter(Boolean).join('/'),
      kind: entry.isDirectory() ? 'directory' : 'file', size_bytes: entry.isFile() ? stat.size : undefined,
      updated_at: stat.mtime.toISOString() };
  }));
  return { info, prefix: target.normalized, data, total_entries: entries.length,
    next_offset: offset + limit < entries.length ? offset + limit : null };
}
async function workspacePut(key, relative, localPath) {
  const info = await workspaceInfo(key);
  if (!info.mounted) throw failure('This deployment has no mounted workspace.', 503);
  const target = workspacePath(relative);
  if (!target.normalized) throw failure('Choose a file name.');
  await fs.mkdir(path.dirname(target.absolute), { recursive: true, mode: 0o700 });
  const source = await fs.stat(localPath);
  try { await fs.copyFile(localPath, target.absolute, constants.COPYFILE_EXCL); }
  catch (error) { if (error.code === 'EEXIST') throw failure('A workspace object already exists at this path. Choose a new name.', 409); throw error; }
  const stat = await fs.stat(target.absolute);
  const [expected, actual] = await Promise.all([fileHash(localPath), fileHash(target.absolute)]);
  if (stat.size !== source.size || actual !== expected) {
    await fs.unlink(target.absolute).catch(() => {});
    throw failure('Workspace upload verification failed; the incomplete object was removed.', 503);
  }
  return { path: target.normalized, workspace_url: workspaceUrl(target.normalized),
    size_bytes: stat.size, sha256: actual, updated_at: stat.mtime.toISOString() };
}
async function workspaceGet(key, relative) {
  const info = await workspaceInfo(key);
  if (!info.mounted) throw failure('This deployment has no mounted workspace.', 503);
  const target = workspacePath(relative);
  const stat = await fs.stat(target.absolute).catch((error) => { if (error.code === 'ENOENT') throw failure('Workspace file not found.', 404); throw error; });
  if (!stat.isFile()) throw failure('Workspace path is not a file.');
  return { ...target, size_bytes: stat.size };
}
async function workspacePreview(key, relative) {
  const target = await workspaceGet(key, relative);
  const limit = 8 * 1024 * 1024;
  if (target.size_bytes > limit) throw failure('Report exceeds the inline preview limit. Download the complete original.', 413);
  const handle = await fs.open(target.absolute, 'r');
  try {
    const buffer = Buffer.alloc(limit + 1);
    let offset = 0;
    while (offset < buffer.length) {
      const { bytesRead } = await handle.read(buffer, offset, buffer.length - offset, offset);
      if (!bytesRead) break;
      offset += bytesRead;
    }
    if (offset > limit) throw failure('Report exceeds the inline preview limit. Download the complete original.', 413);
    return buffer.subarray(0, offset);
  } finally { await handle.close(); }
}
async function status(owner, id) {
  const dir = directory(owner, id);
  let receipt;
  try { receipt = await read(path.join(dir, 'status.json')); }
  catch { throw failure('Clinical job not found', 404); }
  if (['running', 'queued'].includes(receipt.status)) {
    let alive = false;
    try { alive = (await fs.readFile(`/proc/${receipt.pid}/stat`, 'utf8')).split(' ')[21] === receipt.process_start; } catch { /* process exited */ }
    if (!alive) {
      const latest = await read(path.join(dir, 'status.json'));
      receipt = ['running', 'queued'].includes(latest.status) ? { ...latest, status: 'interrupted', error: 'Worker stopped. Resume this job; do not upload again.' } : latest;
    }
  }
  const available = [];
  for (const name of FILES) {
    try { await fs.access(path.join(dir, 'output', name)); available.push(name); } catch { /* not produced */ }
  }
  const request = await read(path.join(dir, 'request.json')).catch(() => ({}));
  return { id, status: receipt.status, created_at: receipt.created_at, finished_at: receipt.finished_at,
    error: receipt.error, ...(receipt.error_code ? { error_code: receipt.error_code } : {}),
    files: available, model: REPORT_MODEL,
    input_provenance: { kind: request.kind, sha256: request.input_sha256,
      size_bytes: request.input_size_bytes, workspace_file: request.source_workspace },
    url: `/demos?tab=clinical&job=${id}`, clinical_validation: false };
}
async function list(owner) {
  const folder = path.join(ROOT, hash(owner));
  const entries = await fs.readdir(folder).catch(() => []);
  const jobs = await Promise.all(entries.filter((id) => /^[a-f0-9]{32}$/.test(id)).map((id) => status(owner, id)));
  return jobs.sort((a, b) => b.created_at.localeCompare(a.created_at));
}
async function start(owner, key, id) {
  const dir = directory(owner, id);
  const request = await read(path.join(dir, 'request.json'));
  if (request.key_hash !== hash(privateKey(key))) throw failure('Resume with the original submitting platform key.', 409);
  let lock;
  try { lock = await fs.open(path.join(dir, 'launch.lock'), 'wx', 0o600); }
  catch { throw failure('A launch is already in progress. Refresh job status.', 409); }
  try {
    const current = await status(owner, id);
    if (['completed', 'running', 'queued'].includes(current.status)) return current;
    await fs.unlink(path.join(dir, 'launched')).catch(() => {});
    const worker = spawn(process.execPath, [path.join(__dirname, 'worker.cjs'), dir], {
      detached: true, stdio: 'ignore', env: { PATH: process.env.PATH, LANG: 'C.UTF-8',
        FS2_API_KEY: key, CLINICAL_REPORT_API_KEY: process.env.NEBIUS_API_KEY || process.env.CLINICAL_REPORT_API_KEY || '',
        SCIENTIFIC_CLINICAL_PYTHON: process.env.SCIENTIFIC_CLINICAL_PYTHON || '/opt/clinical-client/bin/python',
        SCIENTIFIC_CLINICAL_SCRIPT: process.env.SCIENTIFIC_CLINICAL_SCRIPT || '/app/skill/clinical-documentation/scripts/clinical_report.py' },
    });
    await new Promise((resolve, reject) => { worker.once('spawn', resolve); worker.once('error', reject); });
    const processStart = (await fs.readFile(`/proc/${worker.pid}/stat`, 'utf8')).split(' ')[21];
    await save(path.join(dir, 'status.json'), { id, status: 'running', created_at: request.created_at,
      pid: worker.pid, process_start: processStart });
    // The child waits for this receipt, avoiding a fast-exit/parent-overwrite race.
    await fs.writeFile(path.join(dir, 'launched'), '', { mode: 0o600 });
    worker.unref();
    return status(owner, id);
  } finally { await lock.close(); await fs.unlink(path.join(dir, 'launch.lock')); }
}
async function clinical(owner, key, input) {
  privateKey(key);
  if (!['en', 'de'].includes(input.language)) throw failure('Choose English or German.');
  if (!['audio', 'transcript'].includes(input.kind)) throw failure('Choose audio or transcript.');
  if (!/^[A-Za-z0-9_.:-]{1,160}$/.test(input.idempotency_key || '')) throw failure('Supply an idempotency key.');
  if (!process.env.NEBIUS_API_KEY && !process.env.CLINICAL_REPORT_API_KEY) throw failure('The operator must configure the report provider credential.', 503);
  const ext = path.extname(input.filename || '').toLowerCase();
  if (!(input.kind === 'audio' ? ['.wav', '.flac', '.mp3', '.ogg', '.m4a', '.mp4', '.webm'] : ['.txt', '.json']).includes(ext)) throw failure('Unsupported input format.');
  const size = input.local_path ? (await fs.stat(input.local_path)).size : input.bytes?.length;
  if (!size || size > 512 * 1024 * 1024 || (!input.local_path && !Buffer.isBuffer(input.bytes))) throw failure('Upload a nonempty file, at most 512 MiB.');
  const id = hash(input.idempotency_key).slice(0, 32);
  const dir = directory(owner, id);
  const inputDigest = input.local_path ? await fileHash(input.local_path) : hash(input.bytes);
  const signature = hash(JSON.stringify([inputDigest, input.kind, input.language]));
  await fs.mkdir(path.dirname(dir), { recursive: true, mode: 0o700 });
  try { await fs.mkdir(dir, { mode: 0o700 }); }
  catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const existing = await read(path.join(dir, 'request.json')).catch(() => null);
    if (!existing) throw failure('Upload still being admitted; refresh and retry the same request ID.', 409);
    if (existing.signature !== signature || existing.key_hash !== hash(key)) throw failure('Request ID belongs to different input or credentials.', 409);
    return status(owner, id);
  }
  const source = `input${ext}`;
  if (input.local_path) await fs.copyFile(input.local_path, path.join(dir, source));
  else await fs.writeFile(path.join(dir, source), input.bytes, { mode: 0o600 });
  if (await fileHash(path.join(dir, source)) !== inputDigest) throw failure('Transcript changed during input capture; no report was started.', 409);
  await fs.chmod(path.join(dir, source), 0o600);
  await save(path.join(dir, 'request.json'), { source, kind: input.kind, language: input.language,
    signature, key_hash: hash(key), created_at: new Date().toISOString(), platform: PLATFORM,
    input_sha256: inputDigest, input_size_bytes: size, source_workspace: input.source_workspace,
    report_model: REPORT_MODEL, report_provider: REPORT_PROVIDER });
  await save(path.join(dir, 'status.json'), { id, status: 'prepared', created_at: new Date().toISOString() });
  return start(owner, key, id);
}
async function clinicalFromWorkspace(owner, key, relativePath, language, idempotencyKey) {
  const file = await workspaceGet(key, relativePath);
  if (!['.txt', '.json'].includes(path.extname(file.normalized).toLowerCase())) {
    throw failure('Choose an existing transcript .txt or ASR .json workspace file.');
  }
  return clinical(owner, key, { kind: 'transcript', language, idempotency_key: idempotencyKey,
    filename: path.basename(file.normalized), local_path: file.absolute,
    source_workspace: file.normalized });
}
async function output(owner, id, filename) {
  if (!FILES.includes(filename)) throw failure('Unknown report file', 404);
  try { return await fs.readFile(path.join(directory(owner, id), 'output', filename)); }
  catch (error) { if (error.code === 'ENOENT') throw failure('This report file has not been produced. Check job status.', 409); throw error; }
}
async function clinicalOutput(owner, key, id, filename) {
  const bytes = await output(owner, id, filename);
  const workspace_file = await retainWorkspaceBytes(key,
    `.scientific-clinical/${id}/${hash(bytes)}/${filename}`, bytes);
  return { bytes, workspace_file };
}
async function analyzeWorkspace(kind, key, args) {
  const analysis = require('./analysis.cjs');
  return kind === 'aging' ? analysis.aging(key, args, { workspaceGet, retainWorkspaceBytes })
    : kind === 'report' ? analysis.assembleReport(key, args, { workspaceGet, retainWorkspaceBytes })
    : kind === 'docking-batch' ? analysis.dockingBatch(key, args, { workspaceGet, retainWorkspaceBytes })
    : analysis.compare(kind, key, args, { workspaceGet, retainWorkspaceBytes });
}
module.exports = { platform, listApps, operationResult, workshopRun, summarizeResult, clinical, clinicalFromWorkspace, status, list, start, output, clinicalOutput, analyzeWorkspace, track, waitOperation, runs, studies, workspaceInfo, workspaceList,
  workspacePut, workspaceGet, workspacePreview, save, read, failure, publicError, customerOperation, customerProgress, customerCatalogItem, FILES, REPORT_MODEL };
