/** Present measured scientific work using the current public operation contract. */
export type ScientificProgress = {
  schema?: string; available?: boolean; updated_at?: string | null; stale?: boolean | null;
  stale_after_seconds?: number; current_step_id?: string | null;
  steps?: { step_id?: string; state?: string; unit?: string; completed_units?: number | null;
    durable_completed_units?: number | null; target_units?: number | null; rate?: number | null;
    rate_unit?: string; observed_at?: string | null;
    durable_at?: string | null; rate_updated_at?: string | null; stale?: boolean | null }[];
};

const measured = (value: unknown): value is number => typeof value === 'number'
  && Number.isFinite(value) && value >= 0;
const quantity = (value: unknown, unit: string) => !measured(value) ? 'Unknown'
  : `${value === 0 ? '0' : value < 0.0001 ? value.toPrecision(4) : Number(value.toFixed(4))}${unit ? ` ${unit}` : ''}`;
const timestamp = (value?: string | null) => typeof value === 'string' && Number.isFinite(Date.parse(value))
  ? value : null;

/** Show only measured scientific units, never infer throughput from time or hardware. */
export function scientificProgressDisplay(progress?: ScientificProgress | null, now = Date.now()) {
  if (!progress || progress.schema !== 'scientific-ai/progress/v1') return null;
  const limit = measured(progress.stale_after_seconds) && progress.stale_after_seconds > 0
    ? progress.stale_after_seconds : 120;
  const expired = (at: string | null) => at !== null && (now - Date.parse(at)) > limit * 1000;
  return {
    available: progress.available === true,
    currentStep: progress.current_step_id,
    rows: (Array.isArray(progress.steps) ? progress.steps : []).map((step) => {
      const unit = step.unit || '';
      const observedAt = timestamp(step.observed_at) || timestamp(progress.updated_at);
      const rateAt = timestamp(step.rate_updated_at);
      const terminal = ['completed', 'succeeded', 'failed', 'cancelled', 'preempted', 'expired'].includes(step.state || '');
      const stale = progress.stale === true || step.stale === true || (!terminal && expired(observedAt));
      const rateStale = stale || (!terminal && expired(rateAt));
      return {
        id: step.step_id || 'Unspecified step', state: step.state || 'Unknown',
        completed: quantity(step.completed_units, unit),
        durable: quantity(step.durable_completed_units, unit),
        target: quantity(step.target_units, unit),
        rate: quantity(step.rate, step.rate_unit || ''),
        observedAt, durableAt: timestamp(step.durable_at), rateAt, stale, rateStale,
        rateLabel: rateStale ? 'Last measured rate (stale)' : !rateAt ? 'Measured rate (freshness unknown)' : 'Measured rate',
        freshness: stale ? 'Stale observation' : !observedAt ? 'Observation freshness unknown'
          : terminal ? 'Last recorded observation' : 'Latest observation',
      };
    }),
  };
}

export function runDisplay(run: { protocol?: string; status?: string; operation?: { protocol?: string; result_available?: boolean } }) {
  const protocol = run.protocol || run.operation?.protocol;
  const batch = protocol === 'scientific-batch-v1';
  const terminal = ['succeeded', 'failed', 'cancelled', 'completed', 'preempted', 'expired'].includes(run.status || '');
  const pending = !terminal;
  return {
    terminal,
    status: batch && run.status === 'running' ? 'Workflow active' : run.status || 'unknown',
    description: run.status === 'queued' ? 'Accepted; execution has not started'
      : run.status === 'failed' ? 'Execution failed. Inspect the operation reason and retrieve available diagnostic outputs before deciding on a new run.'
      : batch && pending ? 'Individual stages may be queued, loading or computing. Open Details for stage status.' : '',
    // A batch's generic started_at is orchestration, not GPU admission. The
    // observed BindCraft run spent18 minutes queued after that timestamp.
    // Do not present a zero wait or this interval as measured GPU execution.
    showComputeTiming: !batch,
    readyTimingLabel: 'Accepted → ready (includes queue)',
    showResult: run.operation?.result_available === true || ['succeeded', 'completed'].includes(run.status || ''),
  };
}

