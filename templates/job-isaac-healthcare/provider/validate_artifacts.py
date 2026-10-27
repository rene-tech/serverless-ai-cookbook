"""Audit delivered Isaac artifacts against original inputs; never infer task success from job status."""
import argparse,json,shutil,tarfile,tempfile
from pathlib import Path
import h5py
import numpy as np
from isaac_healthcare_runtime.contract import SOURCE,digest,parameters,scenarios
from isaac_healthcare_runtime.validate import validate_recording

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--input',type=Path,required=True); p.add_argument('--parameters',type=Path,required=True)
p.add_argument('--result',type=Path,required=True); p.add_argument('--archive',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); values=parameters(json.loads(a.parameters.read_bytes())); cases=scenarios(json.loads(a.input.read_bytes())); result=json.loads(a.result.read_bytes())
assert result['schema']=='isaac-healthcare-result/v1' and result['source_revision']==SOURCE
assert result['input_sha256']==digest(a.input) and result['parameters']==values
assert [x['scenario'] for x in result['scenarios']]==cases
assert result['files']['simulation.tar']=={'sha256':digest(a.archive),'size_bytes':a.archive.stat().st_size}
checked=[]
with tempfile.TemporaryDirectory(prefix='isaac-artifact-audit-') as tmp,tarfile.open(a.archive,'r:') as archive:
 names=set()
 for member in archive:
  path=Path(member.name)
  assert member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name not in names
  assert '.operator' not in path.parts and path.name!='simulator.log'
  names.add(member.name)
 assert 'assets.json' in names
 assets=archive.extractfile('assets.json').read()
 import hashlib
 assert hashlib.sha256(assets).hexdigest()==result['materialized_assets_sha256']
 patches=archive.extractfile('upstream-patches.json').read()
 assert hashlib.sha256(patches).hexdigest()==result['upstream_patches_sha256']
 assert json.loads(patches)['schema']=='isaac-healthcare-upstream-patches/v1'
 for index,row in enumerate(result['scenarios']):
  expected=f'scenario-{index:06d}/demos.hdf5'; assert row['recording']==expected
  recording=Path(tmp)/f'{index}.hdf5'
  with archive.extractfile(expected) as src,recording.open('wb') as dst: shutil.copyfileobj(src,dst)
  validated=validate_recording(recording,values)
  for key,value in validated.items(): assert row[key]==value,(index,key)
  motion=[]
  with h5py.File(recording,'r') as hdf:
   for name,demo in hdf['data'].items():
    joints=demo['obs/joint_pos'][()]
    motion.append(float(np.max(np.linalg.norm(joints-joints[0],axis=1))))
    for camera in ('room','wrist'):
     if values['cameras']:
      assert demo[f'obs/{camera}'].shape==(len(joints),480,640,3)
     else: assert camera not in demo['obs']
  log=archive.extractfile(f'scenario-{index:06d}/workflow.log').read().decode()
  assert 'Workflow outcome log from upstream HDF5 metadata and terminal summary.' in log
  checked.append({'scenario':row['scenario'],'task_complete':validated['task_complete'],'samples':validated['samples'],'episodes':validated['episodes'],'joint_motion_l2_max':motion})
assert result['task_complete']==all(x['task_complete'] for x in checked)
report={'validation':'passed','task_complete':result['task_complete'],'source_revision':SOURCE,'input_sha256':digest(a.input),'archive_sha256':digest(a.archive),'scenarios':checked,'note':'Structural/sensor/input integrity is distinct from upstream task success; motion values are observations, not fixture eligibility.'}
a.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n'); print(json.dumps({'validation':'passed','task_complete':result['task_complete'],'scenarios':len(checked),'report':str(a.output)}))
