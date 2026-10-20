# Recover a temporarily interrupted status read

A disconnected client does **not** mean the accepted simulation failed.
Keep its original output folder and operation ID; do not submit a replacement.
The current helper retries transient reads up to five times, within the command's
wait period, and respects `Retry-After`. It never retries a scientific execution.

## Update a standalone client

Download into a new directory, not over a helper used by a running process.
Keep the Python environment and credentials you already use:

```sh
mkdir -p scientific-client-update
curl --fail --location \
  https://raw.githubusercontent.com/rene-tech/serverless-ai-cookbook/6cd4e8fe0488d085779adc1b52ddab2c60cc5cd8/templates/hcls-librechat/scripts/scientific-batch-acceptance.py \
  -o scientific-client-update/scientific-batch-acceptance.py
for module in scientific_receipts.py native_md_artifacts.py; do
  curl --fail --location \
    "https://raw.githubusercontent.com/rene-tech/serverless-ai-cookbook/6cd4e8fe0488d085779adc1b52ddab2c60cc5cd8/templates/hcls-librechat/$module" \
    -o "scientific-client-update/$module"
done
python scientific-client-update/scientific-batch-acceptance.py \
  --observe-output /path/to/original/output
```

Use the same `SCIENTIFIC_MODELS_MCP_URL` and `SCIENTIFIC_MODELS_API_KEY`.
The original folder must contain the saved receipt. This command only reads that
operation and verifies/downloads its results; it cannot upload inputs, admit,
cancel, restart or resume a simulation. Original input files are not required.
Repeating the original submission command with its unchanged output directory,
inputs and key also observes its saved operation rather than admitting another.

If observation is interrupted, the final JSON contains `state: "unknown"`,
`last_observed_state`, the original `operation_id`, and an exact
`recovery_command`. The receipt keeps the last authoritative scientific state,
separately from the observation error. Reuse that command and directory.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Results downloaded and hash verified. |
| `75` | Still pending, or observation temporarily unavailable. Not scientific failure. |
| `77` | Authentication/authorization rejected. Resolve access before retrying. |
| `66` | Operation/session endpoint not found. Check the original endpoint and ID. |
| `65` | Request or observation rejected; correct the reported issue first. |
| `1` | Scientific failure/action required, unavailable authorized tool, or unexpected code error. The JSON outcome distinguishes expected failures; unexpected code errors retain a traceback. |

Scientific failures preserve the platform's specific error code, reason and next
action, with status/diagnostic files in the same directory. A failed diagnostics
download does not turn a failed simulation into a success.

The standalone script and future image are released separately from running
workbenches. Updating the default image does not restart or patch existing
clients or change accepted jobs. This recovery qualification is not a claim
that all models, sustained capacity or cluster failover are production-ready.

## Release and evidence

Source: `6cd4e8fe0488d085779adc1b52ddab2c60cc5cd8`.
Future default image: `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:observation-recovery-20261020-r1`,
manifest `sha256:de999b74fa47b0e1b5c9bb6b80ac90b4e1028d6f143069f52bcb63faa5310729`.
The [release receipt](evidence/client-observation-recovery-20261020.json)
records two clean installed-image cohorts (166 tests each). Both the actual
installed helper and the independently downloaded, public client recovered an
existing internal job after five locally injected read failures, verified all
47 result artifacts, and preserved a failed synthetic job's specific error.
No inputs were uploaded, no jobs submitted or restarted, and no current
workbench was changed. All 50 base-image layers, including the inline report
renderer, remain unchanged; this image adds only the observer-helper layer.
