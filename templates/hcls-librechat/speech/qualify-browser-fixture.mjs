// Requires the loopback browser-fixture.cjs and an already opened CLI session.
import fs from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
const [session, output, configuration] = process.argv.slice(2);
const shared = configuration === 'platform';
if (configuration && !shared) throw new Error('Unknown fixture configuration');
if (!/^[a-z0-9-]+$/.test(session || '') || !output) throw new Error('Supply session and new receipt path');
const run = code => JSON.parse(execFileSync('bash', ['/home/tux/.codex/skills/playwright/scripts/playwright_cli.sh', `-s=${session}`, '--raw', 'run-code', code], { encoding: 'utf8', timeout: 30000 }));
const results = [];
const fixtureFile = output + '.wav';
const pcm = Buffer.alloc(44 + 38400); pcm.write('RIFF'); pcm.writeUInt32LE(36 + 38400, 4); pcm.write('WAVEfmt ', 8);
pcm.writeUInt32LE(16, 16); pcm.writeUInt16LE(1, 20); pcm.writeUInt16LE(1, 22); pcm.writeUInt32LE(16000, 24);
pcm.writeUInt32LE(32000, 28); pcm.writeUInt16LE(2, 32); pcm.writeUInt16LE(16, 34); pcm.write('data', 36); pcm.writeUInt32LE(38400, 40);
await fs.writeFile(fixtureFile, pcm, { flag: 'wx', mode: 0o600 });
for (const [mode, scenario, compact, input] of [
  ['english', 'success', false, 'microphone'], ['medical', 'success', false, 'microphone'],
  ['medical-speakers', 'success', false, 'microphone'], ['medical-speakers', 'success', true, 'microphone'],
  ['medical-speakers', 'cancel', false, 'microphone'], ['medical-speakers', 'diar-failure', false, 'microphone'],
  ['medical-speakers', 'missing-words', false, 'microphone'], ['medical-speakers', 'success', false, 'file'],
]) {
  const result = run(`async page => {
    if (!page.url().startsWith('http://127.0.0.1:4420/')) throw new Error('Loopback fixture only');
    await page.request.post('http://127.0.0.1:4420/fixture/scenario', {data:{scenario:${JSON.stringify(scenario)}}});
    await page.goto('http://127.0.0.1:4420/${compact ? 'compact' : ''}');
    const select=page.getByRole('combobox',{name:'Speech model',exact:true});
    await select.locator('option[value="medical-speakers"]').waitFor({state:'attached'});
    const defaultMode=await select.inputValue();
    const choices=await select.locator('option').evaluateAll(options=>options.map(o=>o.value));
    const before=await (await page.request.get('http://127.0.0.1:4420/fixture/evidence')).json();
    await select.selectOption(${JSON.stringify(mode)});
    await page.evaluate(()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async options=>{const stream=await original(options);window.fixtureTrack=stream.getAudioTracks()[0];return stream;};});
    ${input === 'file' ? `await page.getByLabel('Play a recorded consultation through the live pipeline',{exact:true}).setInputFiles(${JSON.stringify(fixtureFile)});await page.getByRole('button',{name:'Play and transcribe live',exact:true}).click();` : `await page.getByRole('button',{name:'Start Nemotron microphone',exact:true}).click();`}
    await page.getByRole('status').filter({hasText:/^listening$/}).waitFor({timeout:8000});
    await page.waitForFunction(()=>{const area=document.querySelector('textarea');return area?.value.includes('aspirin');},{},{timeout:8000});
    const during=${compact ? `await page.getByRole('textbox',{name:'Composer'}).inputValue()` : `await page.getByRole('textbox',{name:'Live transcript for review'}).inputValue()`};
    const liveLabels=${!compact ? `await page.getByLabel('Live anonymous speaker transcript').count()?await page.getByLabel('Live anonymous speaker transcript').innerText():''` : 'during'};
    ${input === 'microphone' ? `await page.getByRole('button',{name:${JSON.stringify(scenario === 'cancel' ? 'Cancel speech' : 'Stop microphone and finalize')},exact:true}).click();` : ''}
    await page.getByRole('status').filter({hasText:/^${scenario === 'cancel' ? 'cancelled' : scenario === 'diar-failure' && !shared ? 'failed' : 'completed'}$/}).waitFor({timeout:8000});
    ${mode === 'medical-speakers' && scenario === 'success' ? compact ? `await page.getByRole('link',{name:/Speaker evidence: completed/}).waitFor({timeout:8000});` : `await page.getByRole('status').filter({hasText:/Speaker job: completed/}).waitFor({timeout:8000});` : ''}
    ${scenario === 'missing-words' ? `await page.getByRole('alert').filter({hasText:/no acoustic word timestamps/}).waitFor({timeout:8000});` : ''}
    ${scenario === 'diar-failure' && shared ? `await page.getByRole('alert').waitFor({timeout:8000});` : ''}
    const after=await (await page.request.get('http://127.0.0.1:4420/fixture/evidence')).json();
    const roleValues=await page.getByRole('combobox',{name:/Speaker [1-4] role/}).evaluateAll(options=>options.map(o=>o.value));
    return {mode:${JSON.stringify(mode)},scenario:${JSON.stringify(scenario)},compact:${compact},input:${JSON.stringify(input)}, defaultMode,choices,during,liveLabels,
      after: ${compact ? `await page.getByRole('textbox',{name:'Composer'}).inputValue()` : `await page.getByRole('textbox',{name:'Live transcript for review'}).inputValue()`},
      alerts:await page.getByRole('alert').allTextContents(),roleValues,
      recordingReleased:await page.evaluate(()=>!window.fixtureTrack||window.fixtureTrack.readyState==='ended'),
      asrModels:after.asr_models.slice(before.asr_models.length),newDiarization:after.stream_starts-before.stream_starts,
      newSpeakerSubmissions:after.speaker_submissions-before.speaker_submissions,newDraftSubmissions:after.draft_submissions-before.draft_submissions,
      newPostStopSubmissions:after.post_stop_submissions-before.post_stop_submissions,
      tracked:after.tracked.slice(before.tracked.length),url:page.url()};
  }`);
  const checks = { default_english: result.defaultMode === 'english', exactly_three_ordered: JSON.stringify(result.choices) === JSON.stringify(['english','medical','medical-speakers']),
    no_auto_draft: result.newDraftSubmissions === 0, recording_released: result.recordingReleased,
    asr_exact: result.asrModels.length === 1 && result.asrModels[0] === (shared ? (mode === 'english' ? 'nemotron-speech-en-0-6b' : 'nemotron-speech-en-medical-0-6b') : (mode === 'english' ? 'nemotron-speech-en-0.6b' : 'nemotron-clinical-en')),
    explicit_diarization_only: result.newDiarization === (!shared && mode === 'medical-speakers' ? 1 : 0),
    one_final_submission: result.newSpeakerSubmissions === (mode === 'medical-speakers' && (scenario === 'success' || shared && scenario === 'diar-failure') ? 1 : 0),
    post_stop_phase: !shared || result.newPostStopSubmissions === (mode === 'medical-speakers' && ['success','diar-failure'].includes(scenario) ? 1 : 0),
    roles_never_inferred: result.roleValues.every(value => value === ''),
    honest_speaker_timing: shared ? !result.liveLabels.includes('Speaker 1') && !result.liveLabels.includes('Speaker 2') : mode !== 'medical-speakers' || scenario === 'missing-words' || result.liveLabels.includes('Speaker 1') && result.liveLabels.includes('Speaker 2'),
    final_speaker_labels: mode !== 'medical-speakers' || scenario !== 'success' || result.after.includes('Speaker 1') && result.after.includes('Speaker 2'),
    composer_prefix_preserved: !compact || result.after.startsWith('Review: '),
    expected_failure_visible: !['missing-words','diar-failure'].includes(scenario) || result.alerts.length > 0,
    no_unexpected_alerts: ['missing-words','diar-failure'].includes(scenario) || result.alerts.length === 0 };
  results.push({ ...result, checks, passed: Object.values(checks).every(Boolean) });
  console.log(JSON.stringify({ mode, scenario, compact, input, passed: results.at(-1).passed }));
}
await fs.writeFile(output, JSON.stringify({ scope: 'Actual LiveSpeech/AudioRecorder and relay, local deterministic backend. Not GPU accuracy, physical microphone, deployed client or qualified winner evidence.', observed_at: new Date().toISOString(), results, passed: results.every(result => result.passed) }, null, 2), { flag: 'wx', mode: 0o600 });
assert.ok(results.every(result => result.passed), 'Browser fixture assertions failed; retained receipt');
