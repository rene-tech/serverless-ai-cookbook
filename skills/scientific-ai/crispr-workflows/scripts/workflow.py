#!/usr/bin/env python3
"""Small, local CRISPR computation adapter; scientific models stay upstream."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import html
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

VERSION = "2026.10.22.1"
NUCLEASES = {"SpCas9": ("NGG", 20, "3prime"), "AsCas12a": ("TTTV", 23, "5prime")}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            result.update(chunk)
    return result.hexdigest()


def fasta(path):
    from Bio import SeqIO
    records = {}
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as handle:
        for record in SeqIO.parse(handle, "fasta"):
            seq = str(record.seq).upper()
            require(record.id not in records, f"Duplicate FASTA identifier: {record.id}")
            require(seq and not (set(seq) - set("ACGTN")),
                    f"{record.id}: expected DNA A/C/G/T/N, not protein/RNA/other ambiguity codes")
            records[record.id] = seq
    require(records, "FASTA contains no records")
    return records


def rc(seq):
    from Bio.Seq import reverse_complement
    return reverse_complement(seq)


def pam_regex(pam):
    from Bio.Data.IUPACData import ambiguous_dna_values
    require(pam and not (set(pam) - set(ambiguous_dna_values)), "PAM must use DNA IUPAC symbols")
    return "".join("[" + ambiguous_dna_values[c] + "]" for c in pam)


def candidates(records, nuclease):
    pam, size, side = NUCLEASES[nuclease]
    pattern = pam_regex(pam)
    for name, seq in records.items():
        for strand, oriented in (("+", seq), ("-", rc(seq))):
            for match in re.finditer("(?=(" + pattern + "))", oriented):
                p = match.start()
                start = p - size if side == "3prime" else p + len(pam)
                end = start + size
                if start < 0 or end > len(seq):
                    continue
                spacer = oriented[start:end]
                if "N" in spacer:
                    continue
                a, b = (start, end) if strand == "+" else (len(seq)-end, len(seq)-start)
                pa, pb = (p, p+len(pam)) if strand == "+" else (len(seq)-p-len(pam), len(seq)-p)
                context = oriented[start-4:end+6] if start >= 4 and end+6 <= len(seq) else ""
                yield {"record": name, "start0": a, "end0": b, "strand": strand,
                       "spacer": spacer, "pam": match.group(1), "pam_start0": pa, "pam_end0": pb,
                       "gc_fraction": (spacer.count("G")+spacer.count("C"))/size,
                       "poly_t": "TTTT" in spacer,
                       "context30": context if nuclease == "SpCas9" and "N" not in context else ""}


def command(args, log, timeout=900):
    with log.open("ab") as output:
        output.write(("$ "+shlex.join([str(x) for x in args])+"\n").encode())
        output.flush()
        result = subprocess.run([str(x) for x in args], stdout=output, stderr=output,
                                timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} exited {result.returncode}: " +
                           log.read_text(errors="replace")[-1500:])


def site_search(rows, reference_path, nuclease, mismatches, scratch, cpus):
    require(shutil.which("bowtie") and shutil.which("bowtie-build"),
            "Bowtie 1 runtime is missing; no reference-wide search was performed")
    require(isinstance(mismatches, int) and 0 <= mismatches <= 3,
            "Bowtie 1 mismatch search supports max_mismatches 0..3; bulges are not supported")
    reference = fasta(reference_path)
    # Index scratch is local disk, not Object Storage/FUSE. No shared mutable index.
    ref = scratch / "reference.fa"
    ref.write_text("".join(f">{name}\n{seq}\n" for name, seq in reference.items()))
    query = scratch / "guides.fa"
    query.write_text("".join(f">g{i}\n{r['spacer']}\n" for i, r in enumerate(rows)))
    index = scratch / "reference"
    log = scratch / "bowtie.log"
    command(["bowtie-build", "--quiet", ref, index], log)
    hits = scratch / "hits.tsv"
    command(["bowtie", "-f", "-v", mismatches, "-a", "--best", "--quiet", "-p", cpus,
             index, query, hits], log)
    pam, size, side = NUCLEASES[nuclease]
    sites = []
    for fields in csv.reader(hits.open(), delimiter="\t"):
        i, strand, name, pos = int(fields[0][1:]), fields[1], fields[2], int(fields[3])
        upstream = (side == "5prime") == (strand == "+")
        pa, pb = (pos-len(pam), pos) if upstream else (pos+size, pos+size+len(pam))
        if pa < 0 or pb > len(reference[name]):
            continue
        actual = reference[name][pa:pb]
        actual = actual if strand == "+" else rc(actual)
        if not re.fullmatch(pam_regex(pam), actual):
            continue
        sites.append({"guide_id": f"g{i}", "record": name, "start0": pos,
                      "end0": pos+size, "strand": strand, "pam": actual,
                      "mismatches": len(fields[7].split(",")) if len(fields)>7 and fields[7] else 0})
    counts = Counter(s["guide_id"] for s in sites)
    for i, row in enumerate(rows):
        row["candidate_sites_including_on_target"] = counts[f"g{i}"]
    return sites


def guides(spec, scratch):
    nuclease = spec.get("nuclease", "SpCas9")
    require(nuclease in NUCLEASES, f"Supported nuclease geometries: {', '.join(NUCLEASES)}")
    modality = spec.get("modality", "knockout")
    require(modality in ("knockout", "activation", "interference"), "Unknown guide modality")
    rows = list(candidates(fasta(spec["fasta"]), nuclease))
    # Explicit candidate interval; no invented transcript/exon/TSS coordinates.
    region = spec.get("region")
    if modality != "knockout":
        require(region and spec.get("region_rationale"),
                "Activation/interference needs an explicit region and TSS/isoform rationale")
    if region:
        require(len(region) == 2 and 0 <= region[0] < region[1], "region must be [start0,end0)")
        rows = [r for r in rows if r["start0"] >= region[0] and r["end0"] <= region[1]]
    for i, row in enumerate(rows):
        row.update(guide_id=f"g{i}", ruleset3=None)
    notes = ["Coordinates are zero-based, half-open on the supplied FASTA, not inferred genome coordinates.",
             "Predicted activity is not editing efficiency or experimental validation."]
    if nuclease == "SpCas9" and modality == "knockout" and spec.get("score", True):
        from rs3.seq import predict_seq
        tracr = spec.get("tracrRNA", "Hsu2013")
        require(tracr in ("Hsu2013", "Chen2013"), "tracrRNA must be Hsu2013 or Chen2013")
        scored = [r for r in rows if len(r["context30"]) == 30]
        if scored:
            values = predict_seq([r["context30"] for r in scored], sequence_tracr=tracr, n_jobs=1)
            for row, value in zip(scored, values):
                row["ruleset3"] = float(value)
        notes.append("Rule Set 3 sequence model, " + tracr + "; score is not a probability. Edge candidates without 30 nt context are unscored.")
    else:
        notes.append("No qualified on-target score for this modality/nuclease; no cleavage score is substituted for CRISPRa/i activity.")
    tables = {}
    if spec.get("reference_fasta") and rows:
        tables["candidate-sites"] = site_search(rows, spec["reference_fasta"], nuclease,
             spec.get("max_mismatches", 3), scratch, spec.get("cpus", 1))
        notes.append("Reference search includes the intended target; only supplied reference, canonical PAMs, <=3 mismatches, no bulges or unprovided variants. Hit count is not a risk score.")
    else:
        notes.append("Reference-wide off-target search NOT PERFORMED; absence of a search is not zero off-target risk.")
    tables["guides"] = sorted(rows, key=lambda r: (r["ruleset3"] is None, -(r["ruleset3"] or 0), r["guide_id"]))
    return tables, notes


def precision(spec, scratch):
    executable = os.getenv("CRISPR_PEGG_PYTHON", "/opt/crispr-pegg/bin/python")
    require(Path(executable).is_file(), "PEGG runtime is missing; no base/prime design was computed")
    request, output = scratch / "precision.json", scratch / "precision.csv"
    request.write_text(json.dumps(spec))
    command([executable, Path(__file__).with_name("precision.py"), request, output], scratch / "pegg.log")
    with output.open() as handle:
        rows = list(csv.DictReader(handle))
    return {"designs": rows}, ["PEGG 2.1.0 predictions, not measured editing efficiency.",
        "PEGG oligos include an added 5-prime G; native protospacer, extension and score fields are retained.",
        "Reference-wide off-targets and all possible bystander alleles are NOT assessed by this step.",
        "Select designs after reviewing the exact editor/window, locus, bystanders and validation plan."]


def primers(spec, scratch):
    import primer3
    records = fasta(spec["fasta"])
    require(len(records) == 1, "Primer design needs exactly one FASTA record")
    name, sequence = next(iter(records.items()))
    target = spec["target"]
    require(len(target) == 2 and 0 <= target[0] < target[0]+target[1] <= len(sequence),
            "target must be [start0,length] entirely inside the FASTA")
    settings = {"PRIMER_NUM_RETURN": 5, "PRIMER_PRODUCT_SIZE_RANGE": [[150, 300]]}
    settings.update(spec.get("primer3", {}))
    result = primer3.bindings.design_primers({"SEQUENCE_ID": name, "SEQUENCE_TEMPLATE": sequence,
                                            "SEQUENCE_TARGET": target}, settings)
    rows = [{"pair": i, "left": result[f"PRIMER_LEFT_{i}_SEQUENCE"],
             "right": result[f"PRIMER_RIGHT_{i}_SEQUENCE"],
             "left_tm": result[f"PRIMER_LEFT_{i}_TM"], "right_tm": result[f"PRIMER_RIGHT_{i}_TM"],
             "product_size": result[f"PRIMER_PAIR_{i}_PRODUCT_SIZE"]}
            for i in range(result["PRIMER_PAIR_NUM_RETURNED"])]
    return {"primers": rows, "primer3-diagnostics": [{"field": k, "value": v} for k,v in result.items()
             if k.endswith("EXPLAIN") or k.endswith("WARNING")]}, [
        "Primer3 thermodynamic design only; no genome-wide primer specificity check or wet-lab validation."]


def select(spec, scratch):
    import pandas as pd
    table = pd.read_csv(spec["table"], sep=spec.get("separator", ","))
    for column, value in spec.get("equals", {}).items():
        require(column in table, f"Unknown filter column: {column}")
        table = table[table[column] == value]
    for column, bounds in spec.get("between", {}).items():
        require(column in table and len(bounds) == 2, f"Invalid interval filter: {column}")
        table = table[pd.to_numeric(table[column], errors="raise").between(*bounds)]
    order = spec.get("order_by", [])
    if order:
        require(all(x["column"] in table for x in order), "Unknown sort column")
        table = table.sort_values([x["column"] for x in order], ascending=[x.get("ascending", True) for x in order], kind="stable")
    top = spec.get("top", len(table))
    require(isinstance(top, int) and top >= 0, "top must be a non-negative integer")
    # JSON conversion maps missing table values to null, never fabricated scores.
    return {"selected-guides": json.loads(table.head(top).to_json(orient="records"))}, [
        "Filtered user-supplied guide table; this selection does not validate its source or scores."]


def amplicons(spec, scratch):
    from Bio import SeqIO
    import edlib
    records = fasta(spec["fasta"])
    require(len(records) == 1 and spec.get("full_length_trimmed") is True,
            "Amplicon QC needs one reference and explicitly full_length_trimmed single/merged reads; raw paired-end FASTQ is not silently merged")
    reference = next(iter(records.values()))
    counts = {"reads": 0, "low_quality": 0, "unmapped": 0, "reference_exact": 0, "nonreference_aligned": 0}
    variants = {}
    path = spec["fastq"]
    require(0 <= spec.get("min_phred", 20) <= 93, "min_phred must be 0..93")
    require(0 <= spec.get("max_edit_fraction", 0.1) <= 1, "max_edit_fraction must be 0..1")
    with (gzip.open(path,"rt") if str(path).endswith(".gz") else open(path)) as handle:
        for read in SeqIO.parse(handle, "fastq"):
            counts["reads"] += 1
            if not read or min(read.letter_annotations["phred_quality"]) < spec.get("min_phred", 20):
                counts["low_quality"] += 1
                continue
            sequence = str(read.seq).upper()
            if set(sequence) - set("ACGT"):
                counts["unmapped"] += 1
                continue
            results = [edlib.align(s, reference, mode="NW", task="path") for s in (sequence, rc(sequence))]
            aligned = min(results, key=lambda r: r["editDistance"])
            if aligned["editDistance"] > len(reference)*spec.get("max_edit_fraction", 0.1):
                counts["unmapped"] += 1
                continue
            counts["reference_exact" if aligned["editDistance"] == 0 else "nonreference_aligned"] += 1
            key = (aligned["cigar"], aligned["editDistance"])
            variants[key] = variants.get(key, 0)+1
    require(counts["reads"] > 0, "FASTQ contains no reads")
    return {"read-qc": [counts], "alignment-classes": [dict(cigar=k[0],edit_distance=k[1],reads=v)
        for k,v in sorted(variants.items())]}, [
        "Exploratory full-length single-amplicon alignment QC, NOT CRISPResso2 or a calibrated editing-efficiency estimate.",
        "Sequencing errors, background variation and alignment ambiguity can produce non-reference reads. Compare controls and validate alleles before interpreting editing.",
        "No paired-end merging, locus demultiplexing, variant calling, cut-window assignment or UMI correction is performed."]


WORKFLOWS = {"guides": guides, "base": precision, "prime": precision, "primers": primers,
             "select": select, "amplicon-qc": amplicons}
COMMON = {"workflow", "species", "assembly", "notes", "cpus"}
FIELDS = {
    "guides": {"fasta", "nuclease", "modality", "region", "region_rationale", "score", "tracrRNA", "reference_fasta", "max_mismatches"},
    "base": {"variants_csv", "editor", "editing_window", "context_size"},
    "prime": {"variants_csv", "pbs_lengths", "rtt_lengths", "context_size", "top"},
    "primers": {"fasta", "target", "primer3"},
    "select": {"table", "separator", "equals", "between", "order_by", "top"},
    "amplicon-qc": {"fasta", "fastq", "full_length_trimmed", "min_phred", "max_edit_fraction"},
}


def write_report(destination, result, tables):
    def esc(value):
        return html.escape(str(value))
    parts = ["<!doctype html><html lang='en'><meta charset='utf-8'><title>CRISPR research report</title>",
      "<style>body{font:15px system-ui;margin:24px;color:#192821;background:#f5fff6}table{border-collapse:collapse;font-size:13px;display:block;overflow:auto}td,th{padding:7px;border:1px solid #cbd9cd;text-align:left}h1{color:#19683d}code{overflow-wrap:anywhere}.note{background:#fff;border-left:4px solid #7ccf95;padding:12px}small{color:#52635a}</style>",
      "<h1>Nebius Scientific AI · CRISPR</h1><p>"+esc(result["workflow"])+" · "+esc(result["status"])+"</p>",
      "<p class='note'>Computational research output; not a verified editing result or clinical recommendation.</p>",
      "<h2>Scope and limitations</h2><ul>"+"".join("<li>"+esc(x)+"</li>" for x in result["limitations"])+"</ul>"]
    for name, rows in tables.items():
        columns = list(rows[0]) if rows else []
        parts.append("<h2>"+esc(name)+f" ({len(rows)} rows)</h2>")
        if rows:
            parts.append("<table><thead><tr>"+"".join("<th>"+esc(k)+"</th>" for k in columns)+"</tr></thead><tbody>")
            parts.extend("<tr>"+"".join("<td>"+esc(row.get(k, ""))+"</td>" for k in columns)+"</tr>" for row in rows[:100])
            parts.append("</tbody></table>")
            if len(rows)>100:
                parts.append("<p>First 100 rows shown; complete data are in the corresponding CSV.</p>")
    parts.append("<h2>Reproducibility</h2><pre>"+esc(json.dumps({k:result[k] for k in ("inputs", "software", "elapsed_seconds")},indent=2))+"</pre></html>")
    (destination / "report.html").write_text("\n".join(parts))


def run(spec_path, destination):
    started = time.monotonic()
    spec_path, destination = Path(spec_path).resolve(), Path(destination).resolve()
    spec = json.loads(spec_path.read_text())
    workflow = spec.get("workflow")
    require(workflow in WORKFLOWS, "workflow must be one of: "+", ".join(WORKFLOWS))
    require(not (set(spec)-COMMON-FIELDS[workflow]), "Unknown request field(s): "+", ".join(sorted(set(spec)-COMMON-FIELDS[workflow])))
    require(spec.get("species") and spec.get("assembly"), "Specify species and assembly; use explicit synthetic/custom labels for non-genomic input")
    require(isinstance(spec.get("cpus", 1), int) and 1 <= spec.get("cpus", 1) <= 8, "cpus must be 1..8 for a CPU workbench")
    require(not destination.exists(), "Output directory exists; choose a new run directory to preserve previous evidence")
    inputs = {"request": {"name": spec_path.name, "sha256": digest(spec_path)}}
    for key in ("fasta", "reference_fasta", "variants_csv", "table", "fastq"):
        if key in spec:
            path = (spec_path.parent / spec[key]).resolve()
            require(path.is_file(), f"Missing input {key}: {path}")
            inputs[key] = {"name": path.name, "sha256": digest(path), "bytes": path.stat().st_size}
            spec[key] = str(path)
    destination.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="crispr-") as temp:
            # Limit only this command's CPU libraries, never the workbench environment.
            for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
                os.environ[variable] = str(spec.get("cpus", 1))
            tables, notes = WORKFLOWS[workflow](spec, Path(temp))
            for artifact in Path(temp).iterdir():
                if artifact.suffix == ".log" or artifact.name == "precision-runtime.json":
                    shutil.copyfile(artifact, destination/artifact.name)
            for name, rows in tables.items():
                with (destination / (name+".csv")).open("w", newline="") as handle:
                    if rows:
                        writer=csv.DictWriter(handle, fieldnames=list(rows[0]))
                        writer.writeheader(); writer.writerows(rows)
            software = {x:metadata.version(x) for x in ("biopython", "rs3", "primer3-py", "edlib")}
            software.update(workflow=VERSION, adapter_sha256=digest(__file__))
            if workflow in ("base", "prime"):
                software["pegg"] = json.loads((destination/"precision-runtime.json").read_text())
            if workflow == "guides" and spec.get("reference_fasta") and tables["guides"]:
                software["bowtie"] = subprocess.check_output(["bowtie","--version"],text=True).splitlines()[0]
            if not any(tables.values()):
                notes.append("No candidates satisfy these inputs/settings; this is not a successful design recommendation.")
            result = {"workflow":workflow, "status":"complete" if any(tables.values()) else "no_candidates", "inputs":inputs, "request":spec,
                "software":software, "elapsed_seconds":round(time.monotonic()-started,3),
                "tables":{k:len(v) for k,v in tables.items()}, "limitations":notes}
            write_report(destination, result, tables)
            result["artifacts"] = [{"file":p.name, "sha256":digest(p)} for p in sorted(destination.iterdir()) if p.is_file()]
            (destination / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
            if destination.is_relative_to("/workspace"):
                relative = destination.relative_to("/workspace").as_posix()
                result["inline_markdown"] = "[CRISPR report](/demos?"+urlencode({"tab":"workspace","path":relative,"file":"report.html"})+")"
            return {k:result[k] for k in ("status","workflow","tables","elapsed_seconds","limitations","inline_markdown") if k in result}
    except Exception as exc:
        (destination / "error.json").write_text(json.dumps({"status":"failed", "workflow":workflow,
            "error":str(exc), "inputs":inputs},indent=2)+"\n")
        raise


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args=parser.parse_args()
    try:
        print(json.dumps(run(args.spec, args.output), allow_nan=False))
    except Exception as exc:
        print(json.dumps({"status":"failed", "error":str(exc)}), file=sys.stderr)
        sys.exit(1)
