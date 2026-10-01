import assert from 'node:assert/strict';
import { test } from 'node:test';
import { patchSkillResult } from './patch-skill-result.mjs';

const fixture = `async function handler(args, skill) {
  if (!skill.accessible) throw new Error('No access');
  let body = skill.body;
  if (args.args) body = body.replace(/\\$ARGUMENTS/g, args.args);
\tconst injectedMessages = [buildSkillPrimeMessage({
\t\tname: skill.name,
\t\tbody
\t})];
\tlet contentText = \`Skill "\${args.skillName}" loaded. Follow the instructions below.\`;
  return {content:contentText, injectedMessages, artifact:skill.artifact};
}`;

test('model-invoked skill is returned completely as reference tool content', async () => {
  const handler = new Function(patchSkillResult(fixture) + '; return handler;')();
  const result = await handler({skillName: 'test', args: 'same authorized task'},
    {accessible:true, body:'Do $ARGUMENTS. Keep `quotes` and ${literal}.', artifact:{files:['asset']}});
  assert.equal(result.injectedMessages.length, 0);
  assert.match(result.content, /continue the user's existing request/);
  assert.match(result.content, /Do same authorized task\. Keep `quotes` and \$\{literal\}\./);
  assert.deepEqual(result.artifact, {files:['asset']});
  await assert.rejects(handler({skillName:'test'}, {accessible:false}), /No access/);
});

test('upstream drift and double patching are rejected', () => {
  assert.throws(() => patchSkillResult('different upstream'), /Unsupported/);
  assert.throws(() => patchSkillResult(patchSkillResult(fixture)), /already patched/);
});
