import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { before, after, test } from 'node:test';
import { chromium, webkit } from 'playwright';
import ts from 'typescript';

const require = createRequire(import.meta.url);
let browser;
before(async () => { browser = await (process.env.TEST_BROWSER === 'webkit' ? webkit : chromium).launch(); });
after(async () => { await browser?.close(); });
async function mount(name, props) {
  const page = await browser.newPage();
  await page.setContent('<div id="root"></div>');
  await page.addScriptTag({ path: require.resolve('./node_modules/react/umd/react.development.js') });
  await page.addScriptTag({ path: require.resolve('./node_modules/react-dom/umd/react-dom.development.js') });
  await page.addScriptTag({ content: `
    window.calls = []; window.pending = []; window.revoked = [];
    const revoke = URL.revokeObjectURL; URL.revokeObjectURL = value => { revoked.push(value); revoke(value); };
    window.dependencies = {
      react: React,
      'react-router-dom': { Link: ({to, ...props}) => React.createElement('a', {href:to,...props}) },
      '@librechat/client': { Button: ({variant, ...props}) => React.createElement('button', props), Input: props => React.createElement('input', props) },
      'librechat-data-provider': { request: Object.fromEntries(['get','post','getResponse'].map(method => [method, (url, body) => {
        calls.push({method,url,body}); return new Promise((resolve,reject)=>pending.push({resolve,reject}));
      }])) },
    };` });
  for (const file of ['ScientificResult', name].filter((v,i,a)=>a.indexOf(v)===i)) {
    const code = ts.transpileModule(readFileSync(new URL(`../demos/${file}.tsx`, import.meta.url), 'utf8'), {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React },
    }).outputText;
    await page.addScriptTag({ content: `{const module={exports:{}};const exports=module.exports; const require=name=>dependencies[name];${code}\n dependencies['./${file}']=module.exports;}` });
  }
  await page.addScriptTag({ content: `window.root=ReactDOM.createRoot(document.getElementById('root'));root.render(React.createElement(dependencies['./${name}'].default,${JSON.stringify(props)}));` });
  return page;
}
const contract = { operations: ['simulate'], service_classes: ['customer-batch'], entries: [{name:'scenarios',compression:'none'}],
  parameters: {properties: {episodes:{type:'integer',minimum:1,default:1}, physics:{enum:[null,'physx'],default:null}}} };
const draft = {parameters:{episodes:1,physics:null},arguments:{source:'/workspace/scenarios.json',entry_name:'scenarios',operation:'simulate',service_class:'customer-batch',compression:'none'},preflight_sha256:'checked-hash',checks:['Scenarios checked'],source_sha256:'source-hash',size_bytes:40};

test('form restores exact checked fields and resumes a lost response using the same identity', async () => {
  const requestId = '12345678-1234-1234-1234-123456789abc';
  const page = await mount('ScientificAppForm', {model:'isaac-healthcare',requestId});
  try {
    await page.waitForFunction(()=>pending.length===2);
    await page.evaluate(({contract,draft})=>{pending.shift().resolve(contract);pending.shift().resolve({draft});},{contract,draft});
    await page.getByRole('button',{name:'Submit checked request'}).waitFor();
    assert.equal(await page.getByLabel('physics',{exact:false}).inputValue(),'null');
    await page.getByLabel('episodes',{exact:false}).fill('2');
    assert.equal(await page.getByRole('button',{name:'Submit checked request'}).isDisabled(),true);
    await page.getByRole('button',{name:'Reconnect',exact:true}).click();
    await page.evaluate(draft=>pending.shift().resolve({draft}),draft);
    await page.waitForFunction(()=>document.querySelector('input[type=number]').value==='1');
    await page.getByRole('button',{name:'Submit checked request'}).click();
    await page.evaluate(()=>pending.shift().reject(new Error('Connection lost')));
    await page.getByRole('alert').waitFor();
    assert.equal(await page.getByRole('button',{name:'Submit checked request'}).isDisabled(),true);
    await page.getByRole('button',{name:'Reconnect',exact:true}).click();
    await page.evaluate(draft=>pending.shift().resolve({draft,intent:true}),draft);
    await page.getByRole('button',{name:'Resume saved request'}).click();
    await page.evaluate(()=>pending.shift().resolve({progress_url:'/demos?tab=runs&workflow=saved'}));
    await page.getByRole('link',{name:'Open the existing workflow in Runs'}).waitFor();
    const posts = await page.evaluate(()=>calls.filter(c=>c.method==='post'));
    assert.equal(posts.length,2);
    assert.deepEqual(posts[0].body,posts[1].body);
    assert.deepEqual(posts[0].body,{request_id:requestId,preflight_sha256:'checked-hash'});
  } finally { await page.close(); }
});

test('result displays zero foreground and false task outcome, with JSON collapsed', async () => {
  const page=await mount('ScientificResult',{value:{result:{status:'succeeded',validation:{foreground_voxels:0},task_complete:false},workspace_file:{workspace_url:'/demos?tab=workspace&path=run&file=result.json'}}});
  try {
    assert.equal(await page.locator('dd').allTextContents().then(a=>a.includes('0')&&a.includes('false')),true);
    assert.equal(await page.locator('details').getAttribute('open'),null);
    assert.equal(await page.getByRole('link',{name:'Open retained result file'}).count(),1);
  } finally { await page.close(); }
});

test('video viewer fetches only on demand and releases object URL on close', async () => {
  const page=await mount('ScientificArtifactViewer',{path:'annotated.mp4'});
  try {
    assert.equal(await page.evaluate(()=>calls.length),0);
    await page.getByRole('button',{name:'Inspect artifact'}).click();
    assert.equal(await page.evaluate(()=>calls.length),0);
    await page.getByRole('button',{name:'Load selected preview'}).click();
    await page.evaluate(()=>pending.shift().resolve({kind:'video',path:'annotated.mp4',notice:'Recorded annotated pixels only.'}));
    await page.waitForFunction(()=>pending.length===1);
    await page.evaluate(()=>pending.shift().resolve({data:new Blob(['fixture'],{type:'video/mp4'})}));
    await page.locator('video').waitFor();
    await page.getByRole('button',{name:'Close preview'}).click();
    assert.equal(await page.locator('video').count(),0);
    assert.equal(await page.evaluate(()=>revoked.length),1);
    assert.equal(await page.evaluate(()=>calls.some(c=>c.url.endsWith('/submit'))),false);
  } finally { await page.close(); }
});

test('closing an in-flight image preview discards its late response', async () => {
  const page=await mount('ScientificArtifactViewer',{path:'ct.nii.gz'});
  try {
    await page.getByRole('button',{name:'Inspect artifact'}).click();
    await page.getByRole('button',{name:'Load selected preview'}).click();
    await page.getByRole('button',{name:'Close preview'}).click();
    await page.evaluate(()=>pending.shift().resolve({kind:'ct',image:'data:image/png;base64,unused'}));
    assert.equal(await page.locator('img').count(),0);
  } finally { await page.close(); }
});
