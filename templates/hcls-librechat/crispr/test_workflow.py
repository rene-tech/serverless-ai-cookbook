"""Independent sequence truth and actual upstream runtime checks, no customer inputs."""
import csv
import importlib.util
import json
from pathlib import Path
import random
import re
import shutil

import pytest

SKILL = next((p/"skills/scientific-ai/crispr-workflows/scripts" for p in Path(__file__).resolve().parents
              if (p/"skills/scientific-ai/crispr-workflows/scripts").is_dir()),
             Path("/app/skill/crispr-workflows/scripts"))


def load(name):
    spec=importlib.util.spec_from_file_location(name, SKILL/(name+".py"))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


workflow=load("workflow"); examples=load("make_examples")


@pytest.fixture
def data(tmp_path):
    root=tmp_path/"input"; examples.create(root); return root


@pytest.mark.parametrize("seed",range(30))
@pytest.mark.parametrize("nuclease",["SpCas9","AsCas12a"])
def test_all_positions_and_strands_against_independent_window_scan(seed,nuclease):
    rng=random.Random(seed); seq="".join(rng.choices("ACGT",k=1000))
    size=20 if nuclease=="SpCas9" else 23
    rc=lambda s:s.translate(str.maketrans("ACGT","TGCA"))[::-1]
    expected=set()
    for pos in range(len(seq)-size+1):
        for strand in "+-":
            if nuclease=="SpCas9":
                a,b=(pos+size,pos+size+3) if strand=="+" else (pos-3,pos)
            else:
                a,b=(pos-4,pos) if strand=="+" else (pos+size,pos+size+4)
            if a<0 or b>len(seq):continue
            pam=seq[a:b] if strand=="+" else rc(seq[a:b])
            match=(len(pam)==3 and pam[1:]=="GG") if nuclease=="SpCas9" else (pam[:3]=="TTT" and pam[3] in "ACG")
            if match:
                spacer=seq[pos:pos+size] if strand=="+" else rc(seq[pos:pos+size])
                expected.add((pos,pos+size,strand,spacer,pam,a,b))
    actual={(r["start0"],r["end0"],r["strand"],r["spacer"],r["pam"],r["pam_start0"],r["pam_end0"])
            for r in workflow.candidates({"locus":seq},nuclease)}
    assert actual==expected


def test_ruleset3_public_upstream_reference_values():
    from rs3.seq import predict_seq
    actual=predict_seq(["GACGAAAGCGACAACGCGTTCATCCGGGCA","AGAAAACACTAGCATCCCCACCCGCGGACT"],sequence_tracr="Hsu2013")
    assert actual==pytest.approx([-0.90030944,1.11451622],abs=1e-7)


def test_examples_ref_allele_matches_fasta(data):
    seq=next(iter(workflow.fasta(data/"target.fa").values()))
    row=next(csv.DictReader((data/"variants.csv").open()))["SEQ"]
    assert row.replace("(C/T)","C")==seq


def test_bowtie_complete_site_output_against_bruteforce(data,tmp_path):
    require_bowtie()
    spec=json.loads((data/"guides.json").read_text())
    spec.update(fasta=str(data/"target.fa"),reference_fasta=str(data/"reference.fa"),score=False)
    tables,_=workflow.guides(spec,tmp_path)
    refs=workflow.fasta(data/"reference.fa")
    expected=set()
    for row in tables["guides"]:
        for site in workflow.candidates(refs,"SpCas9"):
            mismatches=sum(a!=b for a,b in zip(row["spacer"],site["spacer"]))
            if mismatches<=3:
                expected.add((row["guide_id"],site["record"],site["start0"],site["strand"],mismatches))
    actual={(r["guide_id"],r["record"],r["start0"],r["strand"],r["mismatches"]) for r in tables["reference-alignments"]}
    assert actual==expected
    assert any(r[1]=="synthetic-near-match" for r in actual)


def require_bowtie():
    assert shutil.which("bowtie"), "Actual Bowtie runtime is required, not a skipped acceptance test"


