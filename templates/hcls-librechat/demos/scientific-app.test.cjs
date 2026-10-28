const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
let root;
const originalFetch = global.fetch;
const setup = (async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-app-'));
  process.env.SCIENTIFIC_WORKSPACE = root;
  process.env.SCIENTIFIC_MODELS_API_KEY = 'fixture-key';
  process.env.SCIENTIFIC_CLIENT_PYTHON = process.execPath;
  process.env.SCIENTIFIC_WORKFLOW_VIEW_SCRIPT = path.join(root, 'observer.cjs');
  process.env.SCIENTIFIC_APP_SCRIPT = path.join(root, 'app.cjs');
  await fs.writeFile(process.env.SCIENTIFIC_WORKFLOW_VIEW_SCRIPT, 'console.log(JSON.stringify({engine:{alive:true}}))');
  await fs.writeFile(process.env.SCIENTIFIC_APP_SCRIPT, `let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify({action:process.argv[2],model:process.argv[3],body:JSON.parse(s)})));`);
  return require('./service.cjs');
})();
after(async()=>{global.fetch=originalFetch; if(root) await fs.rm(root,{recursive:true,force:true});});

test('guided requests require original key and live storage authorization before helper execution', async()=>{
  const service=await setup;
  let calls=0;
  global.fetch=async()=>{calls++;return new Response('{}');};
  await assert.rejects(service.appRequest('foreign-key','isaac-healthcare','submit',{}),error=>error.status===403);
  await assert.rejects(service.appRequest('fixture-key','unknown','submit',{}),/Unsupported/);
  assert.equal(calls,0);
  const request={request_id:'saved-id',preflight_sha256:'exact'};
  const result=await service.appRequest('fixture-key','isaac-healthcare','submit',request);
  assert.deepEqual(result,{action:'submit',model:'isaac-healthcare',body:request});
  assert.equal(JSON.stringify(result).includes('fixture-key'),false);
  global.fetch=async()=>new Response('{"detail":"revoked"}',{status:403});
  await assert.rejects(service.appRequest('fixture-key','isaac-healthcare','preview',{}),error=>error.status===403);
});

test('batch result exposes manifest artifacts and verifies selected original before retaining it',async()=>{
  const service=await setup;
  const id='op-fixture';
  const payload=Buffer.from(JSON.stringify({status:'succeeded',model_id:'monai-spleen-ct',validation:{foreground_voxels:0}}));
  const ref=(bytes,artifact_id)=>({artifact_id,compression:'none',media_type:'application/json',size_bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});
  const artifact=ref(payload,'11111111-1111-4111-8111-111111111111');
  const mask=Buffer.from('retained compressed mask fixture');
  const maskRef={...ref(mask,'33333333-3333-4333-8333-333333333333'),compression:'gzip',media_type:'application/x-nifti'};
  const manifest=Buffer.from(JSON.stringify({schema:'fs2-serve.nebius.ai/scientific-artifact-manifest/v1',entries:[{name:'result',semantic_type:'monai-result/v1',artifact},{name:'segmentation',semantic_type:'spleen-segmentation-nifti/v1',artifact:maskRef}]}));
  const manifestRef=ref(manifest,'22222222-2222-4222-8222-222222222222');
  let corrupt=false;
  global.fetch=async url=>{
    if(String(url).endsWith('/result')) return new Response(JSON.stringify({terminal_status:'succeeded',output_manifest:manifestRef}));
    if(String(url).endsWith('/'+id)) return new Response(JSON.stringify({id,status:'succeeded'}));
    if(String(url).includes(manifestRef.artifact_id)) return new Response(manifest);
    if(String(url).includes(maskRef.artifact_id)) return new Response(mask);
    if(String(url).includes(artifact.artifact_id)) return new Response(corrupt?Buffer.from('bad'):payload);
    return new Response('{}');
  };
  const result=await service.operationResult('fixture-key',id);
  assert.equal(result.scientific_summary.validation.foreground_voxels,0);
  assert.equal(result.artifacts[0].retrieve_url,'/api/scientific-demos/runs/op-fixture/artifacts/0');
  const saved=await service.operationArtifact('fixture-key',id,0);
  assert.equal(saved.sha256,artifact.sha256);
  assert.deepEqual(await fs.readFile((await service.workspaceGet('fixture-key',saved.relative_path)).absolute),payload);
  const savedMask=await service.operationArtifact('fixture-key',id,1);
  assert.ok(savedMask.relative_path.endsWith('.nii.gz'));
  corrupt=true;
  await assert.rejects(service.operationArtifact('fixture-key',id,0),/integrity check failed/);
  await assert.rejects(service.operationArtifact('fixture-key',id,2),/absent/);
});
