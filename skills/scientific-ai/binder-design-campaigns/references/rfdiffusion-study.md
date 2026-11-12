# RFdiffusion through the existing LibreChat study owner

This is the **LibreChat** path, requiring the installed scientific-study tools.
For plain MCP/Claude Code, use the portable campaign client instead. Do not call
nonexistent study tools from a plain MCP connection.

Freeze all intended batches in one `scientific-workflow/v2` plan before launch.
The example below is a 65-design unconditional-backbone campaign: two native
requests, 64 designs at seeds 8100–8163 and one at seed 8164. It introduces no
new scheduler or native limit. Each native request retains ordinary admission,
queueing, retry, cancellation and artifact semantics.

Prepare a workspace directory and provenance note, then upload that note once
using the existing uploader. Preserve the returned `artifact.json`; never fill
in an invented artifact ID. These commands only prepare/upload input, not models:

```bash
mkdir -p /workspace/rfdiffusion-campaign
printf '%s\n' '65 unconditional 80-residue backbones; seeds 8100..8164; no binding claim.' \
  > /workspace/rfdiffusion-campaign/design-note.txt
/opt/scientific-client/bin/python /opt/bionemo/upload-artifact.py \
  --model rfdiffusion --file /workspace/rfdiffusion-campaign/design-note.txt \
  --media-type text/plain --compression none \
  --idempotency-key backbone-study-001-source \
  --output-dir /workspace/rfdiffusion-campaign/source-upload
```

Generate both parameter files and the whole existing study plan in that same
directory. Choose a new stable campaign key for a distinct intended experiment,
never to bypass a pending or failed request:

```python
import json
from pathlib import Path

root = Path('/workspace/rfdiffusion-campaign')
campaign_key = 'backbone-study-001'
steps, deliverables = [], []
for index, (seed, count) in enumerate([(8100, 64), (8164, 1)]):
    step = f'design_{index:06d}'
    parameters = root / f'{step}.parameters.json'
    parameters.write_text(json.dumps({
        'schema': 'fs2-serve.nebius.ai/rfdiffusion-parameters/v1',
        'operation': 'design-backbone', 'contigs': ['80-80'],
        'num_designs': count, 'seed': seed, 'diffuser_T': 50
    }, indent=2) + '\n')
    steps.append({
        'id': step, 'kind': 'batch', 'model': 'rfdiffusion',
        'tool': 'submit_rfdiffusion', 'operation': 'design-backbone',
        'source': str(root / 'design-note.txt'),
        'source_artifact': str(root / 'source-upload/artifact.json'),
        'parameters': str(parameters), 'media_type': 'text/plain', 'compression': 'none',
        'entry_name': 'design_constraint', 'semantic_type': 'rfdiffusion-design-constraint/v1',
        'idempotency_key': f'{campaign_key}-{index:06d}',
        'display_name': f'Backbones at seeds {seed}..{seed + count - 1}'
    })
    deliverables.append({'name': f'{step}-outputs.json', 'role': 'provenance',
                         'source': {'step': step, 'file': 'output-manifest.json'}})
plan = {'schema': 'scientific-workflow/v2', 'title': '65 backbone designs',
        'steps': steps, 'deliverables': deliverables}
(root / 'study-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
```

Inspect the current `describe_scientific_workflow` contract, validate the plan,
and use its supported `run_scientific_workflow` launch with
`/workspace/rfdiffusion-campaign/study-plan.json`. Register the **whole plan**;
a handwritten tracker or a promise to continue is not a registered study.
The existing worker owns iteration and records actual accepted IDs. Follow that
study's receipt after disconnects; do not launch a second study or recreate keys.

An unknown admission or held child stops further admission for reconciliation.
Failures remain failures; preserve their diagnostic artifacts and do not replay
them automatically. Cancellation uses the existing study/operation owner and
must preserve already accepted IDs and durable evidence. A full 1,000-design
plan uses 15 × 64 plus 40 with the same non-overlapping seed rule; freeze every
phase before launch. This example is CPU/schema qualified, not a claim that
these 65 designs or a thousand-design campaign have been run successfully.
