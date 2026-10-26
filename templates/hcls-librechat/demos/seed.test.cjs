const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { mergeSeed } = require('../seed-merge.cjs');

const source = fs.readFileSync(process.env.DEMO_SEED_TEST_SOURCE || path.join(__dirname, 'seed.cjs'), 'utf8');
const clone = (value) => JSON.parse(JSON.stringify(value));
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const ids = ['agent_clinical_report', 'agent_mindeval_workshop'];

async function seed(agents = [], grants = []) {
  let serial = 0;
  class ObjectId {
    constructor() { this.value = `synthetic-${++serial}`; }
    toJSON() { return this.value; }
  }
  const rows = { users: [{ _id: 'owner', email: 'nebius-scientific-ai-agent@localhost.invalid' }],
    agents: clone(agents), aclentries: clone(grants) };
  let aclWrites = 0, closed = false;
  const db = { collection(name) { return {
    async findOne(query) {
      const found = rows[name].find((row) => Object.entries(query).every(([key, value]) => equal(row[key], clone(value))));
      return found ? clone(found) : null;
    },
    async updateOne(query, update) {
      if (name === 'aclentries') aclWrites++;
      let row = rows[name].find((entry) => Object.entries(query).every(([key, value]) => equal(entry[key], clone(value))));
      let upsertedId = null;
      if (!row) {
        row = { ...clone(query), ...clone(update.$setOnInsert || {}) };
        rows[name].push(row);
        upsertedId = row._id;
      }
      Object.assign(row, clone(update.$set || {}));
      return { upsertedId, matchedCount: upsertedId ? 0 : 1 };
    },
  }; } };
  class MongoClient {
    async connect() {}
    db() { return db; }
    async close() { closed = true; }
  }
  const fakeProcess = { env: { SCIENTIFIC_CHAT_MODEL: 'synthetic/default' }, exitCode: undefined };
  const requireForSeed = (name) => {
    if (name === 'node:module') return { createRequire: () => () => ({ MongoClient, ObjectId }) };
    if (name === '/app/seed-merge.cjs') return { mergeSeed };
    if (name === './mcp.cjs') return { tools: [{ name: 'clinical_submit' }, { name: 'workshop_catalog' }] };
    throw new Error(`Unexpected seed dependency: ${name}`);
  };
  // Same realm as the in-memory driver and mergeSeed: cross-realm array
  // prototypes must not manufacture customization differences in this test.
  const execute = vm.compileFunction('return eval(source)', ['source', 'require', 'console', 'process']);
  await execute(source, requireForSeed, { log() {}, error() {} }, fakeProcess);
  assert.equal(fakeProcess.exitCode, undefined);
  assert.equal(closed, true);
  return { ...rows, aclWrites };
}

const existing = () => ids.map((id, index) => ({ id, _id: `existing-${index}`,
  model: 'customer/model', model_parameters: { model: 'customer/model', maxContextTokens: 777777 },
  instructions: 'Customer instructions', tools: ['customer-tool'], customer_metadata: { retain: true },
  _scientificSeed: { model: 'old/default', instructions: 'Old managed instructions', tools: ['old-tool'] },
}));

test('existing demo customization and existing public ACL remain exact', async () => {
  const agents = existing();
  const grants = agents.map((agent) => ({ _id: `grant-${agent._id}`, principalType: 'public',
    resourceType: 'agent', resourceId: agent._id, permBits: 3, grantedBy: 'customer',
    grantedAt: 'retained-time', customer_metadata: { retain: true } }));
  const after = await seed(agents, grants);
  for (const before of agents) {
    const actual = after.agents.find((agent) => agent.id === before.id);
    for (const key of ['model', 'model_parameters', 'instructions', 'tools', 'customer_metadata'])
      assert.deepEqual(actual[key], before[key]);
  }
  assert.deepEqual(after.aclentries, grants);
  assert.equal(after.aclWrites, 0);
});

test('existing demo with revoked public access does not recreate an ACL', async () => {
  const after = await seed(existing(), []);
  assert.deepEqual(after.aclentries, []);
  assert.equal(after.aclWrites, 0);
});

test('new demo receives defaults and its initial public ACL once', async () => {
  const first = await seed();
  assert.equal(first.agents.length, 2);
  assert.equal(first.aclWrites, 2);
  for (const agent of first.agents) {
    assert.equal(agent.model, 'synthetic/default');
    assert.deepEqual(agent.model_parameters, { model: 'synthetic/default', max_tokens: 8192 });
    const grants = first.aclentries.filter((grant) => grant.resourceId === agent._id);
    assert.equal(grants.length, 1);
    assert.equal(grants[0].permBits, 1);
    assert.equal(grants[0].grantedBy, 'owner');
  }
  const second = await seed(first.agents, first.aclentries);
  assert.deepEqual(second.aclentries, first.aclentries);
  assert.equal(second.aclWrites, 0);
});
