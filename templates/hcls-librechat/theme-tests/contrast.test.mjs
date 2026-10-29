import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright';
import { build } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { brandClient, verifyBranding } from '../brand-client.mjs';
import { component, client, fixture, upstreamSource } from './fixture.mjs';

let browser, markup, css, theme, highContrast;
before(async () => {
  ({ markup, css, highContrast } = await fixture(await upstreamSource(), await readFile(join(client, 'demos/Demos.tsx'), 'utf8')));
  const dir = await mkdtemp(join(tmpdir(), 'scientific-theme-'));
  try {
    await writeFile(join(dir, 'index.html'), '<html><head><title>Test</title></head><body></body></html>');
    await brandClient(dir);
    theme = (await readFile(join(dir, 'index.html'), 'utf8')).match(/<style id="nebius-scientific-theme">[\s\S]*?<\/style>/)[0];
  } finally { await rm(dir, { recursive: true, force: true }); }
  browser = await chromium.launch(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {});
});
after(async () => { await browser?.close(); });

test('Apps discovery distinguishes loading, failed discovery and an empty authorized catalogue', async () => {
  const h = React.createElement;
  let discovery;
  const Demos = component(join(client, 'demos/Demos.tsx'), {
    axios: {},
    'react-router-dom': { Link: ({ to, ...props }) => h('a', { href: to, ...props }),
      useSearchParams: () => [new URLSearchParams('tab=apps'), () => {}] },
    '@tanstack/react-query': { useQueryClient: () => ({}), useQuery: (key) =>
      key[1] === 'settings' ? { data: { configured: true } } : key[1] === 'apps' ? discovery : {} },
    '@librechat/client': { Button: ({ variant, size, ...props }) => h('button', props),
      Input: (props) => h('input', props) },
    'librechat-data-provider': {}, './scientific-comparison': {}, './scientific-run-display': {},
    './ScientificGettingStarted': {},
  }).default;
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  try {
    for (const state of [503, 401, 403, 'loading', 'unavailable', 'empty', 'populated']) {
      discovery = { isLoading: state === 'loading',
        data: state === 'empty' ? { data: [] } : state === 'populated' ? { data: [{ id: 'synthetic-app' }] } : undefined,
        error: typeof state === 'number' ? { message: 'Discovery failed', response: { status: state, data: { error: 'Discovery failed' } } } : undefined };
      await page.setContent(renderToStaticMarkup(h(Demos)));
      assert.equal(await page.getByRole('status').count(), ['loading', 'empty'].includes(state) ? 1 : 0, String(state));
      assert.equal(await page.getByRole('alert').count(), typeof state === 'number' ? 1 : 0, String(state));
      assert.equal(await page.getByRole('article').count(), state === 'populated' ? 1 : 0, String(state));
      if (process.env.SCIENTIFIC_THEME_ARTIFACTS) {
        await page.screenshot({ path: join(process.env.SCIENTIFIC_THEME_ARTIFACTS, `apps-${state}.png`), fullPage: true });
      }
    }
  } finally { await page.close(); }
});

