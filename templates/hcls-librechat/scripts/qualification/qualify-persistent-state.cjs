/* Run inside an ISOLATED system QA workbench, never a customer instance.
 * Seed representative customer state, then compare after stop/replacement.
 * Prints counts/checks only, never logins, tokens or encryption keys.
 */
'use strict';
const { MongoClient, ObjectId } = require('mongodb');
const bcrypt = require('bcryptjs');
const fs = require('node:fs/promises');
const qaCrypto = require('node:crypto');

const testPrefix = 'qa-state-20261002';
const mode = process.env.STATE_QUALIFICATION_MODE || 'verify';
const sha = value => qaCrypto.createHash('sha256').update(value).digest('hex');

async function main() {
  if (process.env.SCIENTIFIC_STUDY_OWNER !== 'system-state-qualification-20261002') {
    throw new Error('This test is restricted to its isolated QA study owner');
  }
  const secrets = await fs.readFile('/data/hcls-librechat/runtime-secrets.env', 'utf8');
  for (const line of secrets.trim().split('\n')) {
    const split = line.indexOf('='); process.env[line.slice(0, split)] = line.slice(split + 1);
  }
  const { encrypt, decrypt } = require('@librechat/api');
  const client = new MongoClient(process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat');
  await client.connect();
  try {
    const db = client.db();
    const owner = await db.collection('users').findOne({ email: process.env.SEED_DEFAULT_USER_EMAIL });
    if (!owner) throw new Error('Seeded owner missing');
    const userId = String(owner._id);
    const conversations = [`${testPrefix}-chat-one`, `${testPrefix}-chat-two`];
    const path = '/data/hcls-librechat/state-qualification.json';
    if (mode === 'seed') {
      try { await fs.access(path); throw new Error('Complete fixture already exists; use verify'); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
      const secondPassword = qaCrypto.randomBytes(24).toString('hex');
      await db.collection('users').updateOne({ email: 'state-second@example.invalid' }, { $set: { email: 'state-second@example.invalid', name: 'Second QA Login',
        username: 'state-second', password: await bcrypt.hash(secondPassword, 10), provider: 'local', role: 'USER',
        emailVerified: true, createdAt: new Date(), updatedAt: new Date() } }, { upsert: true });
      for (const [index, conversationId] of conversations.entries()) {
        await db.collection('conversations').updateOne({ conversationId }, { $setOnInsert: { conversationId, user: userId, title: `State preservation ${index + 1}`,
          endpoint: 'agents', model: 'moonshotai/Kimi-K3', agent_id: 'agent_nebius_scientific_ai',
          createdAt: new Date(), updatedAt: new Date() } }, { upsert: true });
        await db.collection('messages').updateOne({ conversationId }, { $setOnInsert: { messageId: qaCrypto.randomUUID(), conversationId, user: userId,
          sender: 'User', isCreatedByUser: true, text: `Preserve my research notes ${index + 1}`,
          content: [{ type: 'text', text: `Preserve my research notes ${index + 1}` }], createdAt: new Date() } }, { upsert: true });
      }
      await db.collection('agents').updateOne({ id: 'agent_nebius_scientific_ai' }, { $set: {
        instructions: 'Customer customized scientific instructions: preserve this exactly.',
      } });
      await db.collection('presets').updateOne({ presetId: testPrefix }, { $setOnInsert: { presetId: testPrefix, user: userId, title: 'Customer settings',
        model: 'moonshotai/Kimi-K3', temperature: 0.42 } }, { upsert: true });
      await db.collection('pluginauths').insertOne({ userId, pluginKey: testPrefix,
        authField: 'fixture', value: await encrypt('qa-fixture-not-a-real-key') });
      await fs.writeFile(`/app/uploads/${testPrefix}.txt`, 'Customer attachment retained across upgrades\n');
      await fs.mkdir(`/workspace/${testPrefix}`, { recursive: true });
      await fs.writeFile(`/workspace/${testPrefix}/result.txt`, 'Workspace result remains in the same bucket\n');
      await fs.writeFile(path, JSON.stringify({ ownerHash: sha(owner.password), ownerId: userId,
        secretHash: sha(secrets), secondPassword, conversations }), { mode: 0o600 });
    }
    const evidence = JSON.parse(await fs.readFile(path, 'utf8'));
    const second = await db.collection('users').findOne({ email: 'state-second@example.invalid' });
    const plugin = await db.collection('pluginauths').findOne({ userId, pluginKey: testPrefix });
    const primary = await db.collection('agents').findOne({ id: 'agent_nebius_scientific_ai' });
    const checks = {
      owner_identity: userId === evidence.ownerId, owner_password: sha(owner.password) === evidence.ownerHash,
      encryption_keys: sha(secrets) === evidence.secretHash,
      second_login_hash: await bcrypt.compare(evidence.secondPassword, second.password),
      conversations: await db.collection('conversations').countDocuments({ conversationId: { $in: evidence.conversations } }) === 2,
      messages: await db.collection('messages').countDocuments({ conversationId: { $in: evidence.conversations } }) === 2,
      customer_instructions: primary.instructions === 'Customer customized scientific instructions: preserve this exactly.',
      settings: Boolean(await db.collection('presets').findOne({ presetId: testPrefix, temperature: 0.42 })),
      encrypted_plugin: await decrypt(plugin.value) === 'qa-fixture-not-a-real-key',
      attachment: (await fs.readFile(`/app/uploads/${testPrefix}.txt`, 'utf8')).startsWith('Customer attachment'),
      workspace: (await fs.readFile(`/workspace/${testPrefix}/result.txt`, 'utf8')).startsWith('Workspace result'),
    };
    for (const [email, password] of [[process.env.SEED_DEFAULT_USER_EMAIL, process.env.SEED_DEFAULT_USER_PASSWORD],
                                   ['state-second@example.invalid', evidence.secondPassword]]) {
      const origin = process.env.STATE_QUALIFICATION_ORIGIN || 'http://127.0.0.1:3080';
      const response = await fetch(origin + '/api/auth/login', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 ScientificAI-QA' },
        body: JSON.stringify({ email, password }) });
      checks[email === process.env.SEED_DEFAULT_USER_EMAIL ? 'primary_http_login' : 'second_http_login'] = response.ok;
      const auth = await response.json();
      if (response.ok && email === process.env.SEED_DEFAULT_USER_EMAIL) {
        const listing = await fetch(origin + '/api/convos', {
          headers: { Authorization: `Bearer ${auth.token}`, 'User-Agent': 'Mozilla/5.0 ScientificAI-QA' },
        });
        checks.native_history_api = listing.ok && (await listing.text()).includes(evidence.conversations[0]);
      }
    }
    console.log(JSON.stringify({ mode, checks, passed: Object.values(checks).every(Boolean) }));
    if (!Object.values(checks).every(Boolean)) process.exitCode = 1;
  } finally { await client.close(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
