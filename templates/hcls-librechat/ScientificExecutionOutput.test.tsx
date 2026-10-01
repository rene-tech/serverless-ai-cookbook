import { render, screen } from '@testing-library/react';
import ScientificExecutionOutput, { executionOutput } from './ScientificExecutionOutput';
jest.mock('./ToolOutput', () => ({ OutputRenderer: ({ text }: { text: string }) => <pre>{text}</pre> }));

test('ordinary model tools retain their existing renderer', () => {
  expect(executionOutput('{"sequence":"ACGT"}', '{"score":0.9}')).toBeNull();
  render(<ScientificExecutionOutput input="{}" output="normal model result" />);
  expect(screen.getByText('normal model result')).toBeInTheDocument();
});
test('commands and logs are real multiline text, not escaped JSON or truncated parameters', () => {
  const command = "python - <<'PY'\nprint(42)\nPY";
  const output = JSON.stringify({ job_id: 'job-1', status: 'running', output: 'stage 1\nstage 2', more_output: true });
  render(<ScientificExecutionOutput input={JSON.stringify({ command })} output={output} />);
  expect(screen.getByText('Command')).toBeInTheDocument();
  expect(screen.getByText(/print\(42\)/).textContent).toBe(command);
  expect(screen.getByText('running')).toBeInTheDocument();
  expect(screen.getByText(/This tool reply is not a completed/)).toBeInTheDocument();
  expect(screen.getByText(/stage 1 stage 2/).textContent).toBe('stage 1\nstage 2');
  expect(screen.getByText(/More output is retained/)).toBeInTheDocument();
});
test('MCP wrapped result and failure remain visible after reconnect', () => {
  const output = JSON.stringify([{ type: 'text', text: JSON.stringify({
    job_id: 'saved-job', status: 'failed', exit_code: 2, error: 'missing topology', output: '' }) }]);
  render(<ScientificExecutionOutput input='{"job_id":"saved-job"}' output={output} />);
  expect(screen.getByText('failed')).toBeInTheDocument();
  expect(screen.getByText('missing topology')).toBeInTheDocument();
  expect(screen.getByText('Job saved-job')).toBeInTheDocument();
});
