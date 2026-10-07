# Durable native timing reports

Use this when a user requests a new MD run plus a native throughput/timing
report. Read `scientific-batch` and discover the installed `batch` and
`native-md-timing` methods. The complete plan below is illustrative: retain the
user's archive, parameters, identity, display name and actual repeat count.
Three repeats here means three distinct native simulation step IDs, not three
resumed segments or three statistically independent replicas.

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
      "id": "timings",
      "kind": "analysis",
      "method": "native-md-timing",
      "arguments": {
        "manifest_file": {"step": "simulate", "file": "native-files.json"},
        "expected_repeats": 3
      }
    }
  ],
  "deliverables": [
    {"name": "Native timing report", "role": "report", "source": {"step": "timings", "file": "native-timing-report.md"}},
    {"name": "Native timing rows", "role": "metrics", "source": {"step": "timings", "file": "native-timings.csv"}},
    {"name": "Native timing provenance", "role": "provenance", "source": {"step": "timings", "file": "native-timing-report.json"}},
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
Runs → Whole studies even if the chat disconnects. Read the saved study's terminal
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
