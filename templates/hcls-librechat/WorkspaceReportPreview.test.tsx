import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorkspaceReportPreview, { workspaceReportPath, isolatedReportHtml, precheckSummary, nativeMdSummary, readWorkspacePreview } from './WorkspaceReportPreview';
import { request } from 'librechat-data-provider';

jest.mock('librechat-data-provider', () => ({ request: { getResponse: jest.fn() } }));
const read = request.getResponse as jest.Mock;
const href = '/demos?tab=workspace&path=qa%2Fprecheck&file=report.html';
const html = '<html><head><title>Recorded check</title></head><body><h1>Recorded check</h1><script>document.body.dataset.ready="yes";</script></body></html>';
const summary = { schema: 'mdprecheck/check/v1', status: 'warn', verdict: 'Three findings need review',
  counts: { fail: 0, warn: 3, info: 18 } };
const blob = (text: string) => ({ size: text.length, text: async () => text });

beforeEach(() => { read.mockReset(); });

test('existing saved HTML links render inside the conversation with real verdict and downloads', async () => {
  read.mockImplementation(async (url: string) => ({ data: blob(url.includes('report.json') ? JSON.stringify(summary) : html) }));
  render(<WorkspaceReportPreview href={href}>Precheck report</WorkspaceReportPreview>);
  await screen.findByText('MD precheck: WARN');
  expect(screen.getByText(/Three findings need review/)).toBeInTheDocument();
  const frame = screen.getByTitle('Scientific report');
  expect(frame).toHaveAttribute('sandbox', 'allow-scripts');
  expect(frame).not.toHaveAttribute('src');
  expect(frame.getAttribute('srcdoc')).toContain(html);
  expect(frame.getAttribute('srcdoc')).toContain("connect-src 'none'");
  expect(frame.getAttribute('srcdoc')).toContain("default-src 'none'");
  expect(frame.getAttribute('sandbox')).not.toContain('allow-same-origin');
  expect(screen.getByRole('button', { name: 'Download HTML' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Download JSON' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Workspace file' })).toHaveAttribute('href', href);
  expect(read.mock.calls.map(([url]) => url)).toEqual([
    '/api/scientific-demos/workspace/preview?path=qa%2Fprecheck%2Freport.html',
    '/api/scientific-demos/workspace/preview?path=qa%2Fprecheck%2Freport.json',
  ]);
  fireEvent.click(screen.getByRole('button', { name: 'Collapse report' }));
  expect(screen.queryByTitle('Scientific report')).not.toBeInTheDocument();
});

