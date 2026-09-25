/* Explicit bounded acceptance probe. Uses the retained OLD checkpoint, never a round-2 quality claim. */
const fs = require('node:fs/promises'), path = require('node:path'), os = require('node:os'), http = require('node:http');
const crypto = require('node:crypto'), { once } = require('node:events');
const WebSocket = require('/app/node_modules/ws');
const relay = require('./relay.cjs'), receipts = require('./stream-receipt.cjs');
async function main() {
  const [ordinaryFile, medicalFile, fixtureFile, output] = process.argv.slice(2);
  if (!output) throw new Error('Supply mounted ordinary key, medical auth JSON, approved WAV and NEW receipt file');
  const ordinary = (await fs.readFile(ordinaryFile, 'utf8')).trim(), medical = JSON.parse(await fs.readFile(medicalFile, 'utf8')).AUTH_TOKEN;
  const origin = 'https://89.169.99.188', endpoint = 'https://port8000-em51qrpba49682p.tunnel.applications.eu-north1.nebius.cloud';
  const expected = 'dfef5379788f983a2829b8d350e7eeaeb41d7b42751e88df21885a9d2a10bb15';
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'paired-real-probe-')); process.env.SCIENTIFIC_SPEECH_JOBS_DIR = root;
  const target = { id: 'nemotron-clinical-en', expectedCheckpoint: expected, url: endpoint + '/v1/audio/stream', credential: medical,
    diarization: { id: 'diar-streaming-sortformer-4spk-v2-1', url: origin + '/v1/voice/stream', credential: ordinary } };
  target.modelIdentity = await relay.verifyMedicalIdentity(target);
  const source = await fs.readFile(fixtureFile);
  if (source.toString('ascii', 36, 40) !== 'data' || source.readUInt32LE(24) !== 16000) throw new Error('Canonical16k fixture required');
  const helpers = await import('./speech-state.js');
  const get = async (_key, method, resource) => {
    if (method !== 'GET') throw new Error('Read-only result lookup only');
    const response = await fetch(origin + resource, { headers: { Authorization: `Bearer ${ordinary}` }, signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error('Operation observation failed: HTTP ' + response.status); return response.json();
  };
  const server = http.createServer(), wss = relay.attach(server); server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const results = [], started = new Date().toISOString();
  try {
    for (const cancel of [true, false]) {
      const pcm = source.subarray(44, 44 + (cancel ? 2 : 12) * 32000), events = [], wordSegments = new Map(), segments = new Map(), activity = [];
      const auth = relay.issueTicket('paired-probe-owner', 'https://probe.test', target, medical);
      const client = new WebSocket(`ws://127.0.0.1:${server.address().port}${auth.path}`, { origin: 'https://probe.test' });
      let timer, sender, offset = 0, inputEnd, completion, operation, firstLiveLabels, failure;
      try {
        await new Promise((resolve, reject) => {
          timer = setTimeout(() => reject(new Error('Paired runtime probe timeout')), 60000);
          client.on('error', () => reject(new Error('Local paired probe transport failed')));
          client.on('open', () => client.send(JSON.stringify({ type: 'relay.attach', ticket: auth.ticket })));
          client.on('message', raw => {
            const event = JSON.parse(raw), at = new Date().toISOString();
            events.push({ type: event.type, at, ...(event.code ? { code: event.code } : {}) });
            if (event.diarization_operation_id) operation = event.diarization_operation_id;
            if (event.type === 'session.ready') sender = setInterval(() => {
              if (offset >= pcm.length) { clearInterval(sender); inputEnd = new Date().toISOString(); client.send(JSON.stringify({ type: cancel ? 'session.cancel' : 'input.finish' })); return; }
              client.send(pcm.subarray(offset, offset + 3200)); offset += 3200;
            }, 100);
            if (event.type.startsWith('transcript.')) {
              helpers.transcriptEvent(segments, event);
              if (event.type === 'transcript.final' && event.items) wordSegments.set(String(event.segment_id ?? event.sequence ?? 'current'), helpers.acousticWords(event));
            }
            if (event.type === 'speaker.activity') activity.push(event);
            if (!firstLiveLabels && segments.size && activity.length) {
              const labels = helpers.liveSpeakerTurns(segments, wordSegments, activity).filter(turn => /^speaker_[0-3]/.test(turn.speaker));
              if (labels.length) firstLiveLabels = { at, anonymous_ids: [...new Set(labels.map(turn => turn.speaker))], before_input_end: !inputEnd };
            }
            if (event.type === 'session.error') { failure = event.code; reject(new Error(event.code)); }
            if (event.type === 'session.completed') completion = event;
          });
          client.on('close', () => {
            if (cancel ? events.some(e => e.type === 'session.cancelled') : completion) resolve();
            else reject(new Error('Paired probe closed without expected terminal event'));
          });
        });
      } catch (error) { failure = failure || error.message; }
      finally { clearInterval(sender); clearTimeout(timer); if (client.readyState === WebSocket.OPEN) { client.send('{"type":"session.cancel"}'); client.close(); } else client.terminate(); }
      let observed;
      if (operation) {
        for (let attempt = 0; attempt < 30; attempt++) {
          observed = await get(ordinary, 'GET', `/v1/operations/${operation}`);
          if (['succeeded','cancelled','failed'].includes(observed.status)) break;
          await new Promise(resolve => setTimeout(resolve, 200));
        }
      }
      let retained;
      if (completion) try {
        const header = Buffer.from(source.subarray(0, 44)); header.writeUInt32LE(36 + pcm.length, 4); header.writeUInt32LE(pcm.length, 40);
        retained = await receipts.resolve('paired-probe-owner', completion.speaker_stream_receipt, ordinary, Buffer.concat([header, pcm]), target.id, get,
          async (_key, resource) => Buffer.from(await (await fetch(origin + resource, { headers: { Authorization: `Bearer ${ordinary}` } })).arrayBuffer()));
      } catch (error) { failure = 'Retained result: ' + error.message; }
      const words = [...wordSegments.values()].flat(), turns = helpers.liveSpeakerTurns(segments, wordSegments, activity);
      const result = { mode: cancel ? 'cancel' : 'completed-after-cancel', failure: failure || null,
        input_seconds: pcm.length / 32000, input_pcm_sha256: receipts.hash(pcm), input_end_at: inputEnd,
        operation_id: operation, operation: observed, events, first_live_labels: firstLiveLabels,
        asr_final_segments: [...segments.values()].filter(value => value.final).length,
        acoustic_word_count: words.length, acoustic_word_fields: words[0] ? Object.keys(words[0]) : [],
        exact_native_word_rendering: words.map(word => word.render_text).join('').trim() === [...segments.values()].map(segment => segment.text).join('').trim(),
        final_anonymous_ids: [...new Set(turns.map(turn => turn.speaker))], final_flagged_turns: turns.filter(turn => turn.flag).length,
        retained_same_operation: retained?.receipt.operation_id === operation && retained?.operation.id === operation,
        result_sha256: retained ? receipts.hash(JSON.stringify(retained.result)) : null,
        paired_receipt: retained?.receipt, no_second_diarization_invocation: true };
      result.passed = !failure && (cancel ? observed?.status === 'cancelled' : observed?.status === 'succeeded' && words.length > 0 && firstLiveLabels?.before_input_end && result.retained_same_operation && result.exact_native_word_rendering);
      results.push(result);
      console.log(JSON.stringify({ mode: result.mode, operation, passed: result.passed, failure: result.failure, acoustic_words: words.length, live_labels_before_end: firstLiveLabels?.before_input_end }));
      if (!result.passed) break;
    }
  } finally { for (const client of wss.clients) client.terminate(); wss.close(); await new Promise(resolve => server.close(resolve)); }
  await fs.writeFile(output, JSON.stringify({ scope: 'Actual new paired relay with retained OLD medical checkpoint + existing Sortformer. Not round2 winner or final deployed browser qualification.',
    started_at: started, completed_at: new Date().toISOString(), asr_endpoint: 'aiendpoint-e00sg63cy68pg90nq8', asr_runtime: target.modelIdentity,
    asr_expected_old_checkpoint: expected, source_wav_sha256: receipts.hash(source), results, passed: results.length === 2 && results.every(result => result.passed) }, null, 2), { flag: 'wx', mode: 0o600 });
  if (!results.every(result => result.passed)) process.exitCode = 1;
}
main().catch(error => { console.error(JSON.stringify({ error: error.message })); process.exitCode = 1; });
