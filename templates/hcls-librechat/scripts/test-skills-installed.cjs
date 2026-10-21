/* Exercise the real bundled LibreChat deployment-skill loader; no DB or secrets. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { initializeDeploymentSkills, createDeploymentSkillMethods } = require('/app/packages/api/dist/index.cjs');

async function main() {
  const manifest = JSON.parse(fs.readFileSync('/app/skill/manifest.json', 'utf8'));
  const registry = await initializeDeploymentSkills({
    projectRoot: '/app', env: { DEPLOYMENT_SKILLS_DIR: '/app/skill' },
  });
  const loaded = registry.list();
  const expected = Object.keys(manifest.skills);
  // The full workbench and additive skills release retain the pinned ClawBio
  // extension when present. Reject unexpected or accidentally dropped skills.
  if (fs.existsSync('/opt/clawbio/manifest.json')) {
    const extension = JSON.parse(fs.readFileSync('/opt/clawbio/manifest.json', 'utf8'));
    expected.push(...Object.keys(extension.skills).map(name => `clawbio-${name}`));
  }
  assert.deepEqual(loaded.map(x => x.name).sort(), expected.sort());
  const methods = createDeploymentSkillMethods({});
  let files = 0;
  for (const skill of loaded) {
    assert.ok(skill.body.length && skill.description.length, skill.name);
    assert.equal(skill.disableModelInvocation, undefined, skill.name);
    const retrieved = await methods.getSkillByName(skill.name, registry.ids());
    assert.equal(retrieved.body, skill.body, skill.name);
    for (const file of skill.files) {
      const read = await methods.getSkillFileByPath(skill._id, file.relativePath);
      assert.ok(read, `${skill.name}/${file.relativePath}`);
      if (read.content !== undefined && !read.isBinary) {
        const raw = fs.readFileSync(file.filepath, 'utf8');
        assert.equal(read.content, raw, `${skill.name}/${file.relativePath}`);
      }
      files++;
    }
  }
  const root = JSON.parse(fs.readFileSync('/app/skill/files.sha256.json', 'utf8'));
  for (const [name, expected] of Object.entries(root)) {
    const actual = crypto.createHash('sha256').update(fs.readFileSync(`/app/skill/${name}`)).digest('hex');
    assert.equal(actual, expected, name);
  }
  // Test the documented commands against this image's actual helper, not a
  // newer checkout. --help exits before any upload, admission or observation.
  const example = fs.readFileSync('/app/skill/rfd4-proteina/references/client-example.md', 'utf8');
  const commands = [...example.matchAll(/```bash\n([\s\S]*?)\n```/g)].map(match => match[1]);
  assert.equal(commands.length, 2);
  for (const command of commands) {
    const args = command.includes('--recover-operation-id')
      ? ['--recover-operation-id', 'op-example', '--help'] : ['--help'];
    const help = execFileSync('/opt/scientific-client/bin/python',
      ['/opt/bionemo/invoke-scientific-batch.py', ...args], { encoding: 'utf8', timeout: 30000 });
    const supported = new Set(help.match(/--[a-z][a-z-]+/g));
    for (const option of command.match(/--[a-z][a-z-]+/g)) {
      assert.ok(supported.has(option), `Packaged helper does not support documented ${option}`);
    }
  }
  console.log(JSON.stringify({ status: 'passed', version: manifest.version,
    loader: 'LibreChat initializeDeploymentSkills + getSkillByName/getSkillFileByPath',
    skills: loaded.length, resources: files, verified_files: Object.keys(root).length,
    inference_calls: 0, customer_readiness_claim: false }));
}
main().then(() => process.exit(0)).catch(error => { console.error(error); process.exit(1); });
