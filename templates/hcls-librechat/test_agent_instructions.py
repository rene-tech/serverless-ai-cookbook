"""Offline regression for the shared primary-agent instruction source."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class AgentInstructionsTest(unittest.TestCase):
    def test_core_is_bounded_and_contains_execution_contract(self):
        text = (HERE / 'agent-instructions.md').read_text()
        self.assertLess(len(text), 10600)
        for required in ('Explain or recommend', 'Inspect existing data', 'Execute',
                         'exit_code', 'terminal', 'idempotency', 'scientific-gateway'):
            self.assertIn(required, text)
        self.assertNotIn('schema: scientific-workflow/v1', text)

    def test_gromacs_precheck_is_a_pre_submission_conversation_choice(self):
        text = (HERE / 'agent-instructions.md').read_text()
        for required in ('GROMACS exception', 'WAIT', 'separate turn',
                         'saved study plans', 'changed duration',
                         'Do not submit MD while asking', 'Explicit refusal',
                         'unchanged checkpoint continuation', 'not a mandatory'):
            self.assertIn(required, text)
        root = HERE.parents[1] / 'skills' / 'scientific-ai'
        gromacs = (root / 'gromacs' / 'SKILL.md').read_text()
        self.assertLess(gromacs.index('end this turn'), gromacs.index('Establish the scientific protocol'))
        self.assertIn('even as queued work', gromacs)
        self.assertIn('prior execution is not evidence', gromacs)
        precheck = (root / 'md-precheck' / 'SKILL.md').read_text()
        self.assertIn('end the turn and wait', precheck)
        self.assertIn('changed requested duration', precheck)

    def test_language_and_precheck_interpretation_are_explicit(self):
        text = (HERE / 'agent-instructions.md').read_text()
        for required in ("Reply in the user's language", 'English requests get English replies',
                         'only when requested', 'installed runner', '`reused:false`',
                         'not proof of a crash', 'already-authorized justified repairs'):
            self.assertIn(required, text)
        precheck = (HERE.parents[1] / 'skills/scientific-ai/md-precheck/SKILL.md').read_text()
        for required in ('new receipt directory', 'current input/options',
                         'not this conversation', 'missing scientific choices',
                         'not replace the requested workload'):
            self.assertIn(required, precheck)

    def test_rendered_endpoint_uses_the_same_core(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'librechat.json'
            env = dict(os.environ, SCIENTIFIC_DISCOVER_CHAT_MODELS='false',
                       SCIENTIFIC_CORE_INSTRUCTIONS_PATH=str(HERE / 'agent-instructions.md'))
            for name in ('SCIENTIFIC_CHAT_MODEL', 'TEAM_ID', 'TEAM_BUCKET_NAME'):
                env.pop(name, None)
            subprocess.run(['node', str(HERE / 'render-config.mjs'), str(output)],
                           env=env, check=True, capture_output=True)
            config = json.loads(output.read_text())
            serialized = json.dumps(config)
            core = (HERE / 'agent-instructions.md').read_text().strip()
            prefixes = [item.get('preset', {}).get('promptPrefix', '')
                        for item in config['modelSpecs']['list']]
            matching = [prefix for prefix in prefixes if prefix.startswith(core)]
            self.assertTrue(matching)
            self.assertTrue(all(len(prefix) < 11100 for prefix in matching))
            self.assertNotIn('checks Apps and /workspace/examples/v1/README.md', serialized)

    def test_seed_primary_does_not_append_legacy_manual(self):
        script = r'''
const vm = require('node:vm'); const fs = require('node:fs');
const seedRequire = require('node:module').createRequire(process.argv[1]);
const captured = [];
class MongoClient {
  async connect() {} async close() {}
  db() { return { collection(name) { return {
    async updateOne(query, update) { if(name==='agents') captured.push(update.$set); },
    async findOne() { return {_id: 'test-only'}; }
  }; } }; }
}
const context = { require(name) {
  if(name==='mongodb') return {MongoClient, ObjectId: class ObjectId {}};
  if(name==='librechat-data-provider') return {Constants: {mcp_all:'all'}};
  if(name==='node:fs') return fs;
  if(name==='./seed-merge.cjs') return seedRequire(name);
  throw new Error(name);
}, process:{env:{
  SCIENTIFIC_CORE_INSTRUCTIONS_PATH: process.argv[2],
  SCIENTIFIC_AGENT_INSTRUCTIONS_PATH: process.argv[3]
}, stdout:{write(){}}, stderr:process.stderr,
set exitCode(value){process.exitCode=value;},
exit(){throw new Error('seed failed');}}, console};
Promise.resolve(vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context))
  .then(()=>console.log(JSON.stringify(captured)))
  .catch(error=>{console.error(error);process.exitCode=1;});
'''
        with tempfile.TemporaryDirectory() as folder:
            legacy = Path(folder) / 'legacy.md'
            legacy.write_text('LEGACY_MANUAL_MUST_NOT_BE_IN_PRIMARY')
            run = subprocess.run(['node', '-e', script, str(HERE / 'seed-workbench.js'),
                                  str(HERE / 'agent-instructions.md'), str(legacy)],
                                 check=True, capture_output=True, text=True)
            agents = json.loads(run.stdout)
            primary = next(a for a in agents if a['id'] == 'agent_nebius_scientific_ai')
            self.assertEqual(primary['instructions'], (HERE / 'agent-instructions.md').read_text().strip())
            self.assertEqual(primary['model'], 'moonshotai/Kimi-K3')
            self.assertEqual(primary['model_parameters']['reasoning_effort'], 'high')
            self.assertEqual(primary['model_parameters']['maxContextTokens'], 1024000)
            self.assertTrue(primary['skills_enabled'])
            self.assertIn('all_mcp_scientific-ai-apps', primary['tools'])
            design = next(a for a in agents if a['id'] == 'agent_molecular_design')
            self.assertTrue({name + '_mcp_scientific-ai-apps' for name in (
                'submit_rfd4_proteina', 'submit_rfdiffusion', 'submit_proteina_complexa',
                'submit_bindcraft', 'submit_boltzgen', 'submit_mosaic', 'infer_proteinmpnn_native',
            )} <= set(design['tools']))
            self.assertGreater(len(agents), 1)
            tutorial = next(a for a in agents if a['id'] == 'agent_protein_structure')
            self.assertNotIn('LEGACY_MANUAL_MUST_NOT_BE_IN_PRIMARY', tutorial['instructions'])
            self.assertTrue(tutorial['instructions'].startswith((HERE / 'agent-instructions.md').read_text().strip()))


if __name__ == '__main__':
    unittest.main()
