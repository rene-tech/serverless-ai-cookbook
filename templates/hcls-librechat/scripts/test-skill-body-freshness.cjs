/* CPU-only qualification in the candidate image, no Mongo, provider or GPU. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { createRequire } = require('node:module');
const appRequire = createRequire('/app/package.json');
const { initializeDeploymentSkills, createDeploymentSkillMethods } = appRequire('@librechat/api');

(async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-skill-freshness-'));
  const front = '---\nname: measured-report\ndescription: Report verified measurements\nalways-apply: true\n---\n';
  const filename = path.join(root, 'measured-report', 'SKILL.md');
  await fs.mkdir(path.dirname(filename));
  await fs.writeFile(filename, front + 'Original verified guidance.\n');
  try {
    const registry = await initializeDeploymentSkills({ projectRoot: root, env: { DEPLOYMENT_SKILLS_DIR: root } });
    const ids = registry.ids();
    assert.equal(ids.length, 1);
    let databaseLookups = 0;
    const custom = { _id: 'custom-preserved', body: 'Custom user content', metadata: { private: true } };
    const methods = createDeploymentSkillMethods({
      getSkillByName: async (name) => { databaseLookups++; return name === 'custom' ? custom : null; },
      getSkillById: async (id) => id === custom._id ? custom : null,
      listAlwaysApplySkills: async () => ({ skills: [], has_more: false, after: null }),
    });
    const original = await methods.getSkillByName('measured-report', ids);
    assert.equal(original.body, front + 'Original verified guidance.\n');
    const unchanged = { ...original }; delete unchanged.body;
    const updated = front + 'New verified guidance, complete URL /demos?file=report.html and unknowns preserved.\n';
    await fs.writeFile(filename + '.new', updated);
    await fs.rename(filename + '.new', filename);
    const fresh = await methods.getSkillByName('measured-report', ids, { preferModelInvocable: true });
    assert.equal(fresh.body, updated);
    const after = { ...fresh }; delete after.body;
    assert.deepEqual(after, unchanged);
    assert.equal(databaseLookups, 0, 'Deployment reads must not touch custom database rows');
    assert.equal((await methods.getSkillById(ids[0])).body, updated);
    const automatic = await methods.listAlwaysApplySkills({ accessibleIds: ids, limit: 10 });
    assert.equal(automatic.skills.length, 1);
    assert.equal(automatic.skills[0].body, updated);
    assert.equal(await methods.getSkillByName('measured-report', []), null, 'Denied IDs stay denied');
    assert.strictEqual(await methods.getSkillByName('custom', []), custom);
    assert.strictEqual(await methods.getSkillById(custom._id), custom);
    await fs.writeFile(filename, updated.replace('name: measured-report', 'name: different-name'));
    await assert.rejects(methods.getSkillByName('measured-report', ids), /metadata changed/);
    await fs.writeFile(filename, updated.replace('always-apply: true', 'always-apply: false'));
    await assert.rejects(methods.getSkillById(ids[0]), /metadata changed/);
    await fs.writeFile(filename, '---\nname: [invalid\n---\n');
    await assert.rejects(methods.getSkillByName('measured-report', ids), /metadata changed/);
    await fs.unlink(filename);
    await assert.rejects(methods.getSkillByName('measured-report', ids), /ENOENT/);
    await fs.writeFile(filename, updated);
    assert.equal((await methods.getSkillByName('measured-report', ids)).body, updated);
    console.log(JSON.stringify({ passed: true, checks: [
      'selected body refresh without registry/API restart', 'exact metadata and IDs preserved',
      'model/manual detail and always-apply use fresh body', 'ACL miss still denied',
      'custom DB content untouched', 'changed identity/flags/malformed/unreadable fail closed',
      'restored source works without restart'], provider_calls: 0, gpu_calls: 0 }));
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
