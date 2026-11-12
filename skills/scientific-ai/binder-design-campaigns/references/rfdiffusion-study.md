# RFdiffusion through the existing LibreChat study owner

This is the **LibreChat** path, requiring the installed scientific-study tools.
For plain MCP/Claude Code, use the hosted campaign through the portable batch
client. Do not call nonexistent study tools from a plain MCP connection.

When the live RFdiffusion schema advertises `campaign`, register it as **one
batch phase** in the existing `scientific-workflow/v2` plan. The example below
requests 65 unconditional backbones in one public operation: a 64-design GPU
chunk at seeds 8100–8163 and one at seed 8164. The platform owns this graph;
the study owner advances any subsequent models/analysis after its verified result.
This unconditional study template is CPU/schema qualified. A separate hosted
65-design hotspot campaign passed live checks using nine chunks (eight designs
per chunk, then one) with `max_parallelism=4`; that proof does not qualify this
LibreChat study template or 1,000-design throughput.

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

Generate the parameter file and the whole existing study plan in that same
directory. Choose a new stable campaign key for a distinct intended experiment,
never to bypass a pending or failed request:

```python
import json
from pathlib import Path

root = Path('/workspace/rfdiffusion-campaign')
campaign_key = 'backbone-study-001'
step = 'backbone_campaign'
parameters = root / f'{step}.parameters.json'
parameters.write_text(json.dumps({
    'schema': 'fs2-serve.nebius.ai/rfdiffusion-parameters/v1',
    'operation': 'design-backbone', 'contigs': ['80-80'],
    'num_designs': 64, 'seed': 8100, 'diffuser_T': 50,
    'campaign': {'total_designs': 65, 'max_parallelism': 2}
}, indent=2) + '\n')
steps = [{
    'id': step, 'kind': 'batch', 'model': 'rfdiffusion',
    'tool': 'submit_rfdiffusion', 'operation': 'design-backbone',
    'source': str(root / 'design-note.txt'),
    'source_artifact': str(root / 'source-upload/artifact.json'),
    'parameters': str(parameters), 'media_type': 'text/plain', 'compression': 'none',
    'entry_name': 'design_constraint', 'semantic_type': 'rfdiffusion-design-constraint/v1',
    'idempotency_key': campaign_key,
    'display_name': '65 backbones at seeds 8100..8164'
}]
deliverables = [{'name': 'campaign-outputs.json', 'role': 'provenance',
                 'source': {'step': step, 'file': 'output-manifest.json'}}]
plan = {'schema': 'scientific-workflow/v2', 'title': '65 backbone designs',
        'steps': steps, 'deliverables': deliverables}
(root / 'study-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
```

Inspect the current `describe_scientific_workflow` contract, validate the plan,
and use its supported `run_scientific_workflow` launch with
`/workspace/rfdiffusion-campaign/study-plan.json`. Register the **whole plan**;
a handwritten tracker or a promise to continue is not a registered study.
The existing worker records the one accepted operation. Follow that study's
receipt after disconnects; do not launch a second study or recreate keys.

An unknown admission or held child stops further admission for reconciliation.
Failures remain failures; preserve their diagnostic artifacts and do not replay
them automatically. Cancellation uses the existing study/operation owner and
must preserve already accepted IDs and durable evidence. A 1,000-design
campaign uses the same single batch phase with `total_designs=1000`: fifteen
64-design chunks plus 40. Register any requested downstream analyses in the same
study before launch. Read the [campaign guide](../../scientific-gateway/references/portable-campaign.md)
for account admission, cumulative budgets, partial archives and unresolved slot states.
