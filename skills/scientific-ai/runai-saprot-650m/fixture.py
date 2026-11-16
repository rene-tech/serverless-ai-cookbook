"""Portable MIT upstream SaProt example and synthetic validation variant; no network."""
import argparse,gzip,hashlib,io,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workflow',required=True,choices=['embed','score-variants','score-positions','position-probabilities','extract-representations','logits','masked-completion','attention-maps']);p.add_argument('--key',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--precision',choices=['float32','float16','bfloat16'],default='float32');p.add_argument('--optional-profile',choices=['none','msa','mask','substitute','combined'],default='none');a=p.parse_args();a.output.mkdir(parents=True)
payloads={'sequences.fasta':b'>native\nM#EvVpQpL#VyQdYaKv\n>variation\nApCpDpEpFpGpHpIp\n'}
payloads['variants.csv']=b'id,sequence_id,mutations\nnative-single,native,M1A\nnative-multi,native,M1A:E2D\nnative-self,native,V3V\nnative-distant,native,Q4A:K9G\nvariation-single,variation,A1V\n'
parameters={'embed': {'cpu_threads': 4}, 'score-variants': {'cpu_threads': 4}, 'score-positions': {'cpu_threads': 4, 'positions': [1, 4]}, 'position-probabilities': {'cpu_threads': 4, 'positions': [1, 4]}, 'extract-representations': {'cpu_threads': 4, 'masked_positions': [{'sequence_id': 'native', 'positions': [1, 4]}, {'sequence_id': 'variation', 'positions': [2]}], 'layers': [0, 1, 33], 'include_special_tokens': True}, 'logits': {'cpu_threads': 4, 'masked_positions': [{'sequence_id': 'native', 'positions': [1, 4]}, {'sequence_id': 'variation', 'positions': [2]}]}, 'masked-completion': {'cpu_threads': 4, 'masked_positions': [{'sequence_id': 'native', 'positions': [1, 4]}, {'sequence_id': 'variation', 'positions': [2]}]}, 'attention-maps': {'cpu_threads': 4, 'masked_positions': [{'sequence_id': 'native', 'positions': [1, 4]}, {'sequence_id': 'variation', 'positions': [2]}], 'layers': [1, 33], 'include_special_tokens': True, 'heads': [0, 19]}}[a.workflow]
parameters['precision']=a.precision
if a.optional_profile!='none':
 if a.workflow!='score-variants':p.error('--optional-profile requires --workflow score-variants')
 if a.optional_profile in {'msa','combined'}:
  rows=[]
  for name,length in [('native',9),('variation',8)]:rows.append({'DMS_id':name,'MSA_start':0,'MSA_end':length,'MSA_log_prior':[[round((position+1)*.01+column*.001,6)for column in range(25)]for position in range(length)]})
  payloads['msa-priors.jsonl']=''.join(json.dumps(row,allow_nan=False)+'\n'for row in rows).encode();parameters['msa_prior_file']='msa-priors.jsonl'
 if a.optional_profile in {'mask','combined'}:parameters['structure_mask_rate']=.25
 if a.optional_profile in {'substitute','combined'}:parameters['structure_substitute_rate']=.25
 if a.optional_profile in {'mask','substitute','combined'}:parameters['structure_seed']=123456789
archive=a.output/'input.tar.gz'
with archive.open('xb')as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0)as compressed,tarfile.open(fileobj=compressed,mode='w|')as stream:
 for name,data in payloads.items():
  item=tarfile.TarInfo(name);item.size=len(data);item.mode=0o444;item.mtime=0;stream.addfile(item,io.BytesIO(data))
ref={'name':'input.tar.gz','key':a.key,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'size_bytes':archive.stat().st_size}
for name,value in [('parameters.json',parameters),('input-reference.json',ref)]:(a.output/name).write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps({'workflow':a.workflow,'parameters':parameters,'input':ref}))
