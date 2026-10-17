const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { once } = require('node:events');
const { install, rollback, finalize } = require('./scientific-router-maintenance.cjs');
const { installOnRunningApp } = require('./scientific-client-assets.cjs');

const expressPath = process.env.SCIENTIFIC_EXPRESS_MODULE;
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const shell = version => `<!doctype html><html lang="en"><head><script type="module" src="./assets/index.${version}.js"></script>`
  + `<link rel="stylesheet" href="./assets/index.${version}.css"></head><body>Saved session</body></html>`;
const write = (filename, bytes) => { fs.mkdirSync(path.dirname(filename), { recursive: true }); fs.writeFileSync(filename, bytes); };
const selected = filename => ({ path: filename, sha256: hash(fs.readFileSync(filename)) });
const allowed = { Authorization: 'Bearer fixture-only' };

function staging(root, targets, source) {
  const options = { release: 'test-current.1', targets, assets: {} };
  for (const name of ['service', 'router', 'index']) {
    const filename = path.join(root, 'staged', name);
    write(filename, source[name]); options[name] = selected(filename);
  }
  for (const extension of ['js', 'css']) {
    const name = `assets/index.new.${extension}`, filename = path.join(path.dirname(targets.index), name);
    write(filename, `new immutable ${extension}`); options.assets[name] = hash(fs.readFileSync(filename));
  }
  return options;
}

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'scientific-router-maintenance-'));
  const targets = { service: path.join(root, 'service.cjs'), router: path.join(root, 'router.cjs'),
    index: path.join(root, 'dist/index.html') };
  const auth = path.join(root, 'auth.cjs');
  write(auth, `module.exports = function fixtureAuth(req, res, next) {
    if (req.get('Authorization') !== 'Bearer fixture-only') return res.status(401).json({ error: 'unauthenticated' });
    req.user = { id: 'fixture-user' }; next(); };`);
  const service = version => `const inFlight = new Map(); module.exports = {
    version: () => '${version}', workspacePreview: () => Buffer.from('<h1>saved report</h1>'),
    wait: id => new Promise(resolve => inFlight.set(id, resolve)), release: id => inFlight.get(id)?.('${version}'),
    waiting: id => inFlight.has(id) };`;
  const router = preview => `const router = require(${JSON.stringify(expressPath)}).Router();
    const service = require(${JSON.stringify(targets.service)}); router.use(require(${JSON.stringify(auth)}));
    router.get('/version', (_req, res) => res.json({ version: service.version() }));
    router.get('/hold/:id', async (req, res) => res.json({ completed: await service.wait(req.params.id) }));
    ${preview ? "router.get('/workspace/preview', (_req, res) => res.type('text/plain').send(service.workspacePreview()));" : ''}
    module.exports = router;`;
  write(targets.service, service('old')); write(targets.router, router(false)); write(targets.index, shell('old'));
  write(path.join(root, 'dist/assets/index.old.js'), 'old immutable js');
  write(path.join(root, 'dist/assets/index.old.css'), 'old immutable css');
  const options = staging(root, targets, { service: service('new'), router: router(true), index: shell('new') });
  const oldRouter = require(targets.router), oldService = require(targets.service), express = require(expressPath), app = express();
  app.use('/api/scientific-demos', oldRouter);
  app.get('/api/unrelated', (_req, res) => res.json({ unchanged: true }));
  app.get('/index.html', (_req, res) => res.type('html').send(shell('old')));
  app.use(express.static(path.dirname(targets.index)));
  app.get('/c/saved', (_req, res) => res.type('html').send(shell('old')));
  installOnRunningApp(app, path.dirname(targets.index));
  const before = snapshot({ app, targets });
  t.after(() => {
    for (const name of [targets.service, targets.router, auth]) delete require.cache[name];
    fs.rmSync(root, { recursive: true, force: true });
  });
  return { root, app, targets, options, oldRouter, oldService, before };
}

function snapshot({ app, targets }) {
  return { stack: [...app.router.stack], handles: app.router.stack.map(layer => layer.handle),
    files: Object.fromEntries(Object.entries(targets).map(([key, file]) => [key, hash(fs.readFileSync(file))])),
    router: require.cache[targets.router], service: require.cache[targets.service] };
}
function unchanged(value) { assert.deepEqual(snapshot(value), value.before); }
async function listen(t, app) {
  const server = app.listen(0, '127.0.0.1'); await once(server, 'listening');
  t.after(() => new Promise(resolve => { server.close(resolve); server.closeAllConnections(); }));
  return `http://127.0.0.1:${server.address().port}`;
}