test('a missing report is an explicit preview failure, never a fabricated pass or new run', async () => {
  read.mockRejectedValue(new Error('missing'));
  render(<WorkspaceReportPreview href={href}>Precheck report</WorkspaceReportPreview>);
  await screen.findByText(/could not be loaded/);
  expect(screen.queryByTitle('Scientific report')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Download HTML' })).toBeInTheDocument();
  expect(read).toHaveBeenCalledTimes(1);
});

test('old clients use one bounded read-only file fallback only for missing preview route', async () => {
  read.mockRejectedValueOnce({ response: { status: 404 } }).mockResolvedValueOnce({ data: blob(html) });
  expect(await (await readWorkspacePreview('qa/report.html')).text()).toBe(html);
  expect(read.mock.calls[1][0]).toBe('/api/scientific-demos/workspace/file?path=qa%2Freport.html');
  expect(read.mock.calls[1][1].headers.Range).toBe('bytes=0-8388608');
  for (const status of [401, 403, 500, 503]) {
    read.mockReset().mockRejectedValue({ response: { status } });
    await expect(readWorkspacePreview('qa/report.html')).rejects.toEqual({ response: { status } });
    expect(read).toHaveBeenCalledTimes(1);
  }
});

test('oversized preview responses or a legacy range-ignoring server stop at the preview bound', async () => {
  read.mockResolvedValue({ data: { size: 8388609 } });
  await expect(readWorkspacePreview('qa/report.html')).rejects.toThrow('preview_limit');
  read.mockReset().mockRejectedValueOnce({ response: { status: 404 } }).mockImplementationOnce(async (_url, options) => {
    options.onDownloadProgress({ loaded: 8388610 });
    expect(options.signal.aborted).toBe(true);
    throw new Error('cancelled');
  });
  await expect(readWorkspacePreview('qa/report.html')).rejects.toThrow('preview_limit');
});

test('only authenticated owned workspace report/media links get an automatic preview', () => {
  expect(workspaceReportPath(href)).toBe('qa/precheck/report.html');
  expect(workspaceReportPath('/demos?tab=workspace&path=qa&file=qa%2Freport.html')).toBe('qa/report.html');
  for (const file of ['chart.png', 'trajectory.mp4', 'native-timing-report.json']) {
    expect(workspaceReportPath(`/demos?tab=workspace&path=qa&file=${file}`)).toBe(`qa/${file}`);
  }
  for (const value of ['https://other.test' + href, 'javascript:alert(1)',
    '/demos?tab=workspace&path=qa&file=..%2Freport.html', '/demos?tab=workspace&path=qa&file=trajectory.xtc',
    '/demos?tab=workspace&path=qa&file=checkpoint.cpt', '/demos?tab=workspace&path=qa&file=arbitrary.json']) {
    expect(workspaceReportPath(value)).toBeUndefined();
  }
  expect(isolatedReportHtml(html).indexOf('Content-Security-Policy')).toBeLessThan(isolatedReportHtml(html).indexOf('<script>'));
  expect(precheckSummary({ status: 'pass', verdict: 'not a supported report' })).toBeNull();
});

test('native MD results show measured rates and unknown steps without runtime details', async () => {
  const data = { schema: 'scientific-ai/native-md-timing-report/v1', complete: true, timing_rows: [
    { engine: 'gromacs', step_id: 'production', performance_ns_per_day: 218.5, requested_steps: 5000000,
      executed_steps: null, durably_completed_steps: null, wall_seconds: 19.5,
      gpu_type: 'private-device', gpu_count: 8, command: ['private-runtime', '-gpu_id', '0'] }] };
  read.mockResolvedValue({ data: blob(JSON.stringify(data)) });
  render(<WorkspaceReportPreview href="/demos?tab=workspace&path=qa&file=native-timing-report.json">GROMACS results</WorkspaceReportPreview>);
  await screen.findByText('Saved MD measurements');
  expect(screen.getByText('Measured rate: 218.5 ns/day')).toBeInTheDocument();
  expect(screen.getByText(/Executed steps: Unknown/)).toBeInTheDocument();
  expect(screen.queryByText(/private-device|private-runtime/)).not.toBeInTheDocument();
  expect(JSON.stringify(nativeMdSummary(data))).not.toMatch(/private-|gpu|command/);
  expect(read).toHaveBeenCalledTimes(1);
});

test.each([['chart.png', 'image'], ['trajectory.mp4', 'video']])('real saved %s previews its existing bytes without generating anything', async (file, kind) => {
  const create = jest.fn(() => 'blob:owned-fixture');
  const revoke = jest.fn();
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
  URL.createObjectURL = create; URL.revokeObjectURL = revoke;
  read.mockResolvedValue({ data: new Blob(['recorded media fixture']) });
  try {
    const view = render(<WorkspaceReportPreview href={`/demos?tab=workspace&path=qa&file=${file}`}>Saved result</WorkspaceReportPreview>);
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    if (kind === 'image') expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:owned-fixture');
    else expect(screen.getByLabelText('Scientific trajectory video')).toHaveAttribute('src', 'blob:owned-fixture');
    expect(read).toHaveBeenCalledTimes(1);
    view.unmount();
    expect(revoke).toHaveBeenCalledWith('blob:owned-fixture');
  } finally { URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; }
});
