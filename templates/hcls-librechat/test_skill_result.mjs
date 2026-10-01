import assert from 'node:assert/strict';
import { test } from 'node:test';
import { patchSkillResult, patchInstalledSkillPaths } from './patch-skill-result.mjs';

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

test('installed skill aliases retain ACLs and never read arbitrary host files', async () => {
  const source = `async function handleReadFileCall(tc, mergedConfigurable, options, req, onSandboxReadSuccess, signal) {
    if (!options.authorized) throw new Error('No access');
    return tc.args;
  }`;
  const handler = new Function(patchInstalledSkillPaths(source) + '; return handleReadFileCall;')();
  const original = {args:{path:'/app/skill/openff/SKILL.md', start_line:4}};
  assert.deepEqual(await handler(original, {}, {authorized:true}), {path:'openff/SKILL.md', start_line:4});
  assert.equal(original.args.path, '/app/skill/openff/SKILL.md');
  await assert.rejects(handler(original, {}, {authorized:false}), /No access/);
  for (const path of ['/etc/passwd', '/workspace/data.csv', 'gromacs/references/a.md']) {
    assert.equal((await handler({args:{path}}, {}, {authorized:true})).path, path);
  }
  assert.throws(() => patchInstalledSkillPaths(patchInstalledSkillPaths(source)), /already patched/);
  assert.throws(() => patchInstalledSkillPaths('different upstream'), /Unsupported/);
});
