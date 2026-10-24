import { render, screen, waitFor } from '@testing-library/react';
import { request } from 'librechat-data-provider';
import WorkspaceToolReports, { workspaceToolReports } from './WorkspaceToolReports';
import WorkspaceReportPreview from './WorkspaceReportPreview';

jest.mock('librechat-data-provider', () => ({ request: { getResponse: jest.fn() } }));
const read = request.getResponse as jest.Mock;
const href = '/demos?tab=workspace&path=retained&file=retained%2Freport.html';
const output = `Verified workspace links:\n[Retained report](${href})`;
const html = '<html><body><h1>Measured retained result</h1><p>300.1 K</p></body></html>';
const call = (overrides: Record<string, unknown> = {}) => ({ type: 'tool_call', tool_call: {
  id: 'viewer-call', name: 'visualize_workspace_media_mcp_structure-viewer',
  runStepStatus: 'completed', progress: 1, output, ...overrides,
} });

beforeEach(() => {
  read.mockReset().mockImplementation(async (url: string) => {
    if (url.includes('report.json')) throw { response: { status: 404 } };
    return { data: { size: html.length, text: async () => html } };
  });
});

test('completed tool reports render outside closed tool details without an assistant relay', async () => {
  render(<WorkspaceToolReports content={[call()]} enabled>
    <details><summary>Viewer details</summary><pre>{output}</pre></details>
    <p>Completed.</p>
  </WorkspaceToolReports>);
  const frame = await screen.findByTitle('Scientific report');
  expect(frame.closest('details')).toBeNull();
  expect(frame.getAttribute('srcdoc')).toContain(html);
  expect(frame).toHaveAttribute('sandbox', 'allow-scripts');
  expect(frame.getAttribute('srcdoc')).toContain("connect-src 'none'");
  expect(screen.getByLabelText('Verified workspace reports')).toHaveClass('w-full', 'min-w-0');
  await waitFor(() => expect(read).toHaveBeenCalledTimes(2));
  expect(screen.queryByText(/could not be loaded/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Download JSON' })).not.toBeInTheDocument();
});

test('streamed completion appears once, survives later deltas and reopens from saved tool output', async () => {
  const view = render(<WorkspaceToolReports content={[call({ runStepStatus: undefined, progress: 0.5, output: null })]} enabled>
    <p>Working</p>
  </WorkspaceToolReports>);
  expect(read).not.toHaveBeenCalled();
  view.rerender(<WorkspaceToolReports content={[call()]} enabled><p>Working</p></WorkspaceToolReports>);
  const firstFrame = await screen.findByTitle('Scientific report');
  await waitFor(() => expect(read).toHaveBeenCalledTimes(2));
  const saved = [call(), { type: 'text', text: 'The result is ready.' }, call({ id: 'another-call' })];
  view.rerender(<WorkspaceToolReports content={saved} enabled><p>The result is ready.</p></WorkspaceToolReports>);
  expect(screen.getAllByTitle('Scientific report')).toHaveLength(1);
  expect(screen.getByTitle('Scientific report')).toBe(firstFrame);
  expect(read).toHaveBeenCalledTimes(2);
  view.unmount();
  render(<WorkspaceToolReports content={saved} enabled><p>The result is ready.</p></WorkspaceToolReports>);
  expect((await screen.findByTitle('Scientific report')).getAttribute('srcdoc')).toContain(html);
});

test('equivalent paths and a Markdown relay share one preview while original links remain', async () => {
  const alias = '/demos?file=report.html&path=retained&tab=workspace';
  render(<WorkspaceToolReports content={[call(), call({ id: 'second', output: `[Second label](${alias})` })]} enabled>
    <WorkspaceReportPreview href={alias}>Assistant report link</WorkspaceReportPreview>
  </WorkspaceToolReports>);
  await screen.findByTitle('Scientific report');
  await waitFor(() => expect(read).toHaveBeenCalledTimes(2));
  expect(screen.getAllByTitle('Scientific report')).toHaveLength(1);
  expect(screen.getByRole('link', { name: 'Assistant report link' })).toHaveAttribute('href', alias);
  expect(screen.getByRole('link', { name: 'Workspace file' })).toHaveAttribute('href', href);
});

test('preview ownership is local to this message, never shared across users or conversations', async () => {
  const view = render(<WorkspaceToolReports content={[call()]} enabled><span /></WorkspaceToolReports>);
  await screen.findByTitle('Scientific report');
  view.unmount();
  read.mockClear();
  render(<WorkspaceToolReports content={[]} enabled>
    <WorkspaceReportPreview href={href}>Independent message</WorkspaceReportPreview>
  </WorkspaceToolReports>);
  await screen.findByTitle('Scientific report');
  expect(read).toHaveBeenCalled();
});

test('user/edit content and unrelated tools do not trigger workspace reads', () => {
  const view = render(<WorkspaceToolReports content={[call()]} enabled={false}><p>User content</p></WorkspaceToolReports>);
  expect(read).not.toHaveBeenCalled();
  view.rerender(<WorkspaceToolReports content={[call({ name: 'read_file_mcp_other' })]} enabled><p>Tool text</p></WorkspaceToolReports>);
  expect(read).not.toHaveBeenCalled();
  expect(screen.queryByLabelText('Verified workspace reports')).not.toBeInTheDocument();
});

test.each(['failed', 'cancelled', 'in_progress'])('%s calls cannot advertise a verified report', (runStepStatus) => {
  expect(workspaceToolReports([call({ runStepStatus })])).toEqual([]);
});

test('current completed-progress output and serialized MCP text blocks use the same verified route', () => {
  for (const serialized of [output, JSON.stringify([{ type: 'text', text: output }]),
    JSON.stringify({ content: [{ type: 'text', text: output }, { type: 'resource', resource: { text: '<html>ignored</html>' } }] })]) {
    expect(workspaceToolReports([call({ output: serialized, runStepStatus: undefined })])).toEqual([
      { path: 'retained/report.html', href, label: 'Retained report' },
    ]);
  }
  expect(workspaceToolReports([call({ output: JSON.stringify({ isError: true, content: [{ type: 'text', text: output }] }) })])).toEqual([]);
  expect(workspaceToolReports([call({ output: 'Workspace file does not exist.', args: JSON.stringify({ files: [{ path: '/workspace/retained/report.html' }] }) })])).toEqual([]);
});

test('external, traversal, incomplete, non-HTML and arbitrary text links are never promoted', () => {
  for (const value of ['https://example.org' + href, 'javascript:alert(1)',
    '/demos?tab=workspace&path=../secret&file=report.html',
    '/demos?tab=workspace&path=retained&file=data.csv',
    '/demos?tab=workspace&path=retained&file=plot.png']) {
    expect(workspaceToolReports([call({ output: `[Result](${value})` })])).toEqual([]);
  }
  expect(workspaceToolReports([call({ output: '[Incomplete](' + href })])).toEqual([]);
  expect(workspaceToolReports([{ type: 'text', text: output }])).toEqual([]);
  for (const type of ['think', 'reasoning']) {
    expect(workspaceToolReports([{ ...call(), type, text: output }])).toEqual([]);
  }
  expect(workspaceToolReports([call({ output: JSON.stringify({ arbitrary: output }) })])).toEqual([]);
});
