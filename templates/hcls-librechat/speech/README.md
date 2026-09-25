# Clinical speech demo overlay

This is an additive **new-instance** overlay on the operation-polling release
`sha256:81a2f3b54a98299933d487ccca4e9eb3fbea3130257a5a818a83940127429a4d`.
Do not replace, restart, or resize any retained endpoint to deploy it.

## Configuration

Build from the repository root with `templates/hcls-librechat/Dockerfile.clinical-speech`.
Supply `SPEECH_REVISION` as the source commit. The Dockerfile preserves the existing
backend, skills, clinical batch routes, and model/provider selection. It rebuilds
the versioned Scientific AI UI and replaces the actual composer microphone.

| Variable | Meaning |
| --- | --- |
| `SCIENTIFIC_MODELS_API_BASE_URL` | Existing Scientific AI API ending `/v1` |
| `SCIENTIFIC_MODELS_MCP_URL` | Existing hosted MCP URL |
| `SCIENTIFIC_ENGLISH_SPEECH_URL` / `SCIENTIFIC_ENGLISH_SPEECH_API_KEY` | Optional isolated **same English checkpoint** native runtime HTTPS/WSS route and dedicated server bearer. Existing platform route remains default when absent; no runtime failover/replay. |
| `SCIENTIFIC_ENGLISH_SPEECH_UPSTREAM_MODEL` | Isolated native wire ID defaults `nemotron-speech-en-0.6b`; UI and ordinary grant identity remain `nemotron-speech-en-0-6b` |
| `SCIENTIFIC_MEDICAL_SPEECH_URL` | Medical adapter HTTPS or WSS `/v1/audio/stream`; absence hides medical selector |
| `SCIENTIFIC_MEDICAL_SPEECH_HTTP_URL` | Same dedicated endpoint's HTTPS origin, without `/v1`; enables typed agent MCP and direct workspace-byte upload |
| `SCIENTIFIC_MEDICAL_SPEECH_API_KEY` | Server-only adapter bearer, supplied through the deployment secret mechanism |
| `SCIENTIFIC_MEDICAL_SPEECH_MODEL` | Default `nemotron-clinical-en` |
| `SCIENTIFIC_MEDICAL_SPEECH_LABEL` | Public selector label; explicitly mark `PILOT checkpoint` for a pilot deployment, never put secrets here |
| `SCIENTIFIC_SPEECH_JOBS_DIR` | Private local receipts; default `/data/hcls-speech` |
| `NEBIUS_API_KEY` or `CLINICAL_REPORT_API_KEY` | Separate server-side Token Factory credential for existing reviewed-report workflow |
| `CLINICAL_REPORT_BASE_URL` | Optional dedicated OpenAI-compatible HTTPS `/v1` endpoint, e.g. self-hosted Fastino; requires its own `CLINICAL_REPORT_API_KEY` |
| `CLINICAL_REPORT_MODEL` | Optional clinical text model ID; defaults to `Qwen/Qwen3-235B-A22B-Instruct-2507` |
| `CLINICAL_REPORT_PROVIDER_LABEL` | Optional public UI label (never put credentials in it) |
| `CLINICAL_REPORT_MAX_OUTPUT_TOKENS` / `CLINICAL_REPORT_CONTEXT_TOKENS` | Custom backend defaults 2048 / 8192; exact authenticated `/tokenize` count before inference |
| `CLINICAL_REPORT_CHUNK_CHARS` / `CLINICAL_REPORT_REVIEW_WORKERS` | Custom backend defaults 3500 / 1; preserve full source with overlapping chunks, not truncation |

Leave `SCIENTIFIC_STUDY_OWNER_MODE` **unset** on a parallel demo instance; do not
claim ownership of another running client's autonomous scientific-study worker.
Keep `SCHEDULES_SINGLE_PROCESS=true` for this one-process deployment; this is a
separate LibreChat mechanism, not Scientific AI worker ownership.
Use a new ordinary tenant/user key and isolated workspace. Keys are saved through
the existing authenticated Apps/Clinical connection panel, not embedded in JS.
The optional clinical provider does not change the user's chat model. A Token
Factory key is never used as fallback for a separately configured endpoint.
Changing provider/model blocks resume of older report jobs until their original
configuration is restored, preventing mixtures of untracked model outputs.
The dedicated `medical-speech` MCP bridge reads only files in the isolated mounted
workspace, transfers WAV bytes over authenticated HTTP, and passes only immutable
artifact references through typed remote tools. It saves exact completed output
bytes and hashes back to Workspace. The primary Scientific AI and Audio Guide
agents gain these tools only when the dedicated endpoint is explicitly configured.
The medical endpoint has demo-level authentication, not platform per-user tenant
isolation. This deployment must remain single-tenant with registration disabled.
The optional isolated English override has the same limitation. It still checks
the ordinary user's English App grant, never sends that key to the dedicated
runtime, and labels native session IDs separately from durable platform operations.
It overrides **live** speech only; existing batch report model routing is unchanged.

