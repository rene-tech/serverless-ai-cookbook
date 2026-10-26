# Scientific AI theme regression tests

Run from this directory with Node 24:

```sh
npm ci
npx playwright install --with-deps chromium
npm test
```

On a workstation with Chrome installed, `PLAYWRIGHT_CHANNEL=chrome npm test`
can replace the browser download. The suite fetches the LibreChat source pinned
in `life-science/bionemo-librechat/Dockerfile.base`, verifies its SHA-256, and
caches it in `.cache/`. Set `SCIENTIFIC_THEME_ARCHIVE` to an already downloaded
archive to run offline; the same checksum verification still applies.

The tests compile the actual upstream stylesheet and render the current
ScientificLanding, ScientificGettingStarted, ScientificExecutionOutput and
upstream OutputRenderer components. Data hooks, routing and library buttons are
stubbed. Additional DOM fixtures cover chat Markdown, nested prose, the composer,
placeholders, portal inheritance, syntax, error text and an intentionally white
surface. This is a CSS/component regression suite, not an authenticated end-to-end
test of LibreChat or its ThemeProvider.

Chromium measures computed foreground/background contrast, including transparent
ancestors, against the [WCAG normal-text minimum of 4.5:1](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
Both stylesheet orders and repeated light/dark/high-contrast changes are tested
after color transitions settle. High-contrast tests use upstream's actual RGB
palettes. A negative control removes the branding stylesheet and must reproduce
the original dark-mode failures. A real Vite production build must retain the
complete theme and exact brand assets. GitHub Actions runs the suite for client
and LibreChat base changes.

Set `SCIENTIFIC_THEME_ARTIFACTS=/absolute/output/path` to save screenshots and
per-element contrast measurements for each mode. Fixtures contain synthetic
data and do not connect to a deployed client or submit inference.

## Why the fix lives in branding

LibreChat assigns dark backgrounds without a document foreground. Unstyled
Scientific AI headings, navigation, execution commands and controls can therefore
inherit browser black. For example, the landing page's first-visit heading was
black on `#212121`, only **1.30:1** contrast. Separately, each `.prose` block
declares hardcoded light colors; nested blocks without `dark:prose-invert` reset
the enclosing dark Markdown palette.

`brand-client.mjs` now supplies an inherited semantic foreground on `body` and
maps both normal and inverted prose variables to LibreChat's active theme.
Explicit component/status/syntax colors remain in control. The branding entry
point already runs in both full and overlay image builds; verification now
checks the rules themselves, not just the style element's ID.

When changing upstream pins, re-run this suite and the full `scientific-client`
image build. These tests do not qualify runtime services, scientific inference,
arbitrary user-authored HTML inside report iframes, or a live deployment.
