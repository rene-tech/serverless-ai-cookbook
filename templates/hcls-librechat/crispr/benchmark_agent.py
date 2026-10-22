#!/usr/bin/env python3
"""Matched table-query translation benchmark; NOT the unreleased Gene-editing bench."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
from urllib.request import Request, urlopen


def cases():
    # New independent cases, not CRISPR-GPT prompts or labels.
    for i in range(50):
        gene="DEMO1" if i%2 else "DEMO2"; lo=i*10; hi=lo+250
        ascending=bool(i%3==0); top=1+i%7
        expected={"workflow":"select","species":"synthetic","assembly":"test-v1","table":"guides.csv",
             "equals":{"gene":gene},"between":{"position":[lo,hi]},
             "order_by":[{"column":"score","ascending":ascending}],"top":top}
        prompt=(f"Use my synthetic test-v1 guide table guides.csv. Select gene {gene}, keep position from {lo} through {hi} "
                f"inclusive, then take the {top} {'lowest' if ascending else 'highest'} score rows. "
                "Return only the JSON request for the existing local select operation. Do not execute it.")
        yield {"id":f"library-{i:02d}","prompt":prompt,"expected":expected}


def score(text, expected):
    try:
        if text.startswith("```"):text=text.split("\n",1)[1].rsplit("```",1)[0]
        actual=json.loads(text)
        return actual==expected,actual
    except Exception:
        return False,None


def execute(item, args, key, guidance):
    case,arm,repeat=item
    common=("You are a scientific research assistant. Translate the user's guide-library request to JSON. "
            "Schema: workflow='select', species, assembly, table; equals maps column to literal; between maps "
            'column to inclusive [min,max]; each order_by item has exactly two keys, '
            '"column" (string column name) and "ascending" (boolean). For example: '
            '\"order_by\": [{\"column\": \"score\", \"ascending\": false}]. top is integer. '
            "Known columns: id, gene, position, score. No other keys are needed. Do not invent scores or results.")
    system=common+("\nInstalled workflow guidance:\n"+guidance if arm=="skill" else "")
    body={"model":args.model,"messages":[{"role":"system","content":system},{"role":"user","content":case["prompt"]}],
          "temperature":0.2,"max_tokens":700}
    request=Request(args.base_url.rstrip("/")+"/chat/completions",data=json.dumps(body).encode(),
                    headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    started=time.monotonic(); record={"case":case["id"],"arm":arm,"repeat":repeat,"model":args.model,
         "base_url":args.base_url,"time":datetime.now(timezone.utc).isoformat(),"request":body,
         "request_sha256":hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()}
    try:
        with urlopen(request,timeout=120) as response:answer=json.load(response)
        choice=answer["choices"][0]; content=choice["message"].get("content") or ""
        correct,parsed=score(content,case["expected"])
        record.update(correct=correct and choice["finish_reason"]=="stop",response=answer,parsed=parsed)
    except Exception as exc:
        record.update(correct=False,error=str(exc))
    record["latency_seconds"]=time.monotonic()-started
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",required=True)
    parser.add_argument("--base-url",default="https://api.tokenfactory.nebius.com/v1")
    parser.add_argument("--skill",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--repeats",default=3,type=int)
    parser.add_argument("--workers",default=4,type=int)
    args=parser.parse_args(); key=os.environ["NEBIUS_TOKEN_FACTORY_API_KEY"]
    args.output.mkdir(parents=True,exist_ok=False)
    guidance=args.skill.read_text()
    tasks=[(case,arm,repeat) for repeat in range(args.repeats) for case in cases() for arm in ("baseline","skill")]
    records=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool, (args.output/"results.jsonl").open("w") as out:
        for future in as_completed([pool.submit(execute,item,args,key,guidance) for item in tasks]):
            record=future.result(); records.append(record); out.write(json.dumps(record)+"\n");out.flush()
            if len(records)%25==0:print(json.dumps({"completed":len(records),"total":len(tasks)}),flush=True)
    summary={"description":"Independent exact guide-table request translation, not biological efficacy or a replication of the unpublished CRISPR-GPT benchmark",
             "model":args.model,"repeats":args.repeats,"cases":50,"skill_sha256":hashlib.sha256(guidance.encode()).hexdigest()}
    for arm in ("baseline","skill"):
        rows=[r for r in records if r["arm"]==arm]
        summary[arm]={"n":len(rows),"correct":sum(r["correct"] for r in rows),"errors":sum("error" in r for r in rows),
                      "median_seconds":statistics.median(r["latency_seconds"] for r in rows),
                      "total_tokens":sum(r.get("response",{}).get("usage",{}).get("total_tokens",0) for r in rows)}
    (args.output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n");print(json.dumps(summary))


if __name__=="__main__":main()
