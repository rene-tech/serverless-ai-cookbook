"""Check this bundled two-image SAM2 example after artifact hash verification."""
import argparse,hashlib,io,json,tarfile,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('result',type=Path);p.add_argument('--input',type=Path,default=Path('batch-example-input.tar.gz'));args=p.parse_args()
with tarfile.open(args.input,'r:gz')as t:
 settings=json.load(t.extractfile('settings.json'));media=[t.extractfile(r['media_path']).read()for r in settings['images']]
assert settings['mode']=='batch-image'and settings['batch_operation']=='predict'
members={'manifest.json'};quality=[]
with zipfile.ZipFile(args.result)as z:
 manifest=json.loads(z.read('manifest.json'));assert manifest['tool_version']=='sam2.1-hiera-large-665f8e2a'and manifest['mode']=='batch-image'and manifest['batch_operation']=='predict'and manifest['native_batch_encoder']is True;assert manifest['prediction_options']==settings['prediction_options']and len(manifest['images'])==len(settings['images'])==2
 identities=[]
 for i,(entry,row,raw)in enumerate(zip(manifest['images'],settings['images'],media)):
  rgb=np.asarray(Image.open(io.BytesIO(raw)).convert('RGB'));height,width=rgb.shape[:2];assert entry['image_index']==i and entry['input_sha256']==hashlib.sha256(raw).hexdigest()and(entry['width'],entry['height'])==(width,height);assert[o['object_id']for o in entry['objects']]==row['object_ids'];identities.append({'image_index':i,'input_sha256':entry['input_sha256'],'width':width,'height':height});prefix=f'batch/{i+1:04d}';assert entry['embedding']==prefix+'/image-embedding.npy';members.add(entry['embedding']);embedding=np.load(io.BytesIO(z.read(entry['embedding'])),allow_pickle=False);assert embedding.dtype==np.float32 and embedding.shape==(1,256,64,64)and np.isfinite(embedding).all()and np.linalg.norm(embedding)>0
  labels=np.zeros((height,width),dtype=np.uint16)
  for obj,color in zip(entry['objects'],([54,227,196],[232,113,255])):
   name=prefix+f'/object-{obj["object_id"]}.npz';assert obj['predictions']==name;members.add(name)
   with np.load(io.BytesIO(z.read(name)),allow_pickle=False)as arrays:
    assert set(arrays.files)=={'masks','scores','low_resolution_logits'}
    for key,shape in [('masks',(3,height,width)),('scores',(3,)),('low_resolution_logits',(3,256,256))]:assert arrays[key].shape==shape and arrays[key].dtype==np.float32 and np.isfinite(arrays[key]).all()
    assert np.isin(arrays['masks'],[0.,1.]).all();chosen=int(np.argmax(arrays['scores']));assert obj['preview_candidate']==chosen;mask=arrays['masks'][chosen].astype(bool);labels[mask]=obj['object_id'];truth=np.all(rgb==color,axis=-1);iou=float(np.logical_and(mask,truth).sum())/max(1,int(np.logical_or(mask,truth).sum()));assert iou>=.8;quality.append({'image_index':i,'object_id':obj['object_id'],'known_object_IoU':iou})
  members.update({prefix+'/mask.png',prefix+'/overlay.png'})
  assert np.array_equal(labels,np.asarray(Image.open(io.BytesIO(z.read(prefix+'/mask.png')))))
 assert manifest['input_sha256']==hashlib.sha256(json.dumps(identities,sort_keys=True,separators=(',',':')).encode()).hexdigest();assert set(z.namelist())==members and len(z.namelist())==len(members)and z.testzip()is None
print(json.dumps({'status':'PASS_BUNDLED_SAM2_TWO_IMAGE_NATIVE_BATCH_EXAMPLE','images':2,'objects':3,'scientific_version':'sam2.1-hiera-large-665f8e2a','quality':quality}))
