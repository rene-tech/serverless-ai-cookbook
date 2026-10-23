import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import postcss from 'postcss';
import tailwind from 'tailwindcss';

const here = dirname(fileURLToPath(import.meta.url));
export const client = dirname(here);
const require = createRequire(import.meta.url);

// Test the actual base-image stylesheet, not a hand-maintained imitation of it.
// A pin change in Dockerfile.base automatically changes the fixture source.
export async function upstreamSource() {
  const dockerfile = readFileSync(join(client, '../../life-science/bionemo-librechat/Dockerfile.base'), 'utf8');
  const pin = dockerfile.match(/ADD --checksum=sha256:([a-f0-9]{64})\s+\\\s+(https:\/\/codeload.github.com\/danny-avila\/LibreChat\/tar.gz\/[a-f0-9]{40})/);
  assert.ok(pin, 'Missing checksum-pinned LibreChat base source');
  const [, sha256, url] = pin;
  const cache = join(here, '.cache');
  mkdirSync(cache, { recursive: true });
  const archive = process.env.SCIENTIFIC_THEME_ARCHIVE || join(cache, `${sha256}.tgz`);
  if (!existsSync(archive)) {
    const response = await fetch(url);
    assert.ok(response.ok, `LibreChat download failed: ${response.status}`);
    writeFileSync(archive, Buffer.from(await response.arrayBuffer()));
  }
  assert.equal(createHash('sha256').update(readFileSync(archive)).digest('hex'), sha256,
    'LibreChat source checksum mismatch');
  const source = join(cache, sha256);
  if (!existsSync(join(source, '.extracted'))) {
    mkdirSync(source, { recursive: true });
    execFileSync('tar', ['-xzf', archive, '--strip-components=1', '-C', source]);
    writeFileSync(join(source, '.extracted'), sha256);
  }
  return source;
}

function component(file, mocks) {
  const code = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
  } }).outputText;
  const module = { exports: {} };
  const load = (name) => {
    if (name in mocks) return mocks[name];
    if (name === 'react' || name === 'react/jsx-runtime') return require(name);
    throw new Error(`Add an explicit fixture dependency for ${name} in ${file}`);
  };
  new Function('require', 'module', 'exports', code)(load, module, module.exports);
  return module.exports;
}

export async function fixture(source) {
  const h = React.createElement;
  // Mock only data, navigation and library controls. Render the real Scientific
  // AI TSX and pinned OutputRenderer; never copy their text/color classes here.
  const mocks = {
    '@librechat/client': { Button: ({ variant, size, ...props }) => h('button', props) },
    'react-router-dom': { Link: ({ to, ...props }) => h('a', { href: to, ...props }) },
    '~/Providers': {
      useChatContext: () => ({ conversation: {} }),
      useChatFormContext: () => ({ setValue() {} }),
    },
    '~/data-provider': { useGetStartupConfig: () => ({ data: undefined }) },
    '~/hooks': { useRequiresKey: () => ({ requiresKey: true }), useLocalize: () => (key) => key },
    '~/utils': { cn: (...values) => values.filter(Boolean).join(' ') },
    'copy-to-clipboard': () => {},
    '~/components/Messages/Content/CopyButton': { __esModule: true, default: () => null },
    'lucide-react': Object.fromEntries(['Atom', 'BookOpen', 'Server', 'Dna', 'FlaskConical',
      'ScanLine', 'ArrowUpRight', 'Check'].map((name) => [name, () => h('svg', { 'aria-hidden': true })])),
  };
  const gettingStarted = component(join(client, 'ScientificGettingStarted.tsx'), mocks);
  mocks['../ScientificGettingStarted'] = gettingStarted;
  const Landing = component(join(client, 'ScientificLanding.tsx'), mocks).default;
  const OutputRenderer = component(join(source,
    'client/src/components/Chat/Messages/Content/ToolOutput/OutputRenderer.tsx'), mocks).default;
  mocks['./ToolOutput'] = { OutputRenderer };
  const Execution = component(join(client, 'ScientificExecutionOutput.tsx'), mocks).default;
  const execution = h(Execution, {
    input: JSON.stringify({ command: 'printf "Scientific execution ready"' }),
    output: JSON.stringify({ status: 'failed', job_id: 'local-test', exit_code: 1,
      output: 'Saved measurements: 42', error: 'Example failure message' }),
  });
  const scientific = renderToStaticMarkup(h(React.Fragment, null,
    h(Landing, { centerFormOnLanding: false }), h(gettingStarted.default), execution));

  // Representative DOM contracts from TextPart, the composer, and tool output.
  // Include nested prose without prose-invert: it resets inherited prose vars.
  const markup = `<div id="root" class="bg-presentation p-4">
    ${scientific}
    <section class="bg-surface-secondary p-4" aria-label="Composer">
      <textarea data-testid="text-input" class="bg-transparent placeholder:text-text-tertiary" placeholder="Ask a scientific question">Explain these results</textarea>
    </section>
    <article class="markdown prose message-content dark:prose-invert light text-text-primary">
      <p>Assistant response with <strong>bold evidence</strong> and <a href="#report">a report link</a>.</p>
      <h2>Scientific findings</h2><blockquote>Quoted evidence</blockquote>
      <p>Inline code: <code>result.csv</code></p>
      <table><caption>Measured results</caption><thead><tr><th>Metric</th></tr></thead><tbody><tr><td>0.95</td></tr></tbody></table>
      <div class="prose"><h3>Nested tool result</h3><p>Nested body <strong>and emphasis</strong> <a href="#artifact">artifact</a> <code>data.csv</code></p>
        <pre><code>plain code output</code></pre>
      </div>
    </article>
    <div class="bg-surface-tertiary p-4"><span class="text-text-secondary">Secondary label</span> <span class="text-text-tertiary">Tertiary label</span></div>
    <div class="bg-white text-black p-4" data-fixed-surface>Intentionally white report surface</div>
    <pre class="bg-surface-code"><code class="hljs"><span class="hljs-keyword">return</span> measured_value</code></pre>
  </div><div class="bg-surface-dialog p-4" data-portal>Portalled dialog text</div>`
    .replaceAll('src="/assets/nebius-logo.svg"',
      `src="data:image/svg+xml;base64,${readFileSync(join(client, 'assets/nebius-logo.svg')).toString('base64')}"`);
  const { createTailwindColors } = require(join(source, 'packages/client/src/theme/utils/createTailwindColors.js'));
  const css = await postcss([tailwind({
    content: [{ raw: markup, extension: 'html' }], darkMode: 'class',
    theme: { extend: { colors: createTailwindColors() } },
  })]).process(readFileSync(join(source, 'client/src/style.css'), 'utf8'), { from: undefined });
  const highContrast = component(join(source, 'packages/client/src/theme/themes/highContrast.ts'), {});
  return { markup, css: css.css, highContrast };
}
