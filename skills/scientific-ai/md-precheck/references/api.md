# REST usage

Use the same Scientific AI key and origin as GROMACS. No additional account or
checker installation is needed. Keep keys in environment/secret storage.

Upload input bytes using the existing `/v1/scientific-artifacts/uploads` reserve,
content transfer and finalize flow. Supply `model_id: "mdprecheck"`; preserve
the finalized immutable `artifact` object. The input document is:

```json
{
  "input": "REPLACE_WITH_FINALIZED_ARTIFACT_OBJECT",
  "input_format": "tar.gz",
  "coords": "conf.gro",
  "top": "topol.top",
  "mdp": "md.mdp",
  "intent": ["dt=0.002", "stage=production"],
  "probes": []
}
```

The string placeholder is deliberately not executable: `input` must be the
actual object containing `artifact_id`, `sha256`, `size_bytes`, `media_type`,
and `compression: "none"` returned by finalization.

- Read-only reuse: `POST /v1/mdprecheck/lookup` with this input document.
- Execute: `POST /v1/models/mdprecheck:invoke` with
  `{"operation":"check-md-inputs","payload":INPUT_DOCUMENT,"wait_seconds":0}`
  and an `Idempotency-Key` header. HTTP 202 returns `operation.id`.
- Observe: `GET /v1/operations/{id}`.
- Result: `GET /v1/operations/{id}/result` after publication.
- Download each report using the existing artifact download API/helper; verify
  size and SHA-256. The JSON result contains compact findings and separate
  `artifacts.html` / `artifacts.json` references.

Execution can succeed while the scientific verdict is `fail` or `warn`. A new
scientific input needs a new idempotency key. Identical retry uses the old key.
