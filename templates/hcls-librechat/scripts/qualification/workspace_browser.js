async (page) => {
  // Run via playwright-cli run-code, after an authenticated QA UI snapshot.
  // No customer key and no scientific model requests. Fixtures are synthetic.
  const root = '/home/tux/secure-handoff/fs2-workspace-files-20261008';
  const names = ['structure.cif', 'structure.mmcif', 'opaque.custom-format', 'NO_EXTENSION', 'empty.unusual', 'Molekül-α.dat', 'audio-test.wav'];
  const posts = [], failures = [];
  const request = req => { if (req.method() === 'POST') posts.push(new URL(req.url()).pathname); };
  const response = res => { if (res.status() >= 500) failures.push({status: res.status(), path: new URL(res.url()).pathname}); };
  page.on('request', request); page.on('response', response);
  try {
    await page.goto(new URL('/c/new', page.url()).href);
    await page.getByRole('button', {name: 'Attach File Options', exact: true}).click();
    await page.getByRole('menuitem', {name: 'Upload file', exact: true}).waitFor();
    await page.keyboard.press('Escape');
    // playwright-cli yields on native chooser dialogs; set the already-probed
    // input directly for a repeatable multi-step cohort without a modal yield.
    const input = page.getByLabel('Upload file to workspace', {exact: true});
    if (await input.getAttribute('accept')) throw new Error('A file-type allowlist returned');
    await input.setInputFiles(names.map(name => root + '/fixtures/' + name));
    const send = page.getByRole('button', {name: 'Send message', exact: true});
    for (let i = 0; i < 50 && !(await send.isEnabled()); i++) await page.waitForTimeout(1000);
    if (!(await send.isEnabled())) throw new Error('Uploads failed or remained pending');
    if (await page.getByRole('alert').count()) throw new Error('Upload UI shows an error');
    await send.click();
    await page.waitForURL(/\/c\/[0-9a-f-]{36}/);
    const chat = new URL(page.url()).pathname.split('/').pop();
    await page.getByRole('button', {name: 'Download structure.cif', exact: true}).waitFor();
    for (const name of names.filter(name => !name.endsWith('.wav'))) {
      const waiting = page.waitForEvent('download');
      await page.getByRole('button', {name: 'Download ' + name, exact: true}).click();
      const download = await waiting;
      if (download.suggestedFilename() !== name) throw new Error('Filename changed');
      await download.saveAs(root + '/browser-downloads/' + chat + '/' + name);
    }
    const audio = await page.getByLabel('Play audio-test.wav', {exact: true}).evaluate(async element => {
      await element.play(); await new Promise(resolve => setTimeout(resolve, 250));
      const result = {duration: element.duration, position: element.currentTime}; element.pause(); return result;
    });
    if (audio.duration !== 1 || audio.position <= 0) throw new Error('Audio did not play');
    await page.reload();
    await page.getByRole('button', {name: 'Download structure.cif', exact: true}).waitFor();
    if (await page.getByRole('button', {name: /^Download /}).count() !== 6) throw new Error('History lost attachments');
    if (await page.getByRole('region', {name: 'Workspace attachments'}).count()) throw new Error('Sent uploads reappeared as drafts');
    if (posts.some(path => /^\/api\/(ask|agents\/chat)(\/|$)/.test(path))) throw new Error('File-only Send called a model');
    if (failures.length) throw new Error('Unexpected HTTP server errors: ' + JSON.stringify(failures));
    return {chat, upload_count: 7, verified_download_count: 6, audio, restored_history: true,
      file_only_inference_calls: 0, post_routes: posts, http_5xx: failures, candidate: 'workspace-20261008-r3'};
  } finally { page.off('request', request); page.off('response', response); }
}
