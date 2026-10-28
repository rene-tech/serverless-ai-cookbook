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

// Deployment skills are loaded once into the API process. Refresh only the
// selected body from its registered file; metadata/ACLs still belong to the
// existing registry. A changed identity/frontmatter needs normal reloading.
export function patchDeploymentSkillFreshness(source) {
  if (source.includes('scientific-ai: current deployment skill body')) throw new Error('Skill freshness already patched');
  const replace = (before, after) => {
    if (source.split(before).length !== 2) throw new Error('Unsupported pinned deployment skill loader');
    source = source.replace(before, after);
  };
  replace('let registry$1 = new DeploymentSkillRegistry(null, []);',
    'const deploymentSkillBodySources = new WeakMap();\nlet registry$1 = new DeploymentSkillRegistry(null, []);');
  const start = source.indexOf('async function loadSkillFromDirectory(');
  const end = source.indexOf('async function loadDeploymentSkillFiles(', start);
  if (start < 0 || end < 0) throw new Error('Unsupported pinned deployment skill loader');
  const original = source.slice(start, end);
  let loader = original.replace('\n\treturn {\n\t\t_id: skillId,', '\n\tconst skill = {\n\t\t_id: skillId,');
  if (loader === original || !loader.endsWith('\n}\n')) throw new Error('Unsupported pinned deployment skill result');
  loader = loader.slice(0, -3) + '\n\tdeploymentSkillBodySources.set(skill, skillMdPath);\n\treturn skill;\n}\n';
  replace(original, loader);
  replace('function toSkillDetailRow(skill) {\n\tconst { files: _files, ...row } = skill;\n\treturn row;\n}', `
// scientific-ai: current deployment skill body, without API restart or reseed.
async function readCurrentDeploymentSkillBody(skill) {
\tconst filename = deploymentSkillBodySources.get(skill);
\tif (!filename) return skill.body;
\tconst content = await fs.default.promises.readFile(filename, "utf8");
\tconst parsed = parseStructuredFrontmatter(content);
\tif ("error" in parsed || !require("node:util").isDeepStrictEqual(parsed.frontmatter ?? {}, skill.frontmatter))
\t\tthrow new Error("Deployment skill metadata changed; reload its registered definition before use.");
\tconst { errors } = (0, _librechat_data_schemas.partitionIssues)((0, _librechat_data_schemas.validateSkillBody)(content));
\tif (errors.length) throw new Error("Deployment skill body is invalid: " + errors.map((error) => error.message).join("; "));
\treturn content;
}
async function toSkillDetailRow(skill) {
\tconst { files: _files, ...row } = skill;
\treturn { ...row, body: await readCurrentDeploymentSkillBody(skill) };
}`);
  replace('function toAlwaysApplyRow(skill) {\n\treturn {\n\t\t_id: skill._id,\n\t\tname: skill.name,\n\t\tbody: skill.body,',
    'async function toAlwaysApplyRow(skill) {\n\treturn {\n\t\t_id: skill._id,\n\t\tname: skill.name,\n\t\tbody: await readCurrentDeploymentSkillBody(skill),');
  replace('deploymentRows: limitRowsToDbPageBoundary(registry$1.listAlwaysApply(params).map(toAlwaysApplyRow), dbPageBoundary),',
    'deploymentRows: await Promise.all(limitRowsToDbPageBoundary(registry$1.listAlwaysApply(params), dbPageBoundary).map(toAlwaysApplyRow)),');
  return source;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const path = '/app/packages/api/dist/index.cjs';
  await writeFile(path, patchDeploymentSkillFreshness(patchInstalledSkillPaths(patchSkillResult(await readFile(path, 'utf8')))));
}
