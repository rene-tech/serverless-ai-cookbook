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
  `{"operation":"check-md-inputs","payload":INPUT_DOCUMENT}`.
  Set the client timeout to 2400 seconds. HTTP 200 returns the completed `result`
  and native request receipt. There is no 202, job polling or async fallback.
  Do not send `Idempotency-Key`, `wait_seconds` or asynchronous controls.
- Download each report using the existing artifact download API/helper; verify
  size and SHA-256. The JSON result contains compact findings and separate
  `artifacts.html` / `artifacts.json` references.

Execution can succeed while the scientific verdict is `fail` or `warn`.
After a timeout, look up the exact input/options before explicitly retrying;
never automatically repeat inference. Uploads retain their own idempotency keys.
