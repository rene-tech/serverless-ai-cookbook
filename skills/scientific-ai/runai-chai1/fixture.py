#!/usr/bin/env python3
"""Create a reproducible, public/synthetic Chai example with the standard library."""
import argparse,gzip,hashlib,io,json
from pathlib import Path
import tarfile

p=argparse.ArgumentParser();p.add_argument('--workflow',choices=['predict','msa-convert'],default='predict');p.add_argument('--key',required=True,help='Object key in your already authorized bucket');p.add_argument('--output',type=Path,default=Path('prepared'));a=p.parse_args()
if not a.key or a.key.startswith('/')or'..'in a.key.split('/'):p.error('--key must be a relative object key without parent traversal')
if a.workflow=='predict':
 name='input.fasta';raw=b'>protein|name=ubiquitin\nMQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG\n';mode=0o600
 parameters={'seed':42};expected='b1a50848a1aee66d91c1824749e13ce89650ff3aadb40bb08099f2a3444bd569'
else:
 name='hits_uniref90.a3m';raw=b'>query\nACDEFG\n>synthetic insertion homolog\nACdDEFG\n';mode=0o644
 parameters={'a3m_files':[{'path':name,'source_database':'uniref90'}],'insert_keys_for_sources':'uniprot'};expected='1f3425e807bf95fc36aec19919edfcb83f65b6dc138d4f26a6369f18025374fa'
archive=io.BytesIO()
with gzip.GzipFile(filename='',mode='wb',fileobj=archive,mtime=0,compresslevel=9)as compressed:
 with tarfile.open(fileobj=compressed,mode='w',format=tarfile.USTAR_FORMAT)as tar:
  member=tarfile.TarInfo(name);member.size=len(raw);member.mode=mode;member.uid=member.gid=member.mtime=0;member.uname=member.gname='';tar.addfile(member,io.BytesIO(raw))
raw_archive=archive.getvalue();digest=hashlib.sha256(raw_archive).hexdigest();assert digest==expected,'Fixture bytes differ from the documented canonical archive'
a.output.mkdir(parents=True,exist_ok=False);(a.output/'input.tar.gz').write_bytes(raw_archive)
for filename,value in [('parameters.json',parameters),('input-reference.json',{'name':'input.tar.gz','key':a.key,'sha256':digest,'size_bytes':len(raw_archive)})]:
 (a.output/filename).write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps({'workflow':a.workflow,'archive':str(a.output/'input.tar.gz'),'sha256':digest,'size_bytes':len(raw_archive),'upload_required':True}))
