// Keep model-invoked skill instructions inside the tool result. A synthetic
// user turn can be mistaken for a new, already-answered request by OpenAI-
// compatible providers. Manual skill invocation and file/ACL handling remain
// upstream-owned. Fail closed on a different upstream implementation.
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

export function patchSkillResult(source) {
  const before = `\tconst injectedMessages = [buildSkillPrimeMessage({
\t\tname: skill.name,
\t\tbody
\t})];
\tlet contentText = \`Skill "\${args.skillName}" loaded. Follow the instructions below.\`;`;
  const after = `\t// scientific-ai: reference content is a tool result, not a new user turn.
\tconst injectedMessages = [];
\tlet contentText = \`Skill "\${args.skillName}" loaded. Use these reference instructions to continue the user's existing request; loading a skill does not complete that request.\\n\\n\${body}\`;`;
  if (source.includes(after)) throw new Error('Skill result already patched');
  if (source.split(before).length !== 2) throw new Error('Unsupported pinned skill handler');
  return source.replace(before, after);
}

export function patchInstalledSkillPaths(source) {
  const before = 'async function handleReadFileCall(tc, mergedConfigurable, options, req, onSandboxReadSuccess, signal) {';
  const after = before + `
\t// scientific-ai: installed read-only skill path aliases, same upstream ACLs.
\tif (typeof tc.args?.path === 'string' && tc.args.path.startsWith('/app/skill/')) {
\t\ttc = {...tc, args: {...tc.args, path: tc.args.path.slice('/app/skill/'.length)}};
\t}`;
  if (source.includes(after)) throw new Error('Installed skill paths already patched');
  if (source.split(before).length !== 2) throw new Error('Unsupported pinned file handler');
  return source.replace(before, after);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const path = '/app/packages/api/dist/index.cjs';
  await writeFile(path, patchInstalledSkillPaths(patchSkillResult(await readFile(path, 'utf8'))));
}
