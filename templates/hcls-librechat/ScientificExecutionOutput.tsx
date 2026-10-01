import { OutputRenderer } from './ToolOutput';

function object(raw?: string | null): Record<string, unknown> | null {
  try {
    let value = JSON.parse(raw || 'null');
    // MCP text blocks may be serialized around the actual tool response.
    if (Array.isArray(value) && value.length === 1 && value[0]?.type === 'text') {
      value = JSON.parse(value[0].text);
    }
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

export function executionOutput(input: string, output?: string | null) {
  const args = object(input);
  const result = object(output);
  const command = typeof args?.command === 'string' ? args.command : null;
  const job = typeof result?.job_id === 'string' ? result.job_id : null;
  const status = typeof result?.status === 'string' ? result.status : null;
  if (!command && !(job && status)) return null;
  return { command, job, status, result };
}

export default function ScientificExecutionOutput({ input, output }: {
  input: string; output?: string | null;
}) {
  const view = executionOutput(input, output);
  if (!view) return output ? <OutputRenderer text={output} /> : null;
  const { command, job, status, result } = view;
  const failed = ['failed', 'timed_out', 'interrupted'].includes(status || '');
  return (
    <section className="space-y-3" aria-label="Scientific execution details">
      {command && <div>
        <div className="mb-1 text-xs font-medium text-text-secondary">Command</div>
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-surface-tertiary p-2 text-xs">
          <code>{command}</code>
        </pre>
      </div>}
      {status && <div className={failed ? 'text-sm text-status-error' : 'text-sm text-text-primary'}>
        Execution: <strong>{status}</strong>
        {typeof result?.exit_code === 'number' && <> · exit {result.exit_code}</>}
        {job && <div className="mt-1 break-all font-mono text-xs">Job {job}</div>}
        {['starting', 'running', 'publishing', 'queued'].includes(status) &&
          <p className="mt-1 text-xs">Work is still in progress. This tool reply is not a completed scientific result.</p>}
      </div>}
      {typeof result?.output === 'string' && result.output && <div>
        <div className="mb-1 text-xs font-medium text-text-secondary">Output</div>
        <OutputRenderer text={result.output} />
      </div>}
      {typeof result?.error === 'string' && <p className="text-sm text-status-error">{result.error}</p>}
      {result?.more_output === true && <p className="text-xs text-text-secondary">
        More output is retained in the job log; the displayed chunk is not the full log.
      </p>}
      {output && <details>
        <summary className="cursor-pointer text-xs text-text-secondary">Execution receipt and full metadata</summary>
        <div className="mt-2"><OutputRenderer text={output} /></div>
      </details>}
    </section>
  );
}