test('paired reload preserves in-flight handlers, PID, unrelated routes and old assets; rollback restores all bytes',
  { skip: !expressPath }, async t => {
    const value = fixture(t), { app, options, targets, oldService, oldRouter } = value;
    const base = await listen(t, app), pid = process.pid;
    const pending = fetch(base + '/api/scientific-demos/hold/running-study', { headers: allowed });
    for (let count = 0; !oldService.waiting('running-study') && count < 100; count++) {
      await new Promise(resolve => setTimeout(resolve, 1));
    }
    assert(oldService.waiting('running-study'));
    const receipt = install(app, options);
    assert.equal(receipt.pid, pid); assert.equal(receipt.installed, true);
    assert.notEqual(require.cache[targets.service].exports, oldService);
    assert.equal(oldService.version(), 'old'); assert.equal(oldRouter, value.before.router.exports);
    assert.deepEqual(app.router.stack, value.before.stack, 'mounted layer objects must remain unchanged');
    assert.equal((await fetch(base + '/api/scientific-demos/workspace/preview')).status, 401);
    assert.equal(await (await fetch(base + '/api/scientific-demos/workspace/preview', { headers: allowed })).text(), '<h1>saved report</h1>');
    assert.deepEqual(await (await fetch(base + '/api/scientific-demos/version', { headers: allowed })).json(), { version: 'new' });
    assert.deepEqual(await (await fetch(base + '/api/unrelated')).json(), { unchanged: true });
    assert.match(await (await fetch(base + '/c/saved')).text(), /index\.new\.js/);
    assert.equal(await (await fetch(base + '/assets/index.old.js')).text(), 'old immutable js');
    oldService.release('running-study');
    assert.deepEqual(await (await pending).json(), { completed: 'old' }, 'in-flight request completes through its original service');
    assert.throws(() => install(app, options), /owns its rollback/);
    rollback(app, options.release); unchanged(value);
    assert.match(await (await fetch(base + '/c/saved')).text(), /index\.old\.js/);
    assert.equal((await fetch(base + '/api/scientific-demos/workspace/preview', { headers: allowed })).status, 404);
    install(app, options); assert.equal(finalize(app, options.release).finalized, true);
    assert.throws(() => rollback(app, options.release), /No matching active/);
  });

