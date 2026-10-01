const assert = require('node:assert/strict');
const options = require('./scientific-title-options.cjs');
const source = { model: 'zai-org/GLM-5.3-Flash', configuration: { baseURL: 'https://example.invalid' },
  modelKwargs: { preserved: true } };
const result = options(source, 'Nebius Token Factory');
assert.equal(result.modelKwargs.reasoning_effort, 'low');
assert.equal(result.modelKwargs.preserved, true);
assert.equal(source.modelKwargs.reasoning_effort, undefined);
assert.strictEqual(result.configuration, source.configuration);
assert.strictEqual(options(source, 'other-provider'), source);
const other = { model: 'different-model' };
assert.strictEqual(options(other, 'Nebius Token Factory'), other);
console.log('Title reasoning is bounded only for the approved Nebius GLM title model');