@pytest.mark.parametrize("case",["guides","base","prime","primers","select","amplicon-qc"])
def test_real_end_to_end(data,tmp_path,case):
    require_bowtie()
    output=tmp_path/("result-"+case)
    result=workflow.run(data/(case+".json"),output)
    assert result["status"]=="complete"
    assert sum(result["tables"].values())>0
    saved=json.loads((output/"report.json").read_text())
    assert saved["schema"]=="scientific-ai/crispr-report/v1"
    assert saved["inputs"]["request"]["sha256"]==workflow.digest(data/(case+".json"))
    for item in saved["artifacts"]:assert workflow.digest(output/item["file"])==item["sha256"]
    assert "<table>" in (output/"report.html").read_text()
    with pytest.raises(ValueError,match="Output directory exists"):
        workflow.run(data/(case+".json"),output)
    if case=="amplicon-qc":
        row=next(csv.DictReader((output/"read-qc.csv").open()))
        assert row==dict(reads="11",low_quality="0",unmapped="0",reference_exact="8",nonreference_aligned="3")
    if case=="select":
        assert [x["id"] for x in csv.DictReader((output/"selected-guides.csv").open())]==["synthetic-25","synthetic-23","synthetic-21"]
    if case in ("base","prime"):
        for row in csv.DictReader((output/"designs.csv").open()):
            # Check native upstream coordinate and U6-G convention independently.
            wt=row["wt_w_context"]
            oriented=wt if row["PAM_strand"]=="+" else workflow.rc(wt)
            pam_start=int(row["PAM_start"])
            if row["PAM_strand"]=="-":pam_start=len(wt)-pam_start
            assert row["Protospacer"]=="G"+oriented[pam_start-20:pam_start]
            if case=="prime":
                assert len(row["PBS"])==int(row["PBS_length"])
                assert len(row["RTT"])==int(row["RTT_length"])
                assert row["RTT_PBS"]==row["RTT"]+row["PBS"]


def test_fifty_independent_table_queries(data,tmp_path):
    original=list(csv.DictReader((data/"guides.csv").open()))
    for i in range(50):
        lo=i*10; hi=lo+250; gene="DEMO1" if i%2 else "DEMO2"; top=1+i%7
        expected=sorted((r for r in original if r["gene"]==gene and lo<=int(r["position"])<=hi),
                        key=lambda r:float(r["score"]),reverse=True)[:top]
        tables,_=workflow.select(dict(table=str(data/"guides.csv"),equals={"gene":gene},between={"position":[lo,hi]},
             order_by=[dict(column="score",ascending=False)],top=top),tmp_path)
        assert [r["id"] for r in tables["selected-guides"]]==[r["id"] for r in expected]


def test_empty_primer_design_is_not_mistaken_for_success_from_diagnostics(tmp_path):
    (tmp_path/"low-complexity.fa").write_text(">synthetic\n"+"A"*800+"\n")
    request=tmp_path/"request.json"
    request.write_text(json.dumps(dict(workflow="primers",species="synthetic",assembly="demo",
                                     fasta="low-complexity.fa",target=[200,30])))
    result=workflow.run(request,tmp_path/"out")
    assert result["status"]=="no_candidates"
    assert result["tables"]["primer-pairs"]==0
    assert result["tables"]["primer3-diagnostics"]>0


def test_errors_are_specific_and_no_fake_success(data,tmp_path):
    with pytest.raises(ValueError,match="explicit region"):
        workflow.guides(dict(fasta=str(data/"target.fa"),modality="activation"),tmp_path)
    with pytest.raises(ValueError,match="Unknown filter column"):
        workflow.select(dict(table=str(data/"guides.csv"),equals={"invented":1}),tmp_path)
    with pytest.raises(ValueError,match="full_length_trimmed"):
        workflow.amplicons(dict(fasta=str(data/"amplicon.fa"),fastq=str(data/"reads.fastq")),tmp_path)
    invalid=tmp_path/"bad.json"; invalid.write_text(json.dumps(dict(workflow="guides",species="synthetic",assembly="demo",bogus=True)))
    with pytest.raises(ValueError,match="Unknown request field"):
        workflow.run(invalid,tmp_path/"never-created")
    assert not (tmp_path/"never-created").exists()


def test_html_escapes_user_fields(tmp_path):
    workflow.write_report(tmp_path,dict(workflow="<script>alert(1)</script>",status="complete",limitations=["<img onerror=x>"],
                          inputs={},software={},elapsed_seconds=1),{"input":[{"sequence":"<script>x</script>"}]})
    text=(tmp_path/"report.html").read_text()
    assert "<script>" not in text and "&lt;script&gt;" in text
