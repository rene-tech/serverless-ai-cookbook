const { test } = require('node:test');
const assert = require('node:assert/strict');
const { mergeSeed } = require('./seed-merge.cjs');

test('new agent receives complete defaults', () => {
  assert.deepEqual(mergeSeed(null, null, { model: 'approved', instructions: 'base' }),
    { model: 'approved', instructions: 'base' });
});
test('legacy agent customizations are preserved without guessing a baseline', () => {
  assert.deepEqual(mergeSeed({ model: 'custom', instructions: 'custom' }, null,
    { model: 'approved', instructions: 'base', tools: ['new-tool'] }), { tools: ['new-tool'] });
});
test('unchanged fields update, customer instructions do not', () => {
  assert.deepEqual(mergeSeed({ model: 'old', instructions: 'customer', tools: ['tool'] },
    { model: 'old', instructions: 'base', tools: ['tool'] },
    { model: 'approved', instructions: 'new-base', tools: ['tool', 'new-tool'] }),
    { model: 'approved', tools: ['tool', 'new-tool'] });
});
