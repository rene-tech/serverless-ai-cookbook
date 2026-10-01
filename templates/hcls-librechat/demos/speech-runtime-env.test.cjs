const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { loadSpeechRuntimeEnv } = require('./mcp.cjs');
async function fixture(t, value = {}) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'speech-env-'));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));
  const filename = path.join(directory, 'private.json');
  await fs.writeFile(filename, JSON.stringify(value), { mode: 0o600 });
  return { filename, directory };
}
test('absent configuration leaves the original environment unchanged', async t => {
  const f = await fixture(t), env = { ORIGINAL: 'present' };
  assert.deepEqual(loadSpeechRuntimeEnv({ filename: path.join(f.directory, 'missing.json'), env }), { loaded: false });
  assert.deepEqual(env, { ORIGINAL: 'present' });
});
test('approved variables fill only missing values; existing key and identity are untouched', async t => {
  const f = await fixture(t, { SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'platform', SCIENTIFIC_ENGLISH_SPEECH_API_KEY: 'synthetic-private', SCIENTIFIC_MODELS_MCP_URL: 'https://example.invalid/mcp' });
  const env = { SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE: 'dedicated', SCIENTIFIC_MODELS_API_KEY: 'user-key', LIBRECHAT_USER_ID: 'alice' };
  assert.deepEqual(loadSpeechRuntimeEnv({ filename: f.filename, env }), { loaded: true });
  assert.equal(env.SCIENTIFIC_MEDICAL_SPEECH_AUTH_MODE, 'dedicated');
  assert.equal(env.SCIENTIFIC_ENGLISH_SPEECH_API_KEY, 'synthetic-private');
  assert.equal(env.SCIENTIFIC_MODELS_MCP_URL, 'https://example.invalid/mcp');
  assert.equal(env.SCIENTIFIC_MODELS_API_KEY, 'user-key'); assert.equal(env.LIBRECHAT_USER_ID, 'alice');
});
test('unknown keys and identity/platform-key overrides fail atomically without exposing values', async t => {
  for (const forbidden of ['SCIENTIFIC_MODELS_API_KEY', 'LIBRECHAT_USER_ID', 'PATH', 'NODE_OPTIONS']) {
    const f = await fixture(t, { SCIENTIFIC_MEDICAL_SPEECH_MODEL: 'medical', [forbidden]: 'secret-must-not-appear' }), env = {};
    assert.throws(() => loadSpeechRuntimeEnv({ filename: f.filename, env }), error =>
      error.message.includes('Private workshop speech configuration is invalid') && !error.message.includes('secret-must-not-appear'));
    assert.deepEqual(env, {});
  }
});
test('group/world-readable files and symlinks are rejected', async t => {
  const f = await fixture(t);
  await fs.chmod(f.filename, 0o644);
  assert.throws(() => loadSpeechRuntimeEnv({ filename: f.filename, env: {} }), /Private workshop speech configuration is invalid/);
  await fs.chmod(f.filename, 0o600);
  const link = path.join(f.directory, 'link.json'); await fs.symlink(f.filename, link);
  assert.throws(() => loadSpeechRuntimeEnv({ filename: link, env: {} }), /Private workshop speech configuration is invalid/);
  assert.throws(() => loadSpeechRuntimeEnv({ filename: f.directory, env: {} }), /Private workshop speech configuration is invalid/);
});
test('files owned by a different non-root user are rejected', async t => {
  if (process.getuid() !== 0) return t.skip('Ownership fixture requires the root-owned release-test container.');
  const f = await fixture(t); await fs.chown(f.filename, 12345, 12345);
  assert.throws(() => loadSpeechRuntimeEnv({ filename: f.filename, env: {} }), /Private workshop speech configuration is invalid/);
});
test('invalid JSON, non-string values and oversize files fail without printing their content', async t => {
  for (const value of ['{synthetic-secret', '["synthetic-secret"]', '{"SCIENTIFIC_MEDICAL_SPEECH_MODEL":42}', ' '.repeat(65537)]) {
    const f = await fixture(t); await fs.writeFile(f.filename, value);
    assert.throws(() => loadSpeechRuntimeEnv({ filename: f.filename, env: {} }), error =>
      error.message.includes('Private workshop speech configuration is invalid') && !error.message.includes('synthetic-secret'));
  }
});
test('loader runs before service imports, and the fixed path has no environment override', async () => {
  const source = await fs.readFile(path.join(__dirname, 'mcp.cjs'), 'utf8');
  assert(source.indexOf('loadSpeechRuntimeEnv();') < source.indexOf("const service = require('./service.cjs')"));
  assert(source.includes("filename = '/data/hcls-librechat/workshop-speech-env.json'"));
});
