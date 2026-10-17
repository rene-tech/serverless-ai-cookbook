/* Operator-only, synchronous maintenance for the pinned Express workbench.
 * Not an HTTP endpoint or request/version adapter. Load through the existing
 * loopback maintenance inspector after staging a hash-qualified release.
 */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');

const active = new WeakMap();
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const paths = {
  router: '/app/api/server/routes/scientific-demos.js',
  service: '/opt/hcls-librechat/demos/service.cjs',
  index: '/app/client/dist/index.html',
};

function bytesAt(filename) {
  assert(fs.lstatSync(filename).isFile(), 'Expected a regular release file');
  return fs.readFileSync(filename);
}

function writeAtomic(filename, bytes, mode) {
  const temporary = path.join(path.dirname(filename), '.scientific-router-' + crypto.randomUUID());
  try {
    fs.writeFileSync(temporary, bytes, { flag: 'wx', mode });
    fs.renameSync(temporary, filename);
  } finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); }
}

function routes(router) {
  assert(Array.isArray(router?.stack), 'Expected the pinned Express router');
  return router.stack.filter(layer => layer.route).flatMap(layer =>
    Object.keys(layer.route.methods).map(method => method.toUpperCase() + ' ' + layer.route.path));
}

function compile(source, filename) {
  // The canonical filename preserves __dirname and the installed module aliases.
  // No old exports are mutated: in-flight requests keep their captured objects.
  const candidate = new Module(filename);
  candidate.filename = filename;
  candidate.paths = Module._nodeModulePaths(path.dirname(filename));
  require.cache[filename] = candidate;
  candidate._compile(source.toString('utf8'), filename);
  candidate.loaded = true;
  return candidate;
}

function restoreCaches(snapshot) {
  for (const [filename, value] of Object.entries(snapshot)) {
    if (value) require.cache[filename] = value;
    else delete require.cache[filename];
  }
}

