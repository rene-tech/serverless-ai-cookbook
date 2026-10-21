import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright';
import { build } from 'vite';
import { brandClient, verifyBranding } from '../brand-client.mjs';
import { fixture, upstreamSource } from './fixture.mjs';

let browser, markup, css, theme, highContrast;
before(async () => {
  ({ markup, css, highContrast } = await fixture(await upstreamSource()));
  const dir = await mkdtemp(join(tmpdir(), 'scientific-theme-'));
  try {
    await writeFile(join(dir, 'index.html'), '<html><head><title>Test</title></head><body></body></html>');
    await brandClient(dir);
    theme = (await readFile(join(dir, 'index.html'), 'utf8')).match(/<style id="nebius-scientific-theme">[\s\S]*?<\/style>/)[0];
  } finally { await rm(dir, { recursive: true, force: true }); }
  browser = await chromium.launch(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {});
});
after(async () => { await browser?.close(); });

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