test('Workspace distinguishes folder states and hides cached files after access denial', async () => {
  const h = React.createElement;
  let listing;
  const Demos = component(join(client, 'demos/Demos.tsx'), {
    axios: {},
    'react-router-dom': { Link: ({ to, ...props }) => h('a', { href: to, ...props }),
      useSearchParams: () => [new URLSearchParams('tab=workspace&file=synthetic.txt'), () => {}] },
    '@tanstack/react-query': { useQueryClient: () => ({}), useQuery: (key) =>
      key[1] === 'settings' ? { data: { configured: true } } : key[1] === 'workspace' ? listing : {} },
    '@librechat/client': { Button: ({ variant, size, ...props }) => h('button', props), Input: (props) => h('input', props) },
    'librechat-data-provider': {}, './scientific-comparison': {}, './scientific-run-display': {}, './ScientificGettingStarted': {},
  }).default;
  const data = { info: { bucket_name: 'synthetic-bucket' }, data: [{ name: 'synthetic.txt', path: 'synthetic.txt',
    kind: 'file', size_bytes: 0, updated_at: '2026-01-01T00:00:00Z' }] };
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  try {
    for (const mode of ['light', 'dark', 'high-contrast-dark']) {
      for (const state of ['loading', 'empty', 'populated', 'refreshing', 'unknown', 'unavailable', 'stale', 401, 403]) {
        listing = { isLoading: state === 'loading', isFetching: state === 'refreshing', dataUpdatedAt: 1767225600000,
          data: ['populated', 'refreshing', 'stale', 401, 403].includes(state) ? data : state === 'empty' ? { ...data, data: [] } : undefined,
          error: ['unavailable', 'stale', 401, 403].includes(state) ? { message: 'Synthetic listing failure', response: {
            status: typeof state === 'number' ? state : 503, data: { error: 'Synthetic listing failure' } } } : undefined };
        await page.setContent('<html class="' + (mode.endsWith('dark') ? 'dark' : 'light') + '"><head>' + theme + '<style>' + css + '</style></head><body>' + renderToStaticMarkup(h(Demos)) + '</body></html>');
        if (mode.startsWith('high-contrast')) await page.evaluate(palette => {
          for (const [name, value] of Object.entries(palette)) document.documentElement.style.setProperty(name, value);
        }, highContrast.highContrastDarkTheme);
        const visible = ['populated', 'refreshing', 'stale'].includes(state);
        assert.equal(await page.getByRole('button', { name: 'synthetic.txt', exact: true }).count(), visible ? 1 : 0, String(state));
        assert.equal(await page.getByRole('button', { name: 'Download selected file' }).count(), visible ? 1 : 0, String(state));
        assert.equal(await page.getByText('This folder is empty.', { exact: true }).count(), state === 'empty' ? 1 : 0, String(state));
        if (state === 'loading' || state === 'refreshing') assert.ok(await page.getByRole('status').count());
        if (listing.error) assert.ok(await page.getByRole('alert').count());
        if (state === 'stale') assert.ok(await page.getByText(/last known listing/i).count());
        if (process.env.SCIENTIFIC_THEME_ARTIFACTS) await page.screenshot({ path: join(process.env.SCIENTIFIC_THEME_ARTIFACTS, 'workspace-' + mode + '-' + state + '.png'), fullPage: true });
      }
    }
  } finally { await page.close(); }
});

// Measure rendered text, including inherited colors, transparent backgrounds,
// opacity and placeholder text. A class-name assertion cannot catch this bug.
async function contrast(page) {
  return page.evaluate(() => {
    const rgba = (css) => {
      const match = css.match(/^rgba?\(([^)]+)\)$/);
      if (!match) throw new Error(`Unsupported computed color: ${css}`);
      const channels = match[1].split(/[, /]+/).map(Number);
      return [...channels.slice(0, 3), channels[3] ?? 1];
    };
    const blend = (fg, bg) => fg.slice(0, 3).map((v, i) => v * fg[3] + bg[i] * (1 - fg[3]));
    const background = (el) => {
      if (!el) return [255, 255, 255];
      const style = getComputedStyle(el);
      if (style.backgroundImage !== 'none') throw new Error('Gradient needs explicit contrast coverage');
      return blend(rgba(style.backgroundColor), background(el.parentElement));
    };
    const luminance = (rgb) => rgb.map((v) => {
      v /= 255;
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
    const results = [];
    const measure = (el, text, pseudo) => {
      if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) || el.closest('[aria-hidden="true"]')) return;
      const style = getComputedStyle(el, pseudo);
      const bg = background(el);
      const fg = rgba(style.color);
      for (let ancestor = el; ancestor; ancestor = ancestor.parentElement) fg[3] *= Number(getComputedStyle(ancestor).opacity);
      const a = luminance(blend(fg, bg)), b = luminance(bg);
      results.push({ text: text.slice(0, 75), tag: el.tagName, foreground: style.color,
        background: bg, ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) });
    };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.textContent.trim() && !['SCRIPT', 'STYLE'].includes(node.parentElement.tagName)) {
        measure(node.parentElement, node.textContent.trim());
      }
    }
    document.querySelectorAll('textarea, input').forEach((el) => {
      measure(el, el.value);
      if (el.placeholder) measure(el, el.placeholder, '::placeholder');
    });
    return results;
  });
}

