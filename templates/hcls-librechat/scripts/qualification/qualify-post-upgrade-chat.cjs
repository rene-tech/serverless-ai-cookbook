/* Real customer-facing chat turn on the isolated state qualification instance.
 * Verifies retained provider/tool credentials and a tool-written bucket artifact.
 * No GPU inference and no modification of the preserved customer agent fixture.
 */
'use strict';
const fs = require('node:fs/promises');
const crypto = require('node:crypto');
const { MongoClient } = require('mongodb');

async function main() {
  if (process.env.SCIENTIFIC_STUDY_OWNER !== 'system-state-qualification-20261002') {
    throw new Error('Restricted to the isolated state qualification instance');
  }
  const origin = process.env.STATE_QUALIFICATION_ORIGIN;
  if (!origin?.startsWith('https://')) throw new Error('Supply the public HTTPS origin');
  const label = process.env.STATE_QUALIFICATION_CHAT_LABEL || 'after-upgrade';
  if (!/^[a-z0-9-]{1,64}$/.test(label)) throw new Error('Invalid label');
  const output = `/workspace/qa-state-20261002/${label}.txt`;
  try { await fs.access(output); throw new Error('Refusing to overwrite prior chat evidence'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const headers = { 'Content-Type': 'application/json', Origin: origin,
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36' };
  const request = async (path, body) => {
    const response = await fetch(origin + path, {
      method: body ? 'POST' : 'GET', headers,
      ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(45000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status} at ${path}`);
    const content = await response.text();
    try { return JSON.parse(content); }
    catch {
      // LibreChat can return HTTP 200 with an SSE error before chat admission.
      // Preserve it privately; never print raw provider or authentication data.
      await fs.writeFile(`/data/hcls-librechat/qa-chat-${label}-response.txt`, content, { mode: 0o600 });
      throw new Error(`Non-JSON chat response at ${path}; private diagnostic retained`);
    }
  };
  const login = await request('/api/auth/login', { email: process.env.SEED_DEFAULT_USER_EMAIL,
    password: process.env.SEED_DEFAULT_USER_PASSWORD });
  headers.Authorization = `Bearer ${login.token}`;
  const db = new MongoClient(process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/LibreChat');
  await db.connect();
  let agent;
  try { agent = await db.db().collection('agents').findOne({ id: 'agent_nebius_scientific_ai' }); }
  finally { await db.close(); }
  const job = await request('/api/agents/chat', {
    endpoint: 'agents', agent_id: agent.id, model: agent.id,
    text: `Use your execution tool to read /workspace/qa-state-20261002/result.txt. ` +
      `Write its contents verbatim to ${output}, then report the file link. ` +
      'Do not change any other file, do not submit GPU inference. This checks my workspace after a client update.',
    conversationId: null, parentMessageId: '00000000-0000-0000-0000-000000000000',
    messageId: crypto.randomUUID(), clientRequestId: crypto.randomUUID(),
    isContinued: false, isRegenerate: false,
  });
  const start = Date.now();
  let status;
  do {
    await new Promise(resolve => setTimeout(resolve, 3000));
    status = await request('/api/agents/chat/status/' + job.conversationId);
    if (Date.now() - start > 300000) {
      await request('/api/agents/chat/abort', { conversationId: job.streamId });
      throw new Error('QA chat exceeded 300 seconds; only this generation was aborted');
    }
  } while (status.active);
  const messages = await request('/api/messages/' + job.conversationId);
  const answers = messages.filter(message => !message.isCreatedByUser);
  const parts = answers.flatMap(message => message.content || []);
  const checks = {
    retained_default: agent.model === 'moonshotai/Kimi-K3' && agent.model_parameters?.reasoning_effort === 'high',
    visible_reply: parts.some(part => part.type === 'text' && String(part.text || '').trim()),
    tool_execution: parts.some(part => part.type === 'tool_call'),
    no_errors: !answers.some(message => message.error || message.unfinished) && !parts.some(part => part.type === 'error'),
    workspace_artifact: await fs.readFile(output, 'utf8') === await fs.readFile('/workspace/qa-state-20261002/result.txt', 'utf8'),
  };
  const models = await fetch('https://89.169.99.188/v1/models', {
    headers: { Authorization: `Bearer ${process.env.SCIENTIFIC_MODELS_API_KEY}` },
    signal: AbortSignal.timeout(30000),
  });
  checks.hosted_model_discovery = models.ok && (await models.json()).data?.length > 0;
  console.log(JSON.stringify({ conversation_id: job.conversationId, seconds: (Date.now() - start) / 1000,
    checks, passed: Object.values(checks).every(Boolean) }));
  if (Object.values(checks).every(Boolean)) {
    await fs.writeFile(`/data/hcls-librechat/qa-chat-${label}-receipt.json`, JSON.stringify({
      conversation_id: job.conversationId, output,
      sha256: crypto.createHash('sha256').update(await fs.readFile(output)).digest('hex'),
    }), { mode: 0o600 });
  }
  if (!Object.values(checks).every(Boolean)) process.exitCode = 1;
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
