"""Portable native MIT context and synthetic inverse-folding example; stdlib only."""
import argparse,gzip,hashlib,io,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--key',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True)
raw=b'>native-partial\n##Ev#pQp##Vy#dYa#v\n>synthetic-all-masked\n#a#p#n#w#r#q#h#g\n';archive=a.output/'input.tar.gz'
with archive.open('xb')as f,gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0)as z,tarfile.open(fileobj=z,mode='w')as t:
 i=tarfile.TarInfo('sequences.fasta');i.size=len(raw);i.mtime=0;t.addfile(i,io.BytesIO(raw))
ref={'name':'input.tar.gz','key':a.key,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'size_bytes':archive.stat().st_size}
for name,value in [('input-reference.json',ref),('parameters.json',{'cpu_threads':4})]:(a.output/name).write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps({'input':ref,'parameters':{'cpu_threads':4}}))