test('unqualified, incomplete and incompatible candidates leave files, modules and mounted handlers untouched',
  { skip: !expressPath }, async t => {
    const cases = {
      'hash mismatch': value => { value.options.service.sha256 = '0'.repeat(64); },
      'missing asset': value => { fs.unlinkSync(path.join(path.dirname(value.targets.index), 'assets/index.new.js')); },
      'unqualified asset': value => { value.options.assets = {}; },
      'syntax error': value => { write(value.options.router.path, 'syntax error'); value.options.router = selected(value.options.router.path); },
      'drops current route': value => {
        const file = value.options.router.path;
        write(file, fs.readFileSync(file, 'utf8').replace("router.get('/version'", "router.get('/different'")); value.options.router = selected(file);
      },
      'missing preview': value => { write(value.options.router.path, fs.readFileSync(value.targets.router)); value.options.router = selected(value.options.router.path); },
      'changed authentication': value => {
        const file = value.options.router.path;
        write(file, fs.readFileSync(file, 'utf8').replace(/router\.use\(require\([^\n]+\);/, 'router.use((_req, _res, next) => next());'));
        value.options.router = selected(file);
      },
      'drops service export': value => {
        const file = value.options.service.path;
        write(file, fs.readFileSync(file, 'utf8').replace('waiting: id => inFlight.has(id)', 'unrelated: id => inFlight.has(id)'));
        value.options.service = selected(file);
      },
    };
    for (const [label, mutate] of Object.entries(cases)) await t.test(label, sub => {
      const value = fixture(sub); mutate(value); assert.throws(() => install(value.app, value.options)); unchanged(value);
    });
  });

test('a filesystem failure after source publication rolls back before returning control', { skip: !expressPath }, t => {
  const value = fixture(t), original = fs.renameSync;
  let injected = false;
  fs.renameSync = function(source, target) {
    if (target === value.targets.index && !injected) { injected = true; throw new Error('injected index rename failure'); }
    return original.call(this, source, target);
  };
  try { assert.throws(() => install(value.app, value.options), /injected index rename/); }
  finally { fs.renameSync = original; }
  unchanged(value);
  install(value.app, value.options); rollback(value.app, value.options.release); unchanged(value);
});

test('rollback refuses an intervening update instead of clobbering another maintainer', { skip: !expressPath }, t => {
  const value = fixture(t); install(value.app, value.options);
  const original = fs.readFileSync(value.targets.service);
  fs.appendFileSync(value.targets.service, '\n// another writer\n');
  assert.throws(() => rollback(value.app, value.options.release), /Another release changed service/);
  assert.match(fs.readFileSync(value.targets.service, 'utf8'), /another writer/);
  fs.writeFileSync(value.targets.service, original); rollback(value.app, value.options.release); unchanged(value);
});

test('actual pinned image modules install the bounded authenticated preview into an explicitly stale cached router',
  { skip: process.env.SCIENTIFIC_TEST_IMAGE_CONTRACT !== 'true' }, async t => {
    // This test runs ONLY in a disposable, network-disabled image container.
    // Its stale router deliberately omits preview to reproduce the retained
    // API process, whose loaded code predates its on-disk source. Auth/plugin
    // test stubs replace external MongoDB; no production login is simulated.
    assert.equal(require('/app/node_modules/express/package.json').version, '5.2.1');
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'scientific-real-router-'));
    const targets = { router: '/app/api/server/routes/scientific-demos.js',
      service: '/opt/hcls-librechat/demos/service.cjs', index: path.join(root, 'dist/index.html') };
    const savedRouter = fs.readFileSync(targets.router), savedService = fs.readFileSync(targets.service);
    const envWorkspace = process.env.SCIENTIFIC_WORKSPACE;
    process.env.SCIENTIFIC_WORKSPACE = path.join(root, 'workspace'); fs.mkdirSync(process.env.SCIENTIFIC_WORKSPACE);
    const modules = require('/app/node_modules/module-alias'); modules.addAlias('~', '/app/api');
    const middleware = require.resolve('/app/api/server/middleware');
    const plugin = require.resolve('/app/api/server/services/PluginService');
    const savedCaches = new Map([middleware, plugin, targets.router, targets.service].map(name => [name, require.cache[name]]));
    const requireJwtAuth = (req, res, next) => {
      if (req.get('Authorization') !== allowed.Authorization) return res.status(401).json({ error: 'unauthenticated' });
      req.user = { id: 'local-image-fixture' }; next();
    };
    require.cache[middleware] = { id: middleware, filename: middleware, loaded: true, exports: { requireJwtAuth } };
    require.cache[plugin] = { id: plugin, filename: plugin, loaded: true,
      exports: { getUserPluginAuthValue: async () => 'fixture-only', updateUserPluginAuth: async () => true } };
    delete require.cache[targets.router]; delete require.cache[targets.service];
    const stale = savedRouter.toString().replace(/router\.get\('\/workspace\/preview',[\s\S]*?\n\}\)\);\n/u, '');
    assert(!stale.includes("router.get('/workspace/preview'"));
    write(targets.router, stale); write(targets.index, shell('old'));
    write(path.join(root, 'dist/assets/index.old.js'), 'old immutable js');
    write(path.join(root, 'dist/assets/index.old.css'), 'old immutable css');
    t.after(() => {
      fs.writeFileSync(targets.router, savedRouter); fs.writeFileSync(targets.service, savedService);
      for (const [name, value] of savedCaches) { if (value) require.cache[name] = value; else delete require.cache[name]; }
      if (envWorkspace === undefined) delete process.env.SCIENTIFIC_WORKSPACE; else process.env.SCIENTIFIC_WORKSPACE = envWorkspace;
      fs.rmSync(root, { recursive: true, force: true });
    });
    const options = staging(root, targets, { service: fs.readFileSync(path.join(__dirname, 'demos/service.cjs')),
      router: fs.readFileSync(path.join(__dirname, 'demos/router.cjs')), index: shell('new') });
    const app = require(expressPath)(); app.use('/api/scientific-demos', require(targets.router));
    app.get('/index.html', (_req, res) => res.type('html').send(shell('old')));
    installOnRunningApp(app, path.dirname(targets.index));
    const base = await listen(t, app), endpoint = '/api/scientific-demos/workspace/preview?path=';
    assert.equal((await fetch(base + endpoint + 'report.html', { headers: allowed })).status, 404);
    write(path.join(root, 'workspace/report.html'), '<html><h1>Saved precheck</h1></html>');
    const before = snapshot({ app, targets });
    const receipt = install(app, options); assert(receipt.routes.includes('GET /workspace/preview'));
    assert.equal((await fetch(base + endpoint + 'report.html')).status, 401);
    const report = await fetch(base + endpoint + 'report.html', { headers: allowed });
    assert.equal(report.status, 200); assert.match(report.headers.get('content-type'), /^text\/plain/);
    assert.equal(report.headers.get('x-content-type-options'), 'nosniff');
    assert.equal(report.headers.get('cache-control'), 'no-store');
    assert.equal(await report.text(), '<html><h1>Saved precheck</h1></html>');
    assert.equal((await fetch(base + endpoint + 'missing.html', { headers: allowed })).status, 404);
    assert.equal((await fetch(base + endpoint + encodeURIComponent('../escape'), { headers: allowed })).status, 400);
    write(path.join(root, 'workspace/large.html'), Buffer.alloc(8 * 1024 * 1024 + 1));
    assert.equal((await fetch(base + endpoint + 'large.html', { headers: allowed })).status, 413);
    const download = await fetch(base + '/api/scientific-demos/workspace/file?path=large.html', { headers: allowed });
    assert.equal(download.status, 200); assert.equal((await download.arrayBuffer()).byteLength, 8 * 1024 * 1024 + 1);
    const settings = await fetch(base + '/api/scientific-demos/settings', { headers: allowed });
    assert.equal(settings.status, 200); assert.equal((await settings.json()).configured, true);
    rollback(app, options.release); assert.deepEqual(snapshot({ app, targets }), before);
  });
