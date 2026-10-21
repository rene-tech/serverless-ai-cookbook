# One hosted request from a LibreChat workspace

First verify the live schema and use a real caller-owned, uncompressed annotated
CIF. Save `examples/parameters.json` as a new workspace parameter file, retaining
the user's intended settings. The existing helper handles artifact upload,
finalization, the canonical manifest and the named MCP submission:

The [contract snapshot](hosted-contract.json) validates the example offline;
it does not replace the caller's live schema or prove deployment.

```bash
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --model rfd4-proteina --tool submit_rfd4_proteina --operation generate \
  --source /workspace/my-studies/rfd4/input.cif \
  --entry-name annotated-cif --semantic-type rfd4-proteina-annotated-cif/v1 \
  --media-type chemical/x-cif --compression none \
  --parameters /workspace/my-studies/rfd4/parameters.json \
  --output /workspace/my-studies/rfd4/result \
  --display-name 'RFD4 generation' --idempotency-key YOUR_STABLE_REQUEST_KEY \
  --service-class customer-batch --wait-seconds 180 --poll-seconds 10
```

Paths and the idempotency key above are illustrative, not files or credentials
that already exist. Credentials come from the configured client environment,
never the command arguments or chat. Reuse the same output directory to observe
an accepted request; do not choose a new key to poll it. A bounded wait may exit
pending. With the currently packaged observer, continue read-only:

```bash
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --observe-output /workspace/my-studies/rfd4/result --wait-seconds 180
```

This invokes the same hosted App; it does not install or execute RFD4 on the
LibreChat VM. Other MCP clients use their trusted file bridge and the same typed
tool directly, not this LibreChat-specific filesystem path.

Read the `result` JSON artifact and verify the `designs` tar against its artifact
hash. Extract safely into a fresh directory, then use a real `designs[].path`
under that directory, checking its SHA256 and size. The path normally lives
under `outputs/inference_samples/`; the generated CIF is already uncompressed.
Invoke the available viewer with the verified paths, for example:

```json
{
  "workspace_files": [
    {
      "path": "/workspace/my-studies/rfd4/result/extracted/design.cif",
      "label": "RFD4 generated candidate"
    }
  ],
  "title": "RFD4 generated structure"
}
```

`design.cif` is a placeholder: use the exact `designs[].path` from the result,
not a guessed name. Render the returned UI resource marker inline;
also retain the native job ID, parameters, source/checkpoint identity reported
by the result and the verified original files.
