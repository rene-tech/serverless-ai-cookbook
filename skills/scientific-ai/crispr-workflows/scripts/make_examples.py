"""Create deterministic, clearly synthetic examples; never customer data."""
import argparse
import csv
import json
from pathlib import Path
import random


def create(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    rng = random.Random(22026)
    sequence = list("".join(rng.choices("ACGT", k=800)))
    sequence[200:223] = "GACTACGTCGATCGTACGATAGG"  # C at spacer position six.
    sequence[190:193] = "AGG"  # A second nick geometry makes the same edit prime-designable.
    sequence[500:527] = "TTTA"+"GACTACGTCGATCGTACGATACG"
    sequence = "".join(sequence)
    (destination/"target.fa").write_text(">synthetic-target\n"+sequence+"\n")
    (destination/"reference.fa").write_text(">synthetic-target\n"+sequence+"\n>synthetic-near-match\n"+
        "ATCG"+"GACTACGTCGATCGTACGAAAGG"+"ATCG"+"\n")
    with (destination/"variants.csv").open("w",newline="") as handle:
        writer=csv.writer(handle); writer.writerow(["SEQ"])
        assert sequence[205] == "C"
        writer.writerow([sequence[:205]+"(C/T)"+sequence[206:]])
    (destination/"amplicon.fa").write_text(">synthetic-amplicon\n"+sequence[150:270]+"\n")
    ref=sequence[150:270]
    reads=[ref]*8+[ref[:54]+"T"+ref[55:]]*2+[ref[:54]+ref[55:]]
    (destination/"reads.fastq").write_text("".join(f"@synthetic-{i}\n{s}\n+\n{'I'*len(s)}\n" for i,s in enumerate(reads)))
    with (destination/"guides.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=["id","gene","position","score"]); writer.writeheader()
        writer.writerows(dict(id=f"synthetic-{i}",gene="DEMO1" if i%2 else "DEMO2",position=i*20,score=i/50) for i in range(50))
    common={"species":"synthetic","assembly":"synthetic-demo-22026"}
    specs={
        "guides":{"fasta":"target.fa","nuclease":"SpCas9","reference_fasta":"reference.fa","max_mismatches":3},
        "base":{"variants_csv":"variants.csv","editor":"CBE","editing_window":[4,8]},
        "prime":{"variants_csv":"variants.csv","pbs_lengths":[10,13],"rtt_lengths":[15,20,30],"top":5},
        "primers":{"fasta":"target.fa","target":[200,30]},
        "select":{"table":"guides.csv","equals":{"gene":"DEMO1"},"between":{"position":[100,500]},"order_by":[{"column":"score","ascending":False}],"top":3},
        "amplicon-qc":{"fasta":"amplicon.fa","fastq":"reads.fastq","full_length_trimmed":True},
    }
    for name,spec in specs.items():
        (destination/(name+".json")).write_text(json.dumps(dict(common,workflow=name,**spec),indent=2)+"\n")
    (destination/"README.md").write_text("# Synthetic CRISPR examples\n\nSeed 22026; no biological sample, gene or patient. Requests cover computational paths, not wet-lab validation. Amplicon truth: 8 exact-reference, 2 substitutions, 1 deletion; 11 high-quality full-length reads.\n")
    return {"directory":str(destination),"requests":list(specs),"synthetic":True}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--output",required=True)
    print(json.dumps(create(parser.parse_args().output)))
