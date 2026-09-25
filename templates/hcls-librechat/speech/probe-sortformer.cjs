/* Explicit bounded public-path probe; never invoked by unit tests or image build. */
const fs = require('node:fs/promises');
const crypto = require('node:crypto');
const WebSocket = require('/app/node_modules/ws');
async function main() {
  const [keyFile, fixtureFile, outputFile] = process.argv.slice(2);
  if (!keyFile || !fixtureFile || !outputFile) throw new Error('Supply mounted key, approved synthetic WAV and new receipt path');
  const model = 'diar-streaming-sortformer-4spk-v2-1', origin = 'https://89.169.99.188';
  const key = (await fs.readFile(keyFile, 'utf8')).trim();
  const file = await fs.readFile(fixtureFile);
  if (file.toString('ascii', 0, 4) !== 'RIFF' || file.toString('ascii', 36, 40) !== 'data' || file.readUInt32LE(24) !== 16000 || file.readUInt16LE(22) !== 1) throw new Error('Expected canonical mono16k WAV');
  const audio = file.subarray(44, 44 + 12 * 32000);
  const headers = { Authorization: `Bearer ${key}` };
  const catalog = await (await fetch(origin + '/v1/models', { headers })).json();
  const discovered = catalog.data.find(item => item.id === model);
  if (!discovered) throw new Error('Ordinary caller has no Sortformer grant');
  const events = [], started = new Date().toISOString();
  let operation, ready, finishAt, timer, sending;
  const ws = new WebSocket(origin.replace('https:', 'wss:') + '/v1/voice/stream', { headers, maxPayload: 1024 * 1024 });
  await new Promise((resolve, reject) => {
    timer = setTimeout(() => reject(new Error('Bounded probe timeout')), 75000);
    ws.on('error', () => reject(new Error('Voice websocket unavailable')));
    ws.on('close', () => reject(new Error('Voice closed before terminal success')));
    ws.on('open', () => ws.send(JSON.stringify({ type: 'session.start', model, audio: { encoding: 'pcm_s16le', sample_rate_hz: 16000, channels: 1 } })));
    ws.on('message', data => {
      const e = JSON.parse(data); if (e.operation_id) operation = e.operation_id;
      events.push({ type: e.type, at: new Date().toISOString(), ...(e.type === 'speaker.activity' ? { start_seconds: e.start_seconds, frames: e.probabilities.length } : {}) });
      if (e.type === 'error') reject(new Error(`Public stream rejected: ${e.code}`));
      if (e.type === 'session.ready' && !ready) {
        ready = new Date().toISOString(); let offset = 0;
        sending = setInterval(() => {
          if (offset >= audio.length) { clearInterval(sending); finishAt = new Date().toISOString(); ws.send('{"type":"session.finish"}'); return; }
          ws.send(audio.subarray(offset, offset + 3200)); offset += 3200;
        }, 100);
      }
      if (e.type === 'session.done') resolve();
    });
  }).finally(() => { clearTimeout(timer); clearInterval(sending); if (ws.readyState === WebSocket.OPEN) { ws.send('{"type":"session.cancel"}'); ws.close(); } else ws.terminate(); });
  const statusResponse = await fetch(`${origin}/v1/operations/${operation}`, { headers });
  const resultResponse = await fetch(`${origin}/v1/operations/${operation}/result`, { headers });
  const status = await statusResponse.json(), result = await resultResponse.json();
  const receipt = { schema: 'clinical-speech/sortformer-public-stream-probe/v1', started_at: started, completed_at: new Date().toISOString(),
    qualification: 'One bounded existing-principal public Sortformer transport probe; not paired-client, clinical speaker accuracy or final release acceptance.',
    model: discovered, operation_id: operation, status_http: statusResponse.status, result_http: resultResponse.status,
    operation: status, result_sha256: crypto.createHash('sha256').update(JSON.stringify(result)).digest('hex'),
    result_model: result.model, result_audio_seconds: result.audio_seconds, result_event_count: result.events?.length,
    input_pcm_sha256: crypto.createHash('sha256').update(audio).digest('hex'), input_seconds: audio.length / 32000,
    ready_at: ready, input_end_at: finishAt, event_metadata: events,
    activity_before_input_end: events.some(e => e.type === 'speaker.activity' && e.at < finishAt) };
  await fs.writeFile(outputFile, JSON.stringify(receipt, null, 2), { flag: 'wx', mode: 0o600 });
  console.log(JSON.stringify({ operation, status: status.status || status.operation?.status, result_fields: Object.keys(result), activity_before_input_end: receipt.activity_before_input_end, receipt: outputFile }));
}
main().catch(error => { console.error(JSON.stringify({ error: error.message })); process.exitCode = 1; });