for (const order of ['before', 'after']) {
  test(`readable text in light/dark/high-contrast themes and switching; branding ${order} upstream CSS`, async () => {
    const page = await browser.newPage();
    try {
      const styles = order === 'before' ? `${theme}<style>${css}</style>` : `<style>${css}</style>${theme}`;
      await page.setContent(`<html><head>${styles}</head><body>${markup}</body></html>`);
      for (const mode of ['light', 'dark', 'high-contrast-light', 'high-contrast-dark', 'light', 'dark']) {
        const appearance = mode.endsWith('dark') ? 'dark' : 'light';
        await page.emulateMedia({ colorScheme: appearance });
        // ThemeProvider's CSS contract: root classes plus RGB palette overrides.
        const palette = mode.startsWith('high-contrast')
          ? highContrast[appearance === 'dark' ? 'highContrastDarkTheme' : 'highContrastLightTheme'] : {};
        await page.evaluate(({ mode, appearance, palette }) => {
          const root = document.documentElement;
          root.className = `${appearance} ${mode.startsWith('high-contrast') ? 'high-contrast' : ''}`;
          root.removeAttribute('style');
          for (const [key, value] of Object.entries(palette)) root.style.setProperty(`--${key.replace(/^rgb-/, '')}`, value);
        }, { mode, appearance, palette });
        await page.evaluate(() => Promise.all(document.getAnimations().map((animation) => animation.finished)));
        const results = await contrast(page);
        assert.ok(results.length > 100, 'The real component fixture must render enough text to exercise inheritance');
        const failures = results.filter(({ ratio }) => ratio < 4.5);
        assert.equal(failures.length, 0, `${mode}: text must meet 4.5:1 contrast\n${JSON.stringify(failures, null, 2)}`);
        assert.equal(await page.locator('[data-fixed-surface]').evaluate((el) => getComputedStyle(el).color), 'rgb(0, 0, 0)');
        assert.notEqual(await page.locator('.hljs-keyword').evaluate((el) => getComputedStyle(el).color),
          await page.locator('[data-portal]').evaluate((el) => getComputedStyle(el).color), 'Syntax colors must remain distinct');
        assert.equal(await page.locator('p.text-status-error').evaluate((el) => {
          const marker = document.createElement('span');
          marker.style.color = 'rgb(var(--status-error))';
          el.appendChild(marker);
          const expected = getComputedStyle(marker).color;
          marker.remove();
          return getComputedStyle(el).color === expected;
        }), true, 'Error text must retain its status role');
        if (process.env.SCIENTIFIC_THEME_ARTIFACTS && order === 'after') {
          await mkdir(process.env.SCIENTIFIC_THEME_ARTIFACTS, { recursive: true });
          await writeFile(join(process.env.SCIENTIFIC_THEME_ARTIFACTS, `${mode}.json`), JSON.stringify(results, null, 2));
          await page.screenshot({ path: join(process.env.SCIENTIFIC_THEME_ARTIFACTS, `${mode}.png`) });
        }
      }
    } finally { await page.close(); }
  });
}

test('regression control: removing the theme reproduces black inherited text and nested prose', async () => {
  const page = await browser.newPage();
  try {
    await page.setContent(`<html class="dark"><head><style>${css}</style></head><body>${markup}</body></html>`);
    const results = await contrast(page);
    for (const label of ['New here? Start with your sample data.', 'Apps', 'Nested tool result', 'Portalled dialog text']) {
      assert.ok(results.some(({ text, ratio }) => text === label && ratio < 2), `Missing regression control: ${label}`);
    }
  } finally { await page.close(); }
});

