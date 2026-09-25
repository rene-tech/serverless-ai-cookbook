const test = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const service = path.resolve(__dirname, '../demos/service.cjs');
function config(environment) {
  return JSON.parse(execFileSync(process.execPath, ['-e', `const s=require(${JSON.stringify(service)}); console.log(JSON.stringify({model:s.REPORT_MODEL, label:s.REPORT_PROVIDER_LABEL, credential:s.reportCredential()}))`], { env: { PATH: process.env.PATH, ...environment }, encoding: 'utf8' }));
}
test('default reporting retains Token Factory independent of chat model', () => {
  assert.deepEqual(config({ NEBIUS_API_KEY: 'tf-mock' }), { model: 'Qwen/Qwen3-235B-A22B-Instruct-2507', label: 'Nebius Token Factory', credential: 'tf-mock' });
});
test('dedicated Fastino endpoint never inherits Token Factory secret', () => {
  assert.equal(config({ CLINICAL_REPORT_BASE_URL: 'https://medical.test/v1', NEBIUS_API_KEY: 'tf-mock' }).credential, '');
  assert.deepEqual(config({ CLINICAL_REPORT_BASE_URL: 'https://medical.test/v1', CLINICAL_REPORT_MODEL: 'fastino/healthcare', CLINICAL_REPORT_PROVIDER_LABEL: 'Fastino on Nebius', CLINICAL_REPORT_API_KEY: 'fastino-mock', NEBIUS_API_KEY: 'tf-mock' }), { model: 'fastino/healthcare', label: 'Fastino on Nebius', credential: 'fastino-mock' });
});
