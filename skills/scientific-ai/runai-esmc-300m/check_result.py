"""Check the synthetic example's scientific outputs after shared-client download."""
import argparse,csv,io,json,math,tarfile
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--workflow',choices=['embed','score-variants','score-sequences','extract-representations','logits','masked-completion'],required=True);p.add_argument('--result-dir',type=Path,required=True);a=p.parse_args()
root=a.result_dir/'data/outputs'/('score'if a.workflow in ['embed','score-variants','score-sequences']else'infer');r=json.loads((root/'result.json').read_text());assert r['model_id']=='esmc-300m'and r['operation']==a.workflow
assert r['checkpoint']=='biohub/ESMC-300M'and r['hf_revision']=='96a2d8d61654ac0c08881be44da6c867686449b9'
if a.workflow=='embed':
 with(root/'index.csv').open()as f:rows=list(csv.DictReader(f))
 assert len(rows)==1 and rows[0]['id']=='synthetic'and int(rows[0]['residues'])==20
 with tarfile.open(root/'embeddings.tar')as tf:
  residue=np.load(io.BytesIO(tf.extractfile(rows[0]['residue_file']).read()),allow_pickle=False);mean=np.load(io.BytesIO(tf.extractfile(rows[0]['mean_file']).read()),allow_pickle=False)
 assert residue.shape==(20,960)and mean.shape==(960,)and np.isfinite(residue).all()and np.isfinite(mean).all()and np.allclose(residue.mean(0),mean,atol=2e-6)
elif a.workflow in ['score-variants','score-sequences']:
 with(root/'scores.csv').open()as f:rows=list(csv.DictReader(f))
 assert len(rows)==(3 if a.workflow=='score-variants'else 1)
 for row in rows:
  total,mean=float(row['score']),float(row['mean_score']);count=int(row['residues_scored']);assert math.isfinite(total)and math.isfinite(mean)and math.isclose(total/count,mean,rel_tol=1e-7,abs_tol=1e-7)
 if a.workflow=='score-variants':assert [x['id']for x in rows]==['identity','single','multi']and abs(float(rows[0]['score']))<1e-7
 else:assert rows[0]['id']=='synthetic'and int(rows[0]['residues_scored'])==20 and float(rows[0]['score'])<=0
else:
 def contained_artifact(name):
  relative=Path(name)
  if relative.is_absolute() or '..' in relative.parts: raise ValueError('Artifact path escapes result directory')
  path=root/relative
  if not path.resolve().is_relative_to(root.resolve()) or any((root/Path(*relative.parts[:n])).is_symlink() for n in range(1,len(relative.parts)+1)):
   raise ValueError('Artifact path escapes result directory or uses a symlink')
  return path
 assert len(r['sequences'])==1 and r['sequences'][0]['sequence_id']=='synthetic'and r['sequences'][0]['length']==20
 with np.load(contained_artifact(r['sequences'][0]['artifact']),allow_pickle=False)as arrays:
  assert all(np.isfinite(arrays[name]).all()for name in arrays.files)
  if a.workflow=='extract-representations':
   for layer in [0,15,30]:
    assert arrays[f'layer_{layer}_per_token'].shape==(20,960)and arrays[f'layer_{layer}_mean'].shape==(960,)and arrays[f'layer_{layer}_bos'].shape==(960,)
    assert np.allclose(arrays[f'layer_{layer}_per_token'].mean(0),arrays[f'layer_{layer}_mean'],atol=2e-6)
  else:
   assert arrays['logits'].shape==(20,64)
   if a.workflow=='masked-completion':
    rows=r['sequences'][0]['completion'];assert [x['position']for x in rows]==[2,5]
    for row in rows:
     logits=arrays['logits'][row['position']-1].astype('float64');prob=np.exp(logits-logits.max());prob/=prob.sum();assert len(row['predictions'])==5
     for item in row['predictions']:assert math.isclose(item['probability'],prob[item['token_id']],rel_tol=1e-5,abs_tol=1e-7)
print(json.dumps({'status':'PASS_SCIENTIFIC_EXAMPLE','model':'esmc-300m','workflow':a.workflow}))
