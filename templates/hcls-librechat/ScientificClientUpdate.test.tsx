import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ScientificClientUpdate from './ScientificClientUpdate';

const originalFetch = global.fetch;
let read: jest.Mock;
const answer = (revision: string | null, ok = true) => ({ ok, headers: { get: () => revision } });
beforeEach(() => {
  document.head.innerHTML = '<meta name="scientific-client-revision" content="release-one">';
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  read = jest.fn().mockResolvedValue(answer('release-one'));
  global.fetch = read;
});
afterEach(() => { global.fetch = originalFetch; jest.restoreAllMocks(); jest.useRealTimers(); });

test('a retained tab detects the next release without navigating or changing a draft', async () => {
  const reload = jest.spyOn(window, 'confirm').mockReturnValue(false);
  render(<><textarea aria-label="Unsent draft" defaultValue="keep this scientific request" /><ScientificClientUpdate /></>);
  await waitFor(() => expect(read).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  read.mockResolvedValue(answer('release-two'));
  fireEvent(window, new Event('focus'));
  await screen.findByRole('status', { name: 'Workspace update available' });
  expect(reload).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Unsent draft')).toHaveValue('keep this scientific request');
  fireEvent.click(screen.getByRole('button', { name: 'Reload to update' }));
  expect(reload).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText('Unsent draft')).toHaveValue('keep this scientific request');
  expect(read.mock.calls[0][1]).toMatchObject({ method: 'HEAD', cache: 'no-store', credentials: 'same-origin' });
});

test.each([null, 'release-one'])('no false notification for unchanged or absent revision %s', async (revision) => {
  read.mockResolvedValue(answer(revision));
  render(<ScientificClientUpdate />);
  await waitFor(() => expect(read).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('network errors and unsuccessful responses do not claim an update', async () => {
  read.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(answer('release-two', false));
  render(<ScientificClientUpdate />);
  await waitFor(() => expect(read).toHaveBeenCalledTimes(1));
  fireEvent(window, new Event('online'));
  await waitFor(() => expect(read).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('timer detects a deployment; hidden tabs wait and unmount aborts the read', async () => {
  jest.useFakeTimers();
  const view = render(<ScientificClientUpdate />);
  await act(async () => { await Promise.resolve(); });
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
  await act(async () => { jest.advanceTimersByTime(60_000); });
  expect(read).toHaveBeenCalledTimes(1);
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  read.mockImplementation(() => new Promise(() => {}));
  fireEvent(document, new Event('visibilitychange'));
  expect(read).toHaveBeenCalledTimes(2);
  fireEvent(window, new Event('focus'));
  expect(read).toHaveBeenCalledTimes(2);
  view.unmount();
  expect(read.mock.calls[1][1].signal.aborted).toBe(true);
  await act(async () => { jest.advanceTimersByTime(60_000); });
  expect(read).toHaveBeenCalledTimes(2);
});
