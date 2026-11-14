---
name: runai-msa-search-pdb70
description: Search the pinned public PDB70 database with MMseqs2 through managed Scientific AI REST or typed MCP and retrieve the original A3M alignment.
---

# PDB70 homology search

Discover `GET /v1/models/msa-search-pdb70?workflow=search-msa` or MCP
`md_models` with `{"model":"msa-search-pdb70","detail":true}`. Use the
scientific version `mmseqs2-8cc5ce36-pdb70-220313` only where your account's
discovery advertises it. This guide is a contract, not production or commercial
clearance; the current candidate remains in SYSTEM qualification.

This is a CPU-only MMseqs2 search over PDB70 release 220313, containing 92,110
public sequences. It is not NVIDIA NIM, structure prediction or experimental
validation. GPU selection is unnecessary; request `gpu:"cpu"` and a region
permitted by discovery.

Use the [portable gateway client](../runai-scientific-gateway/references/client.md)
for environment-based authentication, bucket uploads, submit-once, polling and
full-hash artifact retrieval. No private helper or Run:ai administrator access is
required. Fetch [fixture.py](fixture.py) and [check_result.py](check_result.py) from the same published revision
as this guide, saving both files locally; fetching only `SKILL.md` does not install
the helpers. Public downloads must not receive your scientific bearer token.

## Search MSA

<a id="search-msa"></a>
MCP tool: `msa-search-pdb70_search_msa`.

The input is one gzip tar named `input.tar.gz`. Its root contains UTF-8
`query.json`, with this shape:

```json
{"sequence":"ACDEFG","databases":["pdb70_220313"],"max_msa_sequences":500,"output_alignment_formats":["a3m"]}
```

Only `sequence` is required in the query JSON. Whitespace is removed and letters
are uppercased before the canonical length check of 6–4096 amino acids. The
alphabet is `ACDEFGHIKLMNPQRSTVWY`; ambiguous letters, gaps and non-string values
are rejected. The whole query JSON must fit within 256 KiB. Do not submit FASTA,
Python, shell commands, arbitrary paths or remote database URLs.

`max_msa_sequences` is 1–5000, default 500, including the query itself. Fewer
available homologs is a successful result. Only `databases:["pdb70_220313"]` and
`output_alignment_formats:["a3m"]` are accepted. Explicit typed `parameters`
override the corresponding query JSON controls; omitted typed fields preserve
explicit query values. An omitted value in both places uses the native default.

For the complete public ubiquitin example:

```sh
export INPUT_KEY=work/your-campaign/pdb70-input.tar.gz
PREPARED=prepared-pdb70
python3 fixture.py --key "$INPUT_KEY" --output "$PREPARED"
aws s3 cp "$PREPARED/input.tar.gz" "s3://$SCIENTIFIC_DATA_BUCKET/$INPUT_KEY" \
  --endpoint-url "$SCIENTIFIC_DATA_ENDPOINT" --region "$SCIENTIFIC_DATA_REGION" \
  --content-type application/gzip
```

Use a fresh directory and unused key in your existing approved bucket. Discover
the workflow's example into `request.json` using the shared client, then bind the
exact uploaded archive and supported placement:

```sh
jq --slurpfile input "$PREPARED/input-reference.json" \
   '.inputs=[$input[0]] | .parameters={} |
    .version="mmseqs2-8cc5ce36-pdb70-220313" |
    .region="eu-north1" | .gpu="cpu"' request.json > request-ready.json
mv request-ready.json request.json
```

Use another region if your account does not permit that placement. Follow the
gateway's REST submission, or call `msa-search-pdb70_search_msa` with `inputs`,
`parameters`, `version`, `region`, `gpu` and your saved `idempotency_key`. Omit
REST's `model` and `workflow` fields from typed MCP. Keep the original idempotency
key, exact request bytes and returned run ID after any transport uncertainty;
never guess whether an uncertain submission should be replayed.

## Results and scientific checks

Poll the same ID using `md_run_status`; retrieve `md_run_artifacts`. Download all
owner artifacts, preserving their relative paths and checking every full SHA-256
and exact byte count before using them. Do not send the API bearer token to signed
bucket download URLs or print those URLs. For the supplied default fixture only:

```sh
python3 check_result.py --result-dir results
```

The checker requires the original deterministic ubiquitin alignment with 141
records at the default cap 500. It must not be applied to other queries or changed
parameters. Main files are `data/outputs/search/alignment.a3m`, `result.json` and
`science.json`. A3M starts with the query; lowercase insertions and gaps retain
native alignment semantics. Avoid treating all A3M character positions as query
residue positions.

Metadata reports exact scientific version, engine revision, database, canonical
query hash/length, requested cap, actual sequence count and alignment hash. Search
seconds exclude queueing, image pull, startup, transfers and billing. Images,
registry addresses and deployment identifiers remain internal. More homologs do
not establish biological function, binding or structure accuracy.

## Storage, recovery and errors

Each finite CPU job uses a private temporary volume; query scratch and cache stay
inside the owner's job data and are synchronized to that owner's bound bucket.
Idle compute scales to zero. Another bucket requires an approved owner binding;
parameters cannot grant storage access. Only the owner and authorized
administrators can retrieve requests or artifacts.

One short query is the closed unit. Interrupted unfinished MMseqs2 searches
recompute under the same original request, version and expiry; there is no native
mid-search process checkpoint. Completed results are durable in the owner bucket.
Final upload retries have a five-minute bound, then scratch is deleted even if
unsynced tail data is lost; a failed upload must be reported. Do not claim a
cross-region recovery was tested solely because another region is listed.

Read structured `error.code`, field, retryability and next action. Invalid
sequences/settings are input errors; an unavailable validation runtime is a
retryable service error. Unauthorized regions fail without dispatch. Preserve the
original run ID for diagnosis rather than repeatedly submitting a failed request.

The exact pinned MMseqs2 revision is MIT-licensed; PDB70 data carries CC-BY 4.0
attribution. These are separate from dependency/security or whole-service hosting
clearance. Sources: [MMseqs2](https://github.com/soedinglab/MMseqs2),
[PDB70](https://wwwuser.gwdguser.de/~compbiol/data/hhsuite/databases/hhsuite_dbs/),
[CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode).
