/** Separate input transfers from model execution using the public operation contract. */
export type ScientificProgress = {
  schema?: string; available?: boolean; updated_at?: string | null; stale?: boolean | null;
  stale_after_seconds?: number; current_step_id?: string | null;
  steps?: { step_id?: string; state?: string; unit?: string; completed_units?: number | null;
    durable_completed_units?: number | null; target_units?: number | null; rate?: number | null;
    rate_unit?: string; completed_ns?: number | null; durable_completed_ns?: number | null;
    target_ns?: number | null; ns_per_day?: number | null; observed_at?: string | null;
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
  if (!progress || !['scientific-ai/progress/v1', 'scientific-ai/md-progress/v1'].includes(progress.schema || '')) return null;
  const limit = measured(progress.stale_after_seconds) && progress.stale_after_seconds > 0
    ? progress.stale_after_seconds : 120;
  const expired = (at: string | null) => at !== null && (now - Date.parse(at)) > limit * 1000;
  return {
    available: progress.available === true,
    rows: (Array.isArray(progress.steps) ? progress.steps : []).map((step) => {
      const md = step.unit === 'ns' || Object.prototype.hasOwnProperty.call(step, 'completed_ns');
      const unit = step.unit || (md ? 'ns' : '');
      const observedAt = timestamp(step.observed_at) || timestamp(progress.updated_at);
      const rateAt = timestamp(step.rate_updated_at);
      const terminal = ['completed', 'succeeded', 'failed', 'cancelled', 'preempted', 'expired'].includes(step.state || '');
      const stale = progress.stale === true || step.stale === true || (!terminal && expired(observedAt));
      const rateStale = stale || (!terminal && expired(rateAt));
      return {
        id: step.step_id || 'Unspecified step', state: step.state || 'Unknown',
        completed: quantity(step.completed_units === undefined ? step.completed_ns : step.completed_units, unit),
        durable: quantity(step.durable_completed_units === undefined ? step.durable_completed_ns : step.durable_completed_units, unit),
        target: quantity(step.target_units === undefined ? step.target_ns : step.target_units, unit),
        rate: quantity(step.rate === undefined ? step.ns_per_day : step.rate, step.rate_unit || (md ? 'ns/day' : '')),
        observedAt, durableAt: timestamp(step.durable_at), rateAt, stale, rateStale,
        rateLabel: rateStale ? 'Last measured rate (stale)' : !rateAt ? 'Measured rate (freshness unknown)' : 'Measured rate',
        freshness: stale ? 'Stale observation' : !observedAt ? 'Observation freshness unknown'
          : terminal ? 'Last recorded observation' : 'Latest observation',
      };
    }),
  };
}

export function runDisplay(run: { protocol?: string; status?: string; operation?: { protocol?: string } }) {
  const protocol = run.protocol || run.operation?.protocol;
  const upload = protocol === 'scientific-artifact-upload-v1';
  const batch = protocol === 'scientific-batch-v1';
  const terminal = ['succeeded', 'failed', 'cancelled', 'completed', 'preempted', 'expired'].includes(run.status || '');
  const pending = !terminal;
  return {
    upload, terminal,
    status: upload ? (pending ? 'Upload pending' : ['succeeded', 'completed'].includes(run.status || '')
      ? 'Upload finalized' : `Upload ${run.status}`)
      : batch && run.status === 'running' ? 'Workflow active' : run.status || 'unknown',
    description: upload && pending ? 'Waiting for input transfer or finalization; this is not inference.'
      : batch && pending ? 'Individual stages may be queued, loading or computing. Open Details for stage status.'
      : run.status === 'queued' ? 'Accepted; execution has not started' : '',
    // A batch's generic started_at is orchestration, not GPU admission. The
    // observed BindCraft run spent18 minutes queued after that timestamp.
    // Do not present a zero wait or this interval as measured GPU execution.
    showComputeTiming: !upload && !batch,
    readyTimingLabel: 'Accepted → ready (includes queue)',
    showResult: !upload && ['succeeded', 'completed'].includes(run.status || ''),
  };
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
      description: 'This step has not been accepted yet. The existing concurrency limit still applies.',
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
