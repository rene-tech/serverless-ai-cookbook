/* Keep no-restart UI releases visible without mutating a cacheable hashed bundle.
 * Only operator-built asset tags change. The existing shell still owns language,
 * base URL, authentication, CSP/nonces and injected deployment/devtools content.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const TAGS = /<script\b[^>]*>[\s\S]*?<\/script\s*>|<link\b[^>]*>/giu;
const attr = (tag, name) => tag.match(new RegExp(`\\s${name}=["']([^"']*)["']`, 'iu'))?.[1];
const assetPath = (tag) => {
  const script = /^<script\b/iu.test(tag) && attr(tag, 'type') === 'module';
  const link = /^<link\b/iu.test(tag) && ['stylesheet', 'modulepreload'].includes(attr(tag, 'rel'));
  const value = script ? attr(tag, 'src') : link ? attr(tag, 'href') : null;
  return value && /^(?:\.\/|\/)?assets\/[\w.-]+\.(?:js|css)$/u.test(value) ? value : null;
};
const assetTags = (html) => (html.match(TAGS) || []).filter(assetPath);
const entry = (tags) => tags.filter((tag) => /^<script\b/iu.test(tag));

function refreshAssetTags(served, current) {
  const oldTags = assetTags(served), newTags = assetTags(current);
  if (entry(oldTags).length !== 1 || entry(newTags).length !== 1 || !served.includes('</head>')) return served;
  // The nonce is generated for this request, not copied from the build artifact.
  const nonce = attr(entry(oldTags)[0], 'nonce');
  const replacement = newTags.map((tag) => {
    const withoutNonce = tag.replace(/\snonce=["'][^"']*["']/giu, '');
    return nonce && /^<script\b/iu.test(tag)
      ? withoutNonce.replace('<script', `<script nonce="${nonce}"`)
      : withoutNonce;
  }).join('\n');
  return served.replace(TAGS, (tag) => assetPath(tag) ? '' : tag)
    .replace('</head>', replacement + '\n</head>');
}

function freshClientAssets(dist) {
  const filename = path.join(dist, 'index.html');
  let signature, current, revision;
  function readCurrent() {
    const stat = fs.statSync(filename);
    const next = `${stat.ino}:${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}`;
    if (next !== signature) {
      const html = fs.readFileSync(filename, 'utf8'), tags = assetTags(html);
      if (entry(tags).length !== 1) throw new Error('Unsupported client asset manifest');
      for (const tag of tags) {
        const relative = assetPath(tag).replace(/^\.?\//u, '');
        if (!fs.statSync(path.join(dist, relative)).isFile()) throw new Error('Client asset not installed');
      }
      current = html;
      revision = crypto.createHash('sha256').update(tags.join('\n')).digest('hex').slice(0, 16);
      signature = next;
    }
    return current;
  }
  // Fail an incomplete deployment before registering its middleware.
  readCurrent();
  return function scientificFreshClientAssets(req, res, next) {
    if (!['GET', 'HEAD'].includes(req.method) || /^\/api(?:\/|$)/u.test(req.path)) return next();
    const send = res.send;
    res.send = function sendFreshClientShell(body) {
      if (typeof body === 'string' && String(res.getHeader('Content-Type') || '').startsWith('text/html')
          && entry(assetTags(body)).length === 1) {
        // Keep the last complete shell if an operator is midway through copying a release.
        try { readCurrent(); } catch { /* No partial asset set is served. */ }
        body = refreshAssetTags(body, current);
        body = body.replace(/<meta\s+name="scientific-client-revision"[^>]*>\s*/giu, '')
          .replace('</head>', `<meta name="scientific-client-revision" content="${revision}"></head>`);
        res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
        res.setHeader('X-Scientific-Client-Revision', revision);
      }
      return send.call(this, body);
    };
    return next();
  };
}

/** Scoped maintenance seam: install before static/index routes, without restarting API/jobs. */
function installOnRunningApp(app, dist) {
  const stack = app.router?.stack || app._router?.stack;
  if (!Array.isArray(stack)) throw new Error('Unsupported Express router');
  if (stack.some((layer) => layer.handle?.name === 'scientificFreshClientAssets')) return { installed: false };
  const index = stack.findIndex((layer) => layer.route?.path === '/index.html');
  if (index < 0) throw new Error('Missing existing index route');
  const handler = freshClientAssets(dist);
  app.use(handler);
  const layer = stack.pop();
  if (layer.handle !== handler) throw new Error('Unexpected concurrent router mutation');
  stack.splice(index, 0, layer);
  return { installed: true };
}

module.exports = { freshClientAssets, refreshAssetTags, installOnRunningApp };
