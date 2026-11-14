"""Prepare a synthetic ESMC fixture/reference; no network or credentials."""
import argparse,gzip,hashlib,io,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workflow',choices=['embed','score-variants','score-sequences','extract-representations','logits','masked-completion','attention-maps'],required=True);p.add_argument('--key',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True)
params={}
if a.workflow=='extract-representations':params={'layers':[0,18,36],'representations':['per-token','mean','bos']}
if a.workflow=='masked-completion':params={'masked_positions':[{'sequence_id':'synthetic','positions':[2,5]}],'top_k':5}
if a.workflow=='attention-maps':params={'layers':[1,18,36],'heads':[0,8,17]}
members={'sequences.fasta':'>synthetic\nACDEFGHIKLMNPQRSTVWY\n'}
if a.workflow=='score-variants':members['variants.csv']='id,sequence_id,mutations\nidentity,synthetic,A1A\nsingle,synthetic,A1G\nmulti,synthetic,A1G:C2A\n'
archive=a.output/'input.tar.gz'
with archive.open('xb')as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0)as gz,tarfile.open(fileobj=gz,mode='w|')as tf:
 for name,value in members.items():
  data=value.encode();m=tarfile.TarInfo(name);m.size=len(data);m.mtime=0;tf.addfile(m,io.BytesIO(data))
reference={'name':'input.tar.gz','key':a.key,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'size_bytes':archive.stat().st_size}
for name,value in [('parameters.json',params),('input-reference.json',reference)]:(a.output/name).write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps({'workflow':a.workflow,'input':reference,'parameters':params}))
