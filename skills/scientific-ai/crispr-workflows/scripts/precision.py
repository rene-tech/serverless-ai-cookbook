"""Execute unmodified PEGG in its own pinned Python environment."""
import json
import hashlib
import importlib.metadata as metadata
from pathlib import Path
import re
import sys

import pandas as pd
from pegg import base, prime


def design(spec):
    frame = pd.read_csv(spec["variants_csv"])
    if "SEQ" not in frame or frame.empty:
        raise ValueError("variants_csv needs nonempty SEQ rows: flankingDNA(reference/alternative)flankingDNA")
    for seq in frame["SEQ"]:
        if not isinstance(seq, str) or not re.fullmatch(r"[ACGT]+\([ACGT]*/[ACGT]*\)[ACGT]+",seq):
            raise ValueError("Use uppercase DNA with one explicit (REF/ALT) edit per SEQ; no ambiguous bases")
        match = re.search(r"\(([ACGT]*)/([ACGT]*)\)", seq)
        if match[1] == match[2]:
            raise ValueError("Reference and alternative must differ")
        if spec["workflow"] == "base" and (len(match[1]) != 1 or len(match[2]) != 1):
            raise ValueError("Base-editing input must be a single nucleotide substitution; use prime for indels")
    context = spec.get("context_size",120)
    if not isinstance(context,int) or not 30 <= context <= 1000:
        raise ValueError("context_size must be 30..1000 nucleotides")
    common = dict(input_format="PrimeDesign", PAM="NGG", proto_size=20,
                  context_size=context, sensor=False)
    if spec["workflow"] == "base":
        editor = spec.get("editor")
        window = spec.get("editing_window")
        if editor not in ("ABE", "CBE") or not window or len(window)!=2 or not 1<=window[0]<=window[1]<=20:
            raise ValueError("Base editing requires editor ABE/CBE and explicit editing_window [first,last] at protospacer positions 1..20")
        results = base.run_base(frame, filtration=editor, ideal_edit_window=window, auto_SNP_filter=False, **common)
    else:
        pbs=spec.get("pbs_lengths",[10,13,15]); rtt=spec.get("rtt_lengths",[10,15,20,25,30])
        if not all(isinstance(x,int) and 1<=x<=100 for x in pbs+rtt) or not pbs or not rtt:
            raise ValueError("PBS/RTT lengths must be nonempty integer lists between 1 and 100")
        top=spec.get("top", "All")
        if top != "All" and (not isinstance(top, int) or top < 1):
            raise ValueError("prime top must be a positive integer or All")
        results = prime.run(frame, PBS_lengths=pbs, RTT_lengths=rtt, pegRNAs_per_mut=top, **common)
    return results


if __name__ == "__main__":
    design(json.loads(Path(sys.argv[1]).read_text())).to_csv(sys.argv[2], index=False)
    runtime={"version":metadata.version("pegg"), "scikit_learn":metadata.version("scikit-learn"),
      "files":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(prime.__file__).parent.iterdir()
               if p.suffix in (".py",".pkl",".pickle")}}
    Path(sys.argv[2]).with_name("precision-runtime.json").write_text(json.dumps(runtime,indent=2)+"\n")
