import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { request } from 'librechat-data-provider';
import ScientificStudyPreview, { scientificWorkflowPath } from './ScientificStudyPreview';

jest.mock('librechat-data-provider', () => ({ request: { get: jest.fn(), getResponse: jest.fn() } }));
const get = request.get as jest.Mock;
const getResponse = request.getResponse as jest.Mock;
const directory = "/workspace/qa/run";
const href = `/demos?tab=runs&workflow=${encodeURIComponent(directory)}`;
const state = (status = 'running') => ({ output_directory: directory, operations: [{step_id: "simulate", operation_id: "op-native-job"}], state: status, completed_steps: [], step_count: 2,
  model_progress: [{ study_step_id: 'simulate', operation_id: 'retained-operation', progress: {
    schema: 'scientific-ai/progress/v1', available: true, updated_at: new Date().toISOString(),
    gpu_type: 'DO-NOT-EXPOSE-HARDWARE', gpu_count: 8, image: 'DO-NOT-EXPOSE-IMAGE',
    steps: [{ step_id: 'production', state: status === 'completed' ? 'completed' : 'running', unit: 'ns',
      completed_units: 0.25, durable_completed_units: 0.2, target_units: 1, rate: 217.8, rate_unit: 'ns/day',
      rate_updated_at: new Date().toISOString(), observed_at: new Date().toISOString() }],
  } }], artifacts: [] });
function mount(link = href) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, cacheTime: 0 } },
    logger: { log: console.log, warn: console.warn, error: () => undefined } });
  return { client, ...render(<QueryClientProvider client={client}>
    <ScientificStudyPreview href={link}>Live progress and results</ScientificStudyPreview>
  </QueryClientProvider>) };
}
beforeEach(() => { get.mockReset(); getResponse.mockReset(); });

test('only exact internal study links are recognized', () => {
  expect(scientificWorkflowPath(href)).toBe(directory);
  for (const value of ['https://other.invalid'+href, '/demos?tab=runs', href+'&workflow='+directory,
    href+'&token=anything', href+'#fragment', '/demos?tab=workspace&workflow='+directory,
    '/demos?tab=runs&study=../other', 'javascript:alert(1)']) expect(scientificWorkflowPath(value)).toBeUndefined();
});

test('actual measured work and rate render without device/runtime details', async () => {
  get.mockResolvedValue(state());
  const view = mount();
  await screen.findByText('Measured rate: 217.8 ns/day');
  expect(screen.getByText('Completed: 0.25 ns · Target: 1 ns')).toBeInTheDocument();
  expect(screen.getByText('Durably checkpointed: 0.2 ns')).toBeInTheDocument();
  expect(view.container.textContent).not.toContain('DO-NOT-EXPOSE');
  expect(get).toHaveBeenCalledWith(`/api/scientific-demos/studies/status?output_directory=${encodeURIComponent(directory)}`);
  view.unmount(); view.client.clear();
});

test('unmeasured work remains unknown and explicit status refresh is read-only', async () => {
  get.mockResolvedValue({ output_directory: directory, operations: [{step_id: "simulate", operation_id: "op-native-job"}], state: 'queued' });
  const view = mount();
  await screen.findByText('Scientific progress and rate are not measured yet—not zero.');
  fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
  await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  expect(view.container.textContent).not.toContain('0 ns/day');
  view.unmount(); view.client.clear();
});

test('errors and wrong study identity are not converted to a completed result', async () => {
  get.mockResolvedValue({ output_directory: '/workspace/other', state: 'completed' });
  const view = mount();
  await screen.findByText(/Live status is unavailable/);
  expect(view.container.textContent).not.toContain('completed');
  expect(get).toHaveBeenCalledTimes(1);
  view.unmount(); view.client.clear();
});

test('failed state stays failed without exposing a raw traceback or resubmitting', async () => {
  get.mockResolvedValue({ output_directory: directory, operations: [{step_id: "simulate", operation_id: "op-native-job"}], state: 'failed', failure: { message: 'DO-NOT-EXPOSE-PRIVATE-TRACE' } });
  const view = mount();
  await screen.findByRole('alert');
  expect(screen.getByText('failed')).toBeInTheDocument();
  expect(view.container.textContent).not.toContain('DO-NOT-EXPOSE');
  expect(get).toHaveBeenCalledTimes(1);
  view.unmount(); view.client.clear();
});

test('completed saved results render automatically and foreign artifact links are ignored', async () => {
  get.mockResolvedValue({ ...state('completed'), artifacts: [
    { name: 'Measured GROMACS results', download_url: '/demos?tab=workspace&path=qa&file=native-timing-report.json' },
    { name: 'Raw trajectory', download_url: '/demos?tab=workspace&path=qa&file=trajectory.xtc' },
    { name: 'Untrusted external artifact', download_url: 'https://other.invalid/leak' },
  ] });
  const report = JSON.stringify({ schema: 'scientific-ai/native-md-timing-report/v1', complete: true,
    timing_rows: [{ engine: 'gromacs', step_id: 'production', performance_ns_per_day: 220.1 }] });
  getResponse.mockResolvedValue({ data: { size: report.length, text: async () => report } });
  const view = mount();
  await screen.findByText('Measured rate: 220.1 ns/day');
  expect(screen.getByRole('link', { name: 'Raw trajectory' })).toHaveAttribute('href', expect.stringContaining('trajectory.xtc'));
  expect(screen.queryByRole('link', { name: 'Untrusted external artifact' })).not.toBeInTheDocument();
  view.unmount(); view.client.clear();
});

test('live polling observes the same run then stops on terminal completion', async () => {
  jest.useFakeTimers();
  get.mockResolvedValueOnce(state()).mockResolvedValue(state('completed'));
  const view = mount();
  try {
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    await act(async () => { jest.advanceTimersByTime(5100); await Promise.resolve(); });
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    await act(async () => { jest.advanceTimersByTime(15000); await Promise.resolve(); });
    expect(get).toHaveBeenCalledTimes(2);
  } finally { view.unmount(); view.client.clear(); jest.useRealTimers(); }
});
