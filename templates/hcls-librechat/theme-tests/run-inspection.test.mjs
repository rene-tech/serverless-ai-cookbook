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
      const datasets = {
        settings: { configured: true },
        studies: { data: [{ output_directory: 'study', title: 'Study', state: 'failed', phase: 'failure', completed_steps: [], step_count: 1, operations: [] }] },
        runs: { data: [{ id: 'op-fixture', model_id: 'fixture', status: 'succeeded' }] },
      };
      window.dependencies = {
        react: React,
        axios: {},
        'react-router-dom': {
          useSearchParams: () => [new URLSearchParams('tab=runs'), () => {}],
          Link: ({ to, ...props }) => React.createElement('a', { href: to, ...props }),
        },
        '@tanstack/react-query': {
          useQuery: (key) => ({ data: datasets[key[1]], isLoading: false }),
          useQueryClient: () => ({ invalidateQueries: () => { throw new Error('Inspection must not invalidate run history'); } }),
        },
        '@librechat/client': {
          Button: ({ size, variant, ...props }) => React.createElement('button', props),
          Input: (props) => React.createElement('input', props),
        },
        'librechat-data-provider': { request: { get: (url) => {
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
    await page.addScriptTag({ content: "ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(dependencies.Demos.default));" });
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
    await panel.getByText(/first response/).waitFor();
    await page.getByRole('button', { name: 'Result', exact: true }).click();
    const result = page.getByRole('region', { name: 'Result · op-fixture' });
    await checkFocusAndVisibility(result);
    assert.equal(await result.locator('pre').count(), 0, 'old response must disappear while loading');
    await page.evaluate(() => pending.shift().resolve({ result: 'saved output' }));
    await result.getByText(/saved output/).waitFor();
    // Repeating the same action must reveal the panel again, even for identical data.
    await page.getByRole('button', { name: 'Result', exact: true }).click();
    await checkFocusAndVisibility(result);
    await page.evaluate(() => pending.shift().reject({ message: 'fallback', response: { data: { error: 'Result unavailable' } } }));
    await result.getByRole('alert').waitFor();
    assert.equal(await result.getByRole('alert').textContent(), 'Result unavailable');
    assert.equal(await result.locator('pre').count(), 0);
    assert.equal(await result.getAttribute('aria-busy'), 'false');
    assert.deepEqual(await page.evaluate(() => calls), [
      '/api/scientific-demos/runs/op-fixture',
      '/api/scientific-demos/runs/op-fixture/result',
      '/api/scientific-demos/runs/op-fixture/result',
    ]);
  } finally { await page.close(); }
});
