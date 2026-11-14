#!/usr/bin/env python3
"""Prepare verified public RFantibody examples; Python standard library only."""
import argparse,gzip,hashlib,io,json,sys,tarfile,urllib.request
from pathlib import Path
REVISION = '947fd3dde58947b4fa64b38e79b744223974d53a'
FILES = {'framework.pdb': {'path': 'test/rfdiffusion/inputs_for_test/hu-4D5-8_Fv.pdb', 'sha256': 'a25ff0f1699551563f7ffa93958d1ec53c1ddce6ea53f4f5da2b5461e50771f7'}, 'nanobody.pdb': {'path': 'test/rfdiffusion/inputs_for_test/h-NbBCII10.pdb', 'sha256': 'ab444bb19d8391b1b75decd0026e0d9f09affff5a702a6180edc990bbda3095e'}, 'target.pdb': {'path': 'test/rfdiffusion/inputs_for_test/rsv_site3.pdb', 'sha256': '09e1dd02435f6c68a2b95a15dbf970e813f156b7c6a4a540d7613f35c5955423'}, 'structures/ab_des_0.pdb': {'path': 'test/proteinmpnn/inputs_for_test/ab_des_0.pdb', 'sha256': '6250f4e6c9d2caeb13ce18d7df9a24fb9c2f6e795b4c70c21477c0806c04dcc8'}, 'rf2/complex.pdb': {'path': 'test/rf2/inputs_for_test/ab_proteinmpnn_output.pdb', 'sha256': 'bc0ef28dc0ee8f73b78a6ac8b464b18a29a85bc3f75d49e3d4ed6cee53792026'}, 'rf2/targets.json': {'path': 'test/rf2/inputs_for_test/rfab_targets.json', 'sha256': '64db435d3dfd2bd9499a1370177d2cd0a568a42ea04bb352644c30b47d1fb074'}}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',nargs='?',default='input.tar.gz',type=Path)
    parser.add_argument('--multiple-inputs',action='store_true',help='Add two-input MPNN/RF2 examples for explicit input granularity; duplicate public fixtures, not independent scientific candidates.')
    args=parser.parse_args();target=args.output
    if target.exists():raise SystemExit('Refusing to overwrite existing '+str(target))
    members={}
    for name,item in FILES.items():
        url='https://raw.githubusercontent.com/RosettaCommons/RFantibody/'+REVISION+'/'+item['path']
        with urllib.request.urlopen(url,timeout=45) as response:raw=response.read((2<<20)+1)
        if len(raw)>2<<20 or hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise SystemExit('Public scientific fixture integrity mismatch: '+name)
        members[name]=raw
    members['structures.qv']=b'QV_TAG ab_des_0\n'+members['structures/ab_des_0.pdb']
    positive=(Path(__file__).parent/'7Y1B.HLT.pdb').read_bytes()
    if hashlib.sha256(positive).hexdigest()!='f92b9724c323316cc06f63aae301ddca25bfe4276e297e2adfa6ea5750dbb134':
        raise SystemExit('Bundled7Y1B fixture integrity mismatch')
    members['positive7Y1B.pdb']=positive
    if args.multiple_inputs:
        members['structures/ab_des_1.pdb']=members['structures/ab_des_0.pdb']
        members.update({'prediction-structures/z_positive.pdb':positive,'prediction-structures/a_positive.pdb':positive})
    with target.open('xb') as output:
        with gzip.GzipFile(fileobj=output,mode='wb',mtime=0,filename='') as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for name,raw in sorted(members.items()):
                    item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o644;item.mtime=0
                    archive.addfile(item,io.BytesIO(raw))
    print(json.dumps({'file':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'size_bytes':target.stat().st_size,'members':sorted(members)},indent=2))

if __name__=='__main__':main()
