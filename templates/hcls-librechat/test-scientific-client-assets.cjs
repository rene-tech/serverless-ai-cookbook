const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { freshClientAssets, refreshAssetTags, installOnRunningApp } = require('./scientific-client-assets.cjs');

const shell = (version) => `<!doctype html><html lang="en-US"><head><base href="/workspace-client/">\n`
  + `<script type="module" crossorigin src="./assets/index.${version}.js"></script>\n`
  + `<link rel="modulepreload" crossorigin href="./assets/hooks.${version}.js">\n`
  + `<link rel="stylesheet" crossorigin href="./assets/index.${version}.css">\n`
  + '<script nonce="request-nonce">window.devtools=true;</script></head><body><div id="root"></div></body></html>';
const old = shell('old');

function fixture(t) {
  const dist = fs.mkdtempSync(path.join(os.tmpdir(), 'scientific-client-assets-'));
  t.after(() => fs.rmSync(dist, { recursive: true, force: true }));
  fs.mkdirSync(path.join(dist, 'assets'));
  function release(version) {
    for (const name of [`index.${version}.js`, `hooks.${version}.js`, `index.${version}.css`]) {
      fs.writeFileSync(path.join(dist, 'assets', name), 'fixture');
    }
    fs.writeFileSync(path.join(dist, 'index.html'), shell(version));
  }
  release('one');
  return { dist, release };
}

function request(handler, body = old, method = 'GET', route = '/c/saved') {
  const headers = { 'Content-Type': 'text/html; charset=utf-8' };
  const res = { getHeader: (key) => headers[key], setHeader: (key, value) => { headers[key] = value; },
    send(value) { this.body = value; return this; } };
  let next = 0;
  handler({ method, path: route }, res, () => { next++; });
  assert.equal(next, 1);
  res.send(body);
  return { body: res.body, headers };
}

test('a cached SPA shell loads current immutable assets while preserving language, base, nonce and bootstrap', () => {
  const served = old.replace('en-US', 'de-DE').replace('type="module"', 'type="module" nonce="fresh-nonce"');
  const result = refreshAssetTags(served, shell('new'));
  assert.match(result, /index\.new\.js/);
  assert.match(result, /hooks\.new\.js/);
  assert.match(result, /index\.new\.css/);
  assert.doesNotMatch(result, /\.old\./);
  assert.match(result, /lang="de-DE"/);
  assert.match(result, /base href="\/workspace-client\/"/);
  assert.match(result, /script nonce="fresh-nonce" type="module"/);
  assert.match(result, /nonce="request-nonce">window.devtools=true/);
  assert.equal((result.match(/type="module"/g) || []).length, 1);
});

test('ordinary reload sees a later complete release without process restart or stale bridge', (t) => {
  const { dist, release } = fixture(t), handler = freshClientAssets(dist);
  const first = request(handler);
  assert.match(first.body, /index\.one\.js/);
  release('two');
  const second = request(handler);
  assert.match(second.body, /index\.two\.js/);
  assert.notEqual(first.headers['X-Scientific-Client-Revision'], second.headers['X-Scientific-Client-Revision']);
  assert.equal(second.headers['Cache-Control'], 'no-cache, no-store, must-revalidate');
  assert.match(request(handler, old, 'HEAD').body, /index\.two\.js/);
});

test('JSON, API, POST, static bytes and unrelated HTML remain unchanged', (t) => {
  const handler = freshClientAssets(fixture(t).dist);
  for (const args of [[old, 'GET', '/api/files'], [old, 'POST'], ['<h1>Other page</h1>'], [{ data: 'unchanged' }]]) {
    const result = request(handler, ...args);
    assert.deepEqual(result.body, args[0]);
    assert.equal(result.headers['X-Scientific-Client-Revision'], undefined);
  }
  const bytes = Buffer.from('unchanged');
  assert.equal(request(handler, bytes).body, bytes);
});

test('a partial deployment preserves the last complete asset set, then recovers', (t) => {
  const { dist, release } = fixture(t), handler = freshClientAssets(dist);
  fs.writeFileSync(path.join(dist, 'index.html'), shell('missing'));
  assert.match(request(handler).body, /index\.one\.js/);
  release('three');
  assert.match(request(handler).body, /index\.three\.js/);
});

test('unsupported shells do not become arbitrary script injection', () => {
  for (const other of ['<h1>Other</h1>', old.replace('./assets/index.old.js', 'https://example.org/app.js'),
    old.replace('./assets/index.old.js', './assets/../private.js')]) {
    assert.equal(refreshAssetTags(other, shell('new')), other);
    assert.equal(refreshAssetTags(old, other), old);
  }
});

test('running-app installation preserves route objects and is idempotent', (t) => {
  const { dist } = fixture(t);
  const before = [{ name: 'cookies' }, { route: { path: '/index.html' } }, { name: 'api' }, { name: 'errors' }];
  const stack = [...before];
  const app = { router: { stack }, use(handle) { stack.push({ handle }); } };
  assert.deepEqual(installOnRunningApp(app, dist), { installed: true });
  assert.equal(stack[1].handle.name, 'scientificFreshClientAssets');
  assert.deepEqual(stack.filter((layer) => before.includes(layer)), before);
  assert.deepEqual(installOnRunningApp(app, dist), { installed: false });
});

test('actual Express retained-shell requests change release without touching cached asset bytes',
  { skip: !process.env.SCIENTIFIC_EXPRESS_MODULE }, async (t) => {
    const express = require(process.env.SCIENTIFIC_EXPRESS_MODULE);
    const { dist, release } = fixture(t), app = express();
    fs.writeFileSync(path.join(dist, 'assets/index.old.js'), 'immutable-old-client');
    const sendCached = (_req, res) => res.type('html').send(old);
    app.get('/index.html', sendCached);
    app.use(express.static(dist));
    app.get('/api/example', (_req, res) => res.json({ unchanged: true }));
    app.use(sendCached);
    const server = app.listen(0, '127.0.0.1');
    await new Promise((resolve) => server.once('listening', resolve));
    t.after(() => new Promise((resolve) => server.close(resolve)));
    const base = `http://127.0.0.1:${server.address().port}`;
    assert.match(await (await fetch(base + '/c/saved')).text(), /index\.old\.js/);
    installOnRunningApp(app, dist);
    for (const version of ['one', 'two']) {
      release(version);
      for (const route of ['/c/saved', '/login', '/index.html']) {
        const response = await fetch(base + route);
        assert.equal(response.status, 200);
        assert.match(await response.text(), new RegExp(`index\\.${version}\\.js`));
        assert.equal(response.headers.get('cache-control'), 'no-cache, no-store, must-revalidate');
      }
    }
    assert.equal(await (await fetch(base + '/assets/index.old.js')).text(), 'immutable-old-client');
    assert.deepEqual(await (await fetch(base + '/api/example')).json(), { unchanged: true });
  });
