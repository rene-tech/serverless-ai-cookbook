# Plan → design → measurement → interpretation

Keep the same owned `/workspace/<study>/` directory, with fresh run directories
for changed inputs. Reuse existing environment-execution observation and file
tools; do not invent another background orchestration layer.

1. **Evidence and target selection:** Tavily and installed literature helpers
   locate primary sources. Read what the assay actually establishes. The
   ClawBio omics-target-evidence mapper can organize existing expression/GWAS
   evidence; target association is not causal proof.
2. **Define the intervention:** write species, assembly, transcript/locus,
   desired molecular change and relevant cell context. An unresolved item is
   a question, not permission to fabricate a value.
3. **Compute designs:** use the local request adapter. Offer a comparison of
   compatible nuclease/editor approaches with evidence and limitations, rather
   than equating one library's raw score across different models/editors.
4. **Specificity and validation:** distinguish guide candidate nomination,
   reference search, allele/bystander review, primer design, molecular editing
   measurement and functional phenotype. Each has its own evidence.
5. **Interpret measured outcomes:** load `clawbio-catalog` and the installed
   `clawbio-crispr-screen-triage` for screen hit triage. Check its actual input
   schema; do not call post-screen enrichment a raw-count CRISPR screen model.
   Use `clawbio-rnaseq-de` for supported differential expression and
   `clawbio-scrna-orchestrator`/`single-cell-analysis` for cellular phenotypes.
   Preserve replicate, batch, guide and cell identities; avoid pseudoreplication.
6. **Optional orthogonal models:** structure/ensemble prediction or imaging can
   address a separate stated hypothesis. Use the model-specific skill and live
   schema. Structural confidence is not guide specificity, target essentiality
   or editing efficiency. No extra GPU work is needed for ordinary guide design.
7. **Deliver:** inline owned report, full candidate tables, input hashes,
   versions, method/source citations, unresolved questions and a concise next
   step. Never claim wet-lab execution from a computed design.

## Paper-inspired evaluation

CRISPR-GPT (Qu et al., DOI 10.1038/s41551-025-01463-z) evaluates planning,
guide-table queries, delivery recommendations and Q&A. Its full testset and
full agent are not publicly available. Our separate evaluation should measure:

- planning task precision/recall and correct dependency order;
- exact filter/order/parameter correctness on known guide tables;
- correct sequences, strand/PAM/coordinates and independently checked outputs;
- grounded answers and appropriate handling of missing data/runtime capabilities;
- successful workbench execution, inline result delivery, latency and tool count.

Use identical base model, inputs, budgets and repeated runs for baseline versus
skill-enabled comparisons. Keep expected answers out of the candidate prompt.
Use independent human reviewers for evidence quality and experimental advice;
an LLM's self-grade is not an expert-blinded replication. Preserve failures as
failures and report confidence intervals/sample sizes rather than a universal
claim that one system is better.
