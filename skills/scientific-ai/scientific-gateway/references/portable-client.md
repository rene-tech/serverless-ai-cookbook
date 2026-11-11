# Scientific AI from a laptop or Claude Code

Use your issued Scientific AI MCP URL and personal inference API key. A
LibreChat password, Claude subscription and Token Factory key are different
credentials. Read the API key from an environment variable or secret store;
never paste it into a chat, request JSON, command-line argument or source file.

The hosted MCP provides caller-scoped discovery, typed model calls, operation
polling and artifact authorization. It does **not** install `workbench_*`,
`environment-execution`, `visualize_structure`, `visualize_workspace_media`,
or the `run/describe/compose/read_scientific_workflow` study tools. Those are
LibreChat additions. `manifest.json.client_requirements` marks each skill's
client dependencies; its presence does not grant or install them.

## Install the existing file client

The separate `scientific-ai-client-*.tar.gz` release asset packages the same
uploader, batch client and receipt modules as the workbench, without its API,
viewer, model weights or supervisor. Verify its `.sha256` file, extract it,
then run these commands inside `scientific-ai-client` on Python 3.11+ on
Linux/macOS (or WSL). This does not need Docker or `/opt/bionemo`.

```bash
sha256sum -c SHA256SUMS  # macOS: shasum -a 256 -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python upload-artifact.py --help
.venv/bin/python invoke-scientific-batch.py --help
```

If the client archive is not present in the selected release, build it from
that release's pinned cookbook checkout (this copies existing source bytes;
it does not implement another upload protocol):

```bash
python3 templates/hcls-librechat/scripts/package-scientific-client.py \
  --output /absolute/path/outside-the-checkout
```

`source-files.json` records each packaged source path and hash. The skill
bundle's existing `bundle.py verify/install` remains independent and refuses
to overwrite customized skills. Downloading skills alone does not install
these Python dependencies.

## Configure the connection

In Bash, set the endpoint from your handoff and enter the key without shell
history. A secret manager can populate the same variables instead.

```bash
export SCIENTIFIC_MODELS_MCP_URL='https://YOUR-ISSUED-HOST/mcp'
read -rsp 'Personal Scientific AI API key: ' SCIENTIFIC_MODELS_API_KEY
printf '\n'
export SCIENTIFIC_MODELS_API_KEY
```

For Claude Code, merge this into `.mcp.json`, preserving other servers:

```json
{
  "mcpServers": {
    "scientific-ai": {
      "type": "http",
      "url": "${SCIENTIFIC_MODELS_MCP_URL}",
      "headers": {"Authorization": "Bearer ${SCIENTIFIC_MODELS_API_KEY}"}
    }
  }
}
```

Start with `get_model_schema` for a known model. Omit `protocol` unless you
select an exact published contract value; an execution-mode label is not a
versioned protocol identifier. On the current server, `scientific-batch`
selects that execution family; `scientific-batch-v1` selects its protocol.
Read the source role/media contract and typed tool before
submitting. A missing contract is a support gap, not permission to guess or
probe by spending GPU work.

For unknown models, `list_models` and `list_scientific_models` return compact
pages by default. Use `query` for a model/name/category substring and `limit`
(1–100, default 20); follow `next_offset` with `offset` until it is null.
For example, `list_scientific_models({"query":"rfdiffusion","limit":20})`
discovers the matching authorized models without loading every full schema.
Fetch `get_model_schema` only for the selected App. If the tool's live schema
does not expose these pagination fields, report the older server revision;
do not invent parameters or truncate a full response and call it complete.

## Transfer and resume

- `upload-artifact.py` uploads one file and verifies the finalized SHA-256,
  byte count, MIME and encoding. It creates no manifest or model operation.
- `invoke-scientific-batch.py` validates the live schema and source metadata,
  uploads source and manifest, submits the exact named tool once, polls, and
  verifies output hashes. It saves the operation ID and private receipts.
- `invoke-native.py` handles discovered native named tools using a JSON input
  file; fill artifact fields from the uploader's verified `artifact.json`.

Use one output directory and stable idempotency key per intended request.
Do not edit inputs or change identity inside an accepted receipt directory.
For an existing batch receipt, this command only observes/downloads that
operation; exit `75` means still incomplete, not failed science:

```bash
.venv/bin/python invoke-scientific-batch.py \
  --observe-output ./runs/my-run --wait-seconds 180
```

For a completed operation whose local receipt is absent, use a **new** directory:

```bash
.venv/bin/python invoke-scientific-batch.py \
  --recover-operation-id "$OPERATION_ID" --output ./runs/recovered
```

This does not submit, cancel or repeat the model. Keep receipt directories
private: they may contain scientific inputs/results and temporary signed URLs.
Hash verification proves transport integrity, not scientific correctness.

Follow the worked RFdiffusion example, restricted-access BindCraft2 design/CPU
analysis examples and own-bucket guide shipped beside this file
(`portable-rfdiffusion.md`, `portable-bindcraft2.md`, `bucket-access.md` in the
skill bundle; `worked-example.md`, `bindcraft2-example.md`, `bucket-access.md`
in the client archive).