function prepare(app, options) {
  assert(/^[a-z0-9][a-z0-9.-]{0,95}$/.test(options.release), 'Supply an exact release identifier');
  const target = options.targets || paths;
  assert.deepEqual(Object.keys(target).sort(), ['index', 'router', 'service']);
  const stack = app.router?.stack;
  assert(Array.isArray(stack), 'Expected the pinned Express application');
  assert.equal(stack.filter(layer => layer.handle?.name === 'scientificFreshClientAssets').length, 1,
    'Current asset middleware must already be installed');
  const previous = { [target.router]: require.cache[target.router], [target.service]: require.cache[target.service] };
  assert(previous[target.router]?.loaded && previous[target.service]?.loaded, 'Expected loaded current modules');
  const oldRouter = previous[target.router].exports;
  const matches = stack.filter(layer => layer.handle === oldRouter);
  assert.equal(matches.length, 1, 'Expected exactly one mounted scientific router');
  const layer = matches[0];
  const original = {}, incoming = {};
  for (const name of ['service', 'router', 'index']) {
    const selected = options[name];
    assert(/^[a-f0-9]{64}$/.test(selected?.sha256), 'Supply the qualified file digest');
    incoming[name] = bytesAt(selected.path);
    assert.equal(hash(incoming[name]), selected.sha256, 'Staged file differs from qualified release: ' + name);
    const stat = fs.statSync(target[name]);
    original[name] = { bytes: bytesAt(target[name]), mode: stat.mode & 0o777 };
    fs.accessSync(path.dirname(target[name]), fs.constants.W_OK);
  }
  const dist = path.dirname(target.index), html = incoming.index.toString('utf8');
  const entries = [...html.matchAll(/<script\b[^>]*type=["']module["'][^>]*src=["']([^"']+)["'][^>]*>/giu)];
  assert.equal(entries.length, 1, 'Expected one current client entry');
  const references = [...html.matchAll(/(?:src|href)=["']((?:\.\/|\/)assets\/[\w.-]+\.(?:js|css))["']/gu)]
    .map(match => match[1].replace(/^\.?\//u, ''));
  assert(references.length && references.includes(entries[0][1].replace(/^\.?\//u, '')), 'Invalid client asset references');
  assert(options.assets && Object.keys(options.assets).length, 'Supply the qualified installed asset manifest');
  for (const [name, digest] of Object.entries(options.assets)) {
    assert(/^assets\/[\w.-]+$/.test(name), 'Unsupported asset path');
    assert(/^[a-f0-9]{64}$/.test(digest), 'Supply the qualified asset digest');
    assert.equal(hash(bytesAt(path.join(dist, name))), digest, 'Installed asset differs: ' + name);
  }
  assert(references.every(name => options.assets[name]), 'Client shell references an unqualified asset');
  let service, router;
  try {
    service = compile(incoming.service, target.service);
    router = compile(incoming.router, target.router);
    assert.equal(typeof router.exports, 'function', 'Candidate router is not callable');
    const wanted = new Set(routes(router.exports));
    const retired = new Set(options.retiredRoutes || []);
    assert([...retired].every(route => ['GET /studies/:id', 'POST /studies/:id/cancel'].includes(route)),
      'Unapproved route retirement');
    assert([...retired].every(route => routes(oldRouter).includes(route) && !wanted.has(route)),
      'Retired route does not match the exact installed transition');
    assert(routes(oldRouter).every(route => wanted.has(route) || retired.has(route)), 'Candidate drops a current route');
    assert(wanted.has('GET /workspace/preview'), 'Candidate lacks the bounded preview route');
    assert.equal(router.exports.stack[0]?.handle, oldRouter.stack[0]?.handle,
      'Authentication middleware changed');
    for (const [name, value] of Object.entries(previous[target.service].exports)) {
      assert.equal(typeof service.exports[name], typeof value, 'Candidate drops a current service export: ' + name);
    }
    assert.equal(typeof service.exports.workspacePreview, 'function', 'Candidate lacks preview service');
  } finally { restoreCaches(previous); }
  return { release: options.release, app, stack, layer, target, previous, original, incoming, service, router };
}

function verifyCurrent(transaction, installed) {
  const { app, stack, layer, previous, target, router, service } = transaction;
  assert.equal(app.router?.stack, stack, 'Application router changed');
  assert.equal(stack.filter(item => item === layer).length, 1, 'Mounted route changed');
  assert.equal(layer.handle, installed ? router.exports : previous[target.router].exports, 'Another router update intervened');
  assert.equal(require.cache[target.router], installed ? router : previous[target.router], 'Router cache changed');
  assert.equal(require.cache[target.service], installed ? service : previous[target.service], 'Service cache changed');
  for (const name of ['service', 'router', 'index']) {
    assert.equal(hash(bytesAt(target[name])), hash(installed ? transaction.incoming[name] : transaction.original[name].bytes),
      'Another release changed ' + name);
  }
}

function install(app, options) {
  assert(!active.has(app), 'Previous maintenance still owns its rollback; finalize or roll it back first');
  const transaction = prepare(app, options);
  verifyCurrent(transaction, false);
  const changed = [];
  try {
    // One synchronous event-loop turn. Publish the HTML last: it never points
    // at a new UI while this process is still using the previous API router.
    for (const name of ['service', 'router']) {
      writeAtomic(transaction.target[name], transaction.incoming[name], transaction.original[name].mode);
      changed.push(name);
    }
    require.cache[transaction.target.service] = transaction.service;
    require.cache[transaction.target.router] = transaction.router;
    transaction.layer.handle = transaction.router.exports;
    writeAtomic(transaction.target.index, transaction.incoming.index, transaction.original.index.mode);
    changed.push('index');
    verifyCurrent(transaction, true);
  } catch (error) {
    transaction.layer.handle = transaction.previous[transaction.target.router].exports;
    restoreCaches(transaction.previous);
    for (const name of changed.reverse()) {
      writeAtomic(transaction.target[name], transaction.original[name].bytes, transaction.original[name].mode);
    }
    throw error;
  }
  active.set(app, transaction);
  return { release: transaction.release, pid: process.pid, installed: true,
    routes: routes(transaction.router.exports),
    before: Object.fromEntries(Object.entries(transaction.original).map(([name, value]) => [name, hash(value.bytes)])),
    after: Object.fromEntries(Object.entries(transaction.incoming).map(([name, value]) => [name, hash(value)])) };
}

function rollback(app, release) {
  const transaction = active.get(app);
  assert(transaction && transaction.release === release, 'No matching active maintenance');
  verifyCurrent(transaction, true);
  // Stop publishing the new UI before restoring its API counterpart.
  for (const name of ['index', 'service', 'router']) {
    writeAtomic(transaction.target[name], transaction.original[name].bytes, transaction.original[name].mode);
  }
  transaction.layer.handle = transaction.previous[transaction.target.router].exports;
  restoreCaches(transaction.previous);
  active.delete(app);
  return { release, pid: process.pid, rolled_back: true };
}

function finalize(app, release) {
  const transaction = active.get(app);
  assert(transaction && transaction.release === release, 'No matching active maintenance');
  verifyCurrent(transaction, true);
  active.delete(app);
  return { release, pid: process.pid, finalized: true };
}

module.exports = { install, rollback, finalize };