## Paths and guarantees

- The default microphone is `nemotron-speech-en-0-6b`; the optional medical
  Nemotron 3.5 selector is never silently substituted for it.
- Authenticated POST `/api/scientific-demos/speech/tickets` exchanges the logged-in
  user's stored platform key for a one-use, 30-second, origin-bound relay ticket.
  WebSocket `/api/scientific-demos/speech/stream` receives that ticket as its first
  frame, never as a query-string credential. The server supplies upstream bearer
  headers. Medical service authentication is distinct from per-user platform
  authorization and must not be described as tenant-native endpoint attribution.
- The AudioWorklet emits mono, signed little-endian PCM16 at 16 kHz in 100 ms
  frames. It resamples the actual browser rate. The live file button plays a
  recording in real time through the same PCM pipeline; it is not a batch request
  disguised as live output.
- ASR partials replace their segment's prior revision. Finals cannot be demoted
  by later partials. The composer does **not** automatically send dictated text.
- Stop flushes queued audio, sends `input.finish`, and waits for actual completion.
  Cancel/disconnect closes the upstream session, with no invisible replay. Frames,
  buffer backlog, connections, per-user sessions, duration and finalization are
  bounded. Failure leaves visible unverified text, not a fabricated final result.
- Live ASR requests real acoustic word timings. Explicit post-stop speaker
  analysis uploads the exact captured WAV through tenant-scoped artifact/MCP
  helpers and invokes Sortformer. Word/activity interval overlap produces
  anonymous channels; low confidence and simultaneous activity stay marked.
  The reviewer, not the model, assigns clinician/patient roles. No timing is
  invented if the ASR returns no word alignment.
- Speaker jobs retain idempotent inputs/receipts and can resume by `speech_job`
  URL after browser reload. The selected, corrected text is explicitly submitted
  to the existing clinical report flow. Original ASR/timing and speaker receipts
  remain separate from human-edited draft input.
- Completed clinical jobs expose an additive structured SOAP/task-handoff view.
  It copies verified source phrases without another model call, keeps unknown
  objective/assessment sections explicitly undocumented, and never assigns or
  executes a treatment task. Source buttons open exact transcript character spans.
  A separate demo-review acknowledgement binds the user, document hash and time;
  it is not clinical sign-off. Live transcript corrections create new report
  jobs, linked to the original speaker/audio hashes and previous draft, leaving
  earlier outputs unchanged.

## Data handling

Use simulated/de-identified data only. Raw live audio is initially retained in
browser memory, and the relay holds bounded transport frames without payload
logging. The model endpoint still receives audio. Clicking speaker analysis saves
audio/receipts on the demo server and in platform artifacts; clicking report
generation requires a completed speaker job owned by the signed-in user. Its
immutable admission request retains the original browser-captured ASR text,
final segments, acoustic word timings, browser timing observations and audio
hash before edits; these are browser observations, not server-attested clinical
evidence. Missing, pending or foreign sources are rejected. Regeneration must
name the same nonempty speaker job as the prior draft. Ordinary uploaded-text
reports do not require this live-source gate. Draft
generation saves the reviewed transcript in the existing clinical-job store and
sends it to the configured report provider. A public authenticated TLS endpoint
is **not** evidence of private networking, HIPAA compliance, or a PHI retention
agreement. Local endpoint disk state is ephemeral on endpoint stop.

## Tests and qualification

```sh
node --test templates/hcls-librechat/speech/test-relay.cjs templates/hcls-librechat/speech/test-audio.mjs
pytest -q templates/hcls-librechat/speech/test_speaker_finalize.py
# Run test-relay-integration.cjs in the image to use its pinned ws dependency.
```

The deterministic tests cover PCM timing/encoding, revisions, WAV, origin-bound
one-use tickets, target TLS restrictions, live relay events/credential isolation,
and speaker uncertainty. Legacy speech/report tests must also run in the image's
scientific Python environment. These do not qualify actual GPU accuracy, public
WSS ingress, microphone hardware, or a final deployed release. The release owner
must bind two unchanged browser/API/MCP cohorts to exact image/model identities,
including invalid input/cancel/recovery, EN/DE batch, tuned live inference,
speaker attribution, reviewed clinical output, and held-out measurements.
