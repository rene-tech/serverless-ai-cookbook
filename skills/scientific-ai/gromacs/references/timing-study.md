# Durable native timing reports

Use this when a user requests a new MD run plus results, timing or visualization.
Read `scientific-batch` and discover the installed `batch` and `python-script`
methods. The complete plan below is illustrative: retain the
user's archive, parameters, identity, display name and actual repeat count.
Three repeats here means three distinct native simulation step IDs, not three
resumed segments or three statistically independent replicas. The preview step
uses the installed deterministic renderer, not an LLM-written analysis. Copy
`/opt/bionemo/native_md_preview.py` to `/workspace/md/preview-native-md.py` before
admission; the executor freezes its bytes. The script creates both the native
timing report, `native-md-report.html` summary and optional embedded final-structure
preview, using the installed helpers. The separate coordinate preview is not a
full report; inspect requested sections and disclose missing evidence.
It works with older running study workers too: do not depend on a new
`native-md-timing` method being present in their schema.
This example has one job with three
simulation steps, so it publishes one final-coordinate PDB. For multiple jobs
declare `final-structure-2.pdb` etc.; the viewer supports up to four jobs.

```json
{
  "schema": "scientific-workflow/v2",
  "title": "MD run and native timing report",
  "steps": [
    {
      "id": "simulate",
      "kind": "batch",
      "model": "gromacs",
      "tool": "submit_gromacs_workflow",
      "operation": "run-workflow",
      "source": "/workspace/md/input.tar.gz",
      "parameters": "/workspace/md/parameters.json",
      "entry_name": "gromacs-inputs",
      "semantic_type": "gromacs-input-bundle/v1",
      "media_type": "application/x-tar",
      "compression": "gzip",
      "idempotency_key": "md-performance-repeats-01",
      "display_name": "MD performance repeats"
    },
    {
      "id": "results",
      "kind": "analysis",
      "method": "python-script",
      "arguments": {
        "script": "/workspace/md/preview-native-md.py",
        "inputs": [{"name": "native_manifest", "file": {"step": "simulate", "file": "native-files.json"}}],
        "parameters": {"expected_repeats": 3, "structure_preview": true},
        "outputs": ["native-md-report.html", "native-timing-report.json", "native-timings.csv", "native-timing-report.md", "md-structure-preview.html", "md-structure-preview.json", "final-structure-1.pdb"]
      }
    }
  ],
  "deliverables": [
    {"name": "Native MD HTML report", "role": "report", "source": {"step": "results", "file": "native-md-report.html"}},
    {"name": "Interactive final structure", "role": "support", "source": {"step": "results", "file": "md-structure-preview.html"}},
    {"name": "Final structure coordinates", "role": "support", "source": {"step": "results", "file": "final-structure-1.pdb"}},
    {"name": "Preview provenance", "role": "provenance", "source": {"step": "results", "file": "md-structure-preview.json"}},
    {"name": "Native timing report", "role": "report", "source": {"step": "results", "file": "native-timing-report.md"}},
    {"name": "Native timing rows", "role": "metrics", "source": {"step": "results", "file": "native-timings.csv"}},
    {"name": "Native timing provenance", "role": "provenance", "source": {"step": "results", "file": "native-timing-report.json"}},
    {"name": "Native file mapping", "role": "support", "source": {"step": "simulate", "file": "native-files.json"}},
    {"name": "Output artifact manifest", "role": "provenance", "source": {"step": "simulate", "file": "output-manifest.json"}}
  ]
}
```

Compose/finalize this plan once, then invoke `run_scientific_workflow`. Its batch
step handles upload and immutable artifact references; do not separately upload
the same source or fall back to a second submission because a local draft lacks
a report. Correct an unadmitted draft; retain an accepted study's identity.

Study admission is not completion. The durable worker finishes native execution,
downloads/hash-checks the original result and logs, then publishes the report in
the live chat card and Runs → Whole studies even if the chat disconnects.
The final-coordinate preview is interactive 3D, not a trajectory animation or
proof of equilibration. Larger structures are explicitly protein-only in the
preview; full original coordinates and trajectories remain in the native files.
Read the saved study's terminal
state and verified downloads before claiming the benchmark is finished. The
native timing JSON must have `complete: true`, the actual requested repeat count
and nonempty timing rows. Source logs and commands remain linked and unmodified.

`result.json` is the platform envelope. `output-manifest.json` identifies raw
transport artifacts. **`native-files.json`** is the installed client's verified
native mapping consumed by this analysis method. They are not interchangeable.
Missing native rates or repeats retain an incomplete report and stop the study;
unknown executed/durably completed step counts remain null, not inferred from
an absolute checkpoint position.

For an already completed operation, use the read-only recovery and installed
`report-native-md.py` commands in the main skill. Alternatively, an analysis-only
saved study can pass the exact recovered `/workspace/.../native-files.json` path
to this same method; no new simulation is needed. Do not edit an admitted old
plan or overwrite its earlier incomplete report.