export function studyNotice(study: { state: string; operation_admission?: string; phase?: string;
  admission_reason?: { code?: string; message?: string; retry_after_seconds?: number };
  failure?: { type?: string; message?: string }; operations?: { operation_id: string }[] }) {
  if (study.operation_admission === 'unknown' || study.state === 'admission_pending') {
    return 'Submission acknowledgement is unconfirmed. Compute may be running. Reconnect to the saved receipt; do not submit again.';
  }
  if (['SourcePreflightError', 'ParameterPreflightError', 'ToolAvailabilityError'].includes(study.failure?.type || '') ||
      /no upload (?:was submitted|or inference was submitted)/i.test(study.failure?.message || '')) {
    return 'Input validation failed before this step was submitted. Correct the reported input or parameter against the live contract before starting a new run.';
  }
  if (study.state === 'waiting_admission') {
    const reason = study.admission_reason;
    return `The study is saved, but this operation has not been accepted. ${reason?.message || reason?.code || 'Admission reason is unavailable.'} Refresh status${reason?.retry_after_seconds ? ` after ${reason.retry_after_seconds}s` : ''} before retrying.`;
  }
  if (['observation_interrupted', 'observation_expired'].includes(study.state)) {
    return 'Status observation was interrupted. Compute may still be running. Refresh the existing operation; do not submit another copy.';
  }
  if (study.failure) return study.operations?.length
    ? 'The study needs attention. Inspect the operation status before deciding whether compute failed; retrieve available outputs without rerunning.'
    : 'The study stopped before a confirmed operation was recorded. Inspect the failure and saved receipt before starting a new run.';
  return study.operation_admission === 'not_admitted'
    ? 'Study orchestration is saved; no operation has been admitted yet.' : '';
}

export function resultFacts(value: unknown, prefix = '', depth = 0): { label: string; value: string }[] {
  if (value === null || value === undefined || depth > 5) return [];
  if (['string', 'number', 'boolean'].includes(typeof value)) {
    return typeof value === 'string' && value.length > 300 ? [] : [{ label: prefix.replace(/_/g, ' '), value: String(value) }];
  }
  if (Array.isArray(value)) {
    if (value.length <= 16 && value.every(item => ['string', 'number'].includes(typeof item))) {
      return value.length ? [{ label: prefix.replace(/_/g, ' '), value: value.join(' × ') }] : [];
    }
    return value.slice(0, 5).flatMap((item, index) => resultFacts(item, `${prefix} [${index + 1}]`, depth + 1)).slice(0, 60);
  }
  return Object.entries(value as Record<string, unknown>)
    .filter(([key]) => !/schema|sha256|revision|artifact|manifest|files|path|url|runtime|source|bundle|affine/i.test(key) || key === 'runtime_metrics')
    .flatMap(([key, item]) => resultFacts(item, prefix ? `${prefix} · ${key}` : key, depth + 1)).slice(0, 60);
}

/** A bounded observation ending is not the saved study or model timing out. */
export function studyDisplay(state: string) {
  if (state === 'observation_expired') {
    return {
      status: 'Waiting for an update',
      description: 'The status-check window ended, not the study. Checks continue automatically while the study supervisor is available.',
    };
  }
  if (state === 'waiting_admission') {
    return {
      status: 'Waiting to start',
      description: 'This step has not been accepted yet. Inspect the recorded admission reason before retrying.',
    };
  }
  if (state === 'observation_interrupted') {
    return {
      status: 'Reconnecting to the existing operation',
      description: 'A status connection was interrupted. Saved operation IDs are retained; do not submit another copy.',
    };
  }
  // Preserve terminal and unknown states; presentation never turns a failure
  // or unrecognized state into a successful or active run.
  return { status: state, description: '' };
}
