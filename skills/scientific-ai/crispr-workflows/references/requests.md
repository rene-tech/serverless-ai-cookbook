# Local computation requests

All requests require `workflow`, `species`, `assembly`. Paths are relative to the
request JSON unless absolute. FASTA identifiers must be unique. DNA uses ACGTN;
candidate spacers with N are excluded. Unknown request fields fail explicitly.
Results use forward-FASTA, zero-based half-open intervals. These are not
automatically genomic coordinates. A user must supply the locus origin before
mapping a fragment's coordinates onto a genome assembly.

## Guides and explicit-reference site search

```json
{
  "workflow": "guides",
  "species": "synthetic",
  "assembly": "demo-v1",
  "fasta": "target.fa",
  "nuclease": "SpCas9",
  "modality": "knockout",
  "tracrRNA": "Hsu2013",
  "reference_fasta": "reference.fa",
  "max_mismatches": 3,
  "cpus": 1
}
```

`nuclease`: SpCas9 (NGG, 20 nt) or AsCas12a (TTTV, 23 nt). No custom PAM is
silently interpreted as a validated editor. Omit `reference_fasta` only if a
reference search is not requested; absence is recorded prominently. Bowtie
builds a local temporary index, so human-genome indexing is not an instant
operation. Large genomes/library searches need a suitably sized CPU workbench;
the small example timing is not a full-genome throughput promise.

`modality`: knockout, activation, interference. The last two require
`region: [start0,end0]` and `region_rationale` explaining the chosen TSS/isoform
and target window. `score: false` disables RS3 deliberately, without claiming
activity scoring happened. `tracrRNA` can be Hsu2013 or Chen2013.

## Base/prime editing

CSV has a `SEQ` column: explicit flanking DNA with one `(REF/ALT)` edit.
`(A/G)` is substitution; `(/AC)` insertion; `(AC/)` deletion. Use uppercase DNA,
unambiguous flanks, and preserve accession/build outside the sequence. This
syntax is PEGG's native input, not an installation of PrimeDesign.

```json
{"workflow":"base","species":"synthetic","assembly":"demo-v1",
 "variants_csv":"variants.csv","editor":"CBE","editing_window":[4,8]}
```

The window is an explicit user scientific setting, not a universal editor
default. Base input accepts only SNPs. Inspect whether PEGG marks a guide in the
desired window; a returned guide outside that window is not a recommended edit.

```json
{"workflow":"prime","species":"synthetic","assembly":"demo-v1",
 "variants_csv":"variants.csv","pbs_lengths":[10,13,15],
 "rtt_lengths":[10,15,20,25,30],"top":10}
```

PBS/RTT lengths are configurable; defaults are exploration settings, not a
guarantee of activity. `context_size` defaults to 120 nt. All native PEGG columns
are retained so the agent cannot discard a caveat while presenting a score.

## Primers

```json
{"workflow":"primers","species":"synthetic","assembly":"demo-v1",
 "fasta":"target.fa","target":[200,30],
 "primer3":{"PRIMER_NUM_RETURN":5,"PRIMER_PRODUCT_SIZE_RANGE":[[150,300]]}}
```

`target` uses start0 and length (not end). Other documented Primer3 global
settings pass through directly. Review thermodynamic and assay assumptions.

## Query a precomputed guide library

```json
{"workflow":"select","species":"synthetic","assembly":"demo-v1",
 "table":"guides.csv","equals":{"gene":"DEMO1"},
 "between":{"position":[100,500]},
 "order_by":[{"column":"score","ascending":false}],"top":3}
```

CSV by default; `separator:"\t"` for TSV. Filter fields use exact existing
column names. Values/ranking preserve the input's score definitions. No SQL or
Python expression is evaluated from user text.

## Full-length amplicon exploratory QC

```json
{"workflow":"amplicon-qc","species":"synthetic","assembly":"demo-v1",
 "fasta":"amplicon.fa","fastq":"reads.fastq.gz",
 "full_length_trimmed":true,"min_phred":20,"max_edit_fraction":0.1}
```

No silent read merging or adapter trimming. Exact-reference and nonreference
alignment counts are not automatically edit fractions. Paired raw reads must
first use an appropriate installed and validated preprocessing workflow.

## Synthetic getting-started bundle

```sh
/opt/crispr-core/bin/python /app/skill/crispr-workflows/scripts/make_examples.py \
  --output /workspace/demos/crispr
```

This creates deterministic synthetic inputs and one request per operation;
existing directories are never overwritten. It does not download a human genome
or make any model calls. Run the selected JSON with `workflow.py`; do not pretend
the generated sequences came from a biological sample or the published benchmark.