test('production Vite build retains the complete theme and exact brand assets', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'scientific-theme-build-'));
  try {
    await writeFile(join(dir, 'index.html'), `<html><head><title>Test</title><link rel="stylesheet" href="/style.css"></head><body>${markup}</body></html>`);
    await writeFile(join(dir, 'style.css'), css);
    await brandClient(dir, undefined, true);
    await build({ root: dir, configFile: false, logLevel: 'error' });
    await verifyBranding(join(dir, 'dist'));
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test('chat header masks scrolling text and footer cannot cover content', async () => {
  const source = await upstreamSource();
  const dir = await mkdtemp(join(tmpdir(), 'scientific-chat-surfaces-'));
  const page = await browser.newPage();
  try {
    await mkdir(join(dir, 'src/components/Chat'), { recursive: true });
    await mkdir(join(dir, 'src/components/Auth'), { recursive: true });
    for (const file of ['Chat/Header.tsx', 'Auth/AuthLayout.tsx']) {
      await writeFile(join(dir, 'src/components', file), await readFile(join(source, 'client/src/components', file)));
    }
    const patch = () => execFileSync(process.execPath, [join(client, 'patch-branding.mjs'), dir]);
    patch();
    const header = await readFile(join(dir, 'src/components/Chat/Header.tsx'), 'utf8');
    patch();
    assert.equal(await readFile(join(dir, 'src/components/Chat/Header.tsx'), 'utf8'), header, 'Reapplying the release patch must be safe');
    // Use the patched pinned header layout; its provider-backed controls are
    // represented by ordinary buttons. Render the actual partner footer.
    const headerClass = header.match(/return \(\s*<div className="([^"]+)"/)[1];
    const Footer = component(join(client, 'PoweredByFooter.tsx'), {
      'react-markdown': { __esModule: true, default: ({ children }) => children },
      '~/data-provider': { useGetStartupConfig: () => ({ data: undefined }) },
      '~/hooks': { useLocalize: () => key => key },
    }).default;
    const footer = renderToStaticMarkup(React.createElement(Footer, { startupConfig: { interface: {
      privacyPolicy: { externalUrl: 'https://example.com/privacy' },
      termsOfService: { externalUrl: 'https://example.com/terms' },
    } } })).replace('src="/assets/nebius-logo.svg"', `src="data:image/svg+xml;base64,${(await readFile(join(client, 'assets/nebius-logo.svg'))).toString('base64')}"`);
    const shell = `<div data-shell class="relative flex h-screen w-full flex-col bg-presentation">
      <div data-header class="${headerClass}"><button>Chat model</button><button>Temporary Chat</button></div>
      <div data-scroll class="min-h-0 flex-1 overflow-y-auto pt-16">
        ${Array.from({ length: 30 }, (_, i) => `<p class="p-4">Scientific content ${i}</p>`).join('')}
        <textarea aria-label="Message input" class="w-full bg-transparent p-4">Prepared prompt</textarea>
      </div><div data-footer>${footer}</div></div>`;
    const { css: shellCss } = await fixture(source, shell);
    for (const mode of ['light', 'dark', 'high-contrast-light', 'high-contrast-dark']) {
      for (const width of [390, 768, 1600]) {
        await page.setViewportSize({ width, height: 600 });
        const appearance = mode.endsWith('dark') ? 'dark' : 'light';
        await page.setContent(`<html class="${appearance}"><head><style>${shellCss}</style>${theme}</head><body>${shell}</body></html>`);
        if (mode.startsWith('high-contrast')) await page.evaluate(palette => {
          for (const [key, value] of Object.entries(palette)) document.documentElement.style.setProperty(`--${key.replace(/^rgb-/, '')}`, value);
        }, highContrast[appearance === 'dark' ? 'highContrastDarkTheme' : 'highContrastLightTheme']);
        await page.locator('[data-scroll]').evaluate(el => { el.scrollTop = el.scrollHeight; });
        const layout = await page.evaluate(() => {
          const header = document.querySelector('[data-header]');
          const footer = document.querySelector('[data-testid="powered-by-partners"]');
          const footerSlot = document.querySelector('[data-footer]');
          const input = document.querySelector('textarea');
          const style = getComputedStyle(header);
          return { headerColor: style.backgroundColor, headerImage: style.backgroundImage,
            shellColor: getComputedStyle(document.querySelector('[data-shell]')).backgroundColor,
            reserved: footerSlot.getBoundingClientRect().height,
            inputBottom: input.getBoundingClientRect().bottom,
            footerTop: footer.getBoundingClientRect().top };
        });
        assert.match(layout.headerColor, /^rgb\(/, `${mode}/${width}: header needs an opaque surface`);
        assert.equal(layout.headerColor, layout.shellColor, 'Header must follow the selected theme');
        assert.equal(layout.headerImage, 'none', 'A fading gradient lets content show through');
        if (width >= 640) {
          assert.ok(layout.reserved > 0, 'Footer must reserve layout space');
          assert.ok(layout.inputBottom <= layout.footerTop, 'Footer must not cover the composer');
          await page.getByRole('link', { name: 'com_ui_privacy_policy' }).waitFor();
          await page.getByRole('link', { name: 'com_ui_terms_of_service' }).waitFor();
        } else assert.equal(layout.reserved, 0, 'Keep the existing mobile footer visibility');
        if (process.env.SCIENTIFIC_THEME_ARTIFACTS) await page.screenshot({ path: join(process.env.SCIENTIFIC_THEME_ARTIFACTS, `chat-surfaces-${mode}-${width}.png`) });
      }
    }
  } finally { await page.close(); await rm(dir, { recursive: true, force: true }); }
});
