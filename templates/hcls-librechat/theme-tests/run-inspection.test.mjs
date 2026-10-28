import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const compile = (file) => ts.transpileModule(readFileSync(new URL(file, import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React },
}).outputText;
let browser;
before(async () => {
  browser = await chromium.launch(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {});
});
after(async () => { await browser?.close(); });

test('run inspection reveals loading, responses, repeat selections and errors in the scroll container', async () => {
  const page = await browser.newPage({ viewport: { width: 1000, height: 600 } });
  try {
    await page.setContent('<style>main { height: 500px; overflow-y: auto } article { height: 650px } pre { max-height: 200px; overflow: auto }</style><div id="root"></div>');
    await page.addScriptTag({ path: require.resolve('./node_modules/react/umd/react.development.js') });
    await page.addScriptTag({ path: require.resolve('./node_modules/react-dom/umd/react-dom.development.js') });
    await page.addScriptTag({ content: `
      window.calls = [];
      window.pending = [];
      window.queryErrors = {};
      window.datasets = {
        settings: { configured: true },
        studies: { data: [{ output_directory: 'study', title: 'Study', state: 'failed', phase: 'failure', completed_steps: [], step_count: 1, operations: [] }] },
        runs: { data: [{ id: 'op-fixture', model_id: 'fixture', status: 'running', operation: { result_available: true } }] },
      };
      window.dependencies = {
        react: React,
        axios: {},
        'react-router-dom': {
          useSearchParams: () => {
            const [params, setParams] = React.useState(new URLSearchParams(window.initialQuery || 'tab=runs'));
            window.navigate = value => setParams(new URLSearchParams(value));
            return [params, value => setParams(new URLSearchParams(value))];
          },
          Link: ({ to, ...props }) => React.createElement('a', { href: to, ...props }),
        },
        '@tanstack/react-query': {
          useQuery: (key) => ({ data: datasets[key[1]], error: queryErrors[key[1]], isLoading: false,
            dataUpdatedAt: 1793192400000, refetch: () => {} }),
          useQueryClient: () => ({ invalidateQueries: () => { throw new Error('Inspection must not invalidate run history'); } }),
        },
        '@librechat/client': {
          Button: ({ size, variant, ...props }) => React.createElement('button', props),
          Input: (props) => React.createElement('input', props),
        },
        'librechat-data-provider': { request: { post: () => { throw new Error('Observation must never POST'); }, get: (url) => {
          calls.push(url);
          return new Promise((resolve, reject) => pending.push({ resolve, reject }));
        }, getResponse: (url, options) => {
          if (options.responseType !== 'blob') throw new Error('Artifact must use authenticated download');
          calls.push(url);
          return new Promise((resolve, reject) => pending.push({ resolve, reject }));
        } } },
        './ScientificGettingStarted': {},
        './scientific-comparison': {},
      };
    ` });
    for (const [name, file] of [['./scientific-run-display', '../demos/run-display.ts'], ['Demos', '../demos/Demos.tsx']]) {
      await page.addScriptTag({ content: `{
        const module = { exports: {} }; const exports = module.exports;
        const require = (name) => window.dependencies[name];
        ${compile(file)}
        window.dependencies[${JSON.stringify(name)}] = module.exports;
      }` });
    }
    await page.addScriptTag({ content: "window.root = ReactDOM.createRoot(document.getElementById('root')); root.render(React.createElement(dependencies.Demos.default));" });
    const panel = page.getByRole('region', { name: 'Details · op-fixture' });
    const checkFocusAndVisibility = async (region) => {
      await region.waitFor();
      await page.waitForFunction(() => document.activeElement?.getAttribute('aria-labelledby') === 'run-inspection-title');
      const inside = await region.evaluate((element) => {
        const box = element.getBoundingClientRect();
        const container = element.closest('main').getBoundingClientRect();
        return box.top >= container.top && box.top < container.bottom;
      });
      assert.equal(inside, true, 'panel heading must be visible inside the nested scroll container');
    };
    await page.getByRole('button', { name: 'Details', exact: true }).click();
    await checkFocusAndVisibility(panel);
    assert.equal(await panel.getAttribute('aria-busy'), 'true');
    assert.equal(await panel.getByRole('status').textContent(), 'Loading details…');
    await page.evaluate(() => pending.shift().resolve({ detail: 'first response' }));
    await panel.getByText('first response', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Result', exact: true }).click();
    const result = page.getByRole('region', { name: 'Result · op-fixture' });
    await checkFocusAndVisibility(result);
    assert.equal(await result.locator('pre').count(), 0, 'old response must disappear while loading');
    await page.evaluate(() => pending.shift().resolve({ result: 'saved output' }));
    await result.getByText('saved output', { exact: true }).waitFor();
    // Repeating the same action must reveal the panel again, even for identical data.
    await page.getByRole('button', { name: 'Result', exact: true }).click();
    await checkFocusAndVisibility(result);
    await page.evaluate(() => pending.shift().reject({ message: 'fallback', response: { data: { error: 'Result unavailable' } } }));
    await result.getByRole('alert').waitFor();
    assert.match(await result.getByRole('alert').textContent(), /Output retrieval failed.*does not rerun compute/);
    await result.getByText('saved output', { exact: true }).waitFor();
    assert.equal(await result.locator('pre').count(), 1, 'last successful result is retained');
    assert.equal(await result.getAttribute('aria-busy'), 'false');
    assert.deepEqual(await page.evaluate(() => calls), [
      '/api/scientific-demos/runs/op-fixture',
      '/api/scientific-demos/runs/op-fixture/result',
      '/api/scientific-demos/runs/op-fixture/result',
    ]);
    await result.getByRole('button', { name: 'Retrieve outputs' }).click();
    await page.evaluate(() => pending.shift().resolve({ result: { frames_processed: 0, task_complete: false }, artifacts: [
      { name: 'segmentation', size_bytes: 5, download_url: '/api/scientific-demos/runs/op-fixture/artifacts/mask' },
      { name: 'foreign', size_bytes: 5, download_url: 'https://other.invalid/leak' },
    ] }));
    await result.getByText('false', { exact: true }).waitFor();
    assert.equal(await result.getByRole('button', { name: /foreign/ }).count(), 0);
    await result.getByRole('button', { name: /segmentation/ }).click();
    await page.evaluate(() => pending.shift().reject(new Error('Download interrupted')));
    await result.getByRole('alert').waitFor();
    await result.getByText('false', { exact: true }).waitFor();
    await result.getByRole('button', { name: /segmentation/ }).click();
    await page.evaluate(() => pending.shift().resolve({ data: new Blob(['mask']), headers: {} }));
    await result.getByRole('alert').waitFor({ state: 'detached' });
    assert.deepEqual((await page.evaluate(() => calls)).slice(-2), [
      '/api/scientific-demos/runs/op-fixture/artifacts/mask', '/api/scientific-demos/runs/op-fixture/artifacts/mask',
    ]);
    await result.getByRole('button', { name: /segmentation/ }).click();
    await page.evaluate(() => navigate('tab=runs&operation=op-other'));
    const other = page.getByRole('region', { name: 'Details · op-other' });
    await other.getByRole('status').waitFor();
    await page.evaluate(() => pending.shift().reject(new Error('Previous download failed')));
    await page.waitForFunction(() => pending.length === 1);
    assert.equal(await other.getByRole('alert').count(), 0, 'old download errors must not affect another operation');
    assert.equal(await other.getByRole('button', { name: 'Refresh operation' }).isDisabled(), true,
      'old download completion must not clear another request’s busy state');
    await page.evaluate(() => pending.shift().resolve({ operation: { id: 'op-other', status: 'running' } }));
    await other.getByText('running', { exact: true }).waitFor();
    await page.evaluate(() => {
      queryErrors.runs = new Error('offline');
      datasets.studies.data[0].state = 'needs_attention';
      datasets.studies.data[0].operation_admission = 'unknown';
      root.render(React.createElement(dependencies.Demos.default));
    });
    await page.getByText(/Operations status fetch failed/).waitFor();
    await page.getByText(/Submission acknowledgement is unconfirmed/).waitFor();
    await page.getByRole('cell', { name: /^running/ }).waitFor();
    await page.evaluate(() => {
      root.unmount(); window.initialQuery = 'tab=runs&operation=op-fixture';
      window.root = ReactDOM.createRoot(document.getElementById('root'));
      root.render(React.createElement(dependencies.Demos.default));
    });
    await page.waitForFunction(() => pending.length === 1);
    await page.evaluate(() => pending.shift().resolve({ operation: { id: 'op-fixture', status: 'running' } }));
    await panel.getByRole('button', { name: 'Refresh operation' }).waitFor();
    assert.equal((await page.evaluate(() => calls)).at(-1), '/api/scientific-demos/runs/op-fixture');
    await page.evaluate(() => {
      dependencies['librechat-data-provider'].request.put = async () => ({ configured: true });
      dependencies['librechat-data-provider'].request.post = async () => ({});
      dependencies['@tanstack/react-query'].useQueryClient = () => ({
        invalidateQueries: async () => {},
        resetQueries: async () => { window.scopeReset = true; },
      });
      root.render(React.createElement(dependencies.Demos.default));
    });
    await page.getByText('Platform connection · key configured for your account', { exact: true }).click();
    await page.getByRole('textbox', { name: 'Scientific AI API key' }).fill('another-fixture-key');
    await page.getByRole('button', { name: 'Save key', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('input[type="password"]').value === '');
    assert.equal(await page.getByRole('region', { name: 'Details · op-fixture' }).count(), 0,
      'changing keys must discard the previous key’s operation details');
    assert.equal(await page.evaluate(() => window.scopeReset), true, 'cached caller data must be reset');
  } finally { await page.close(); }
});
