---
name: runai-isaac-healthcare-interactive
description: Run Isaac for Healthcare scissor teleoperation on Scientific AI with Nextflow and verify the recording.
license: Apache-2.0
---

# Isaac for Healthcare interactive

## Scissor teleoperation

Discover the authorized `isaac-healthcare-interactive` model and its
`scissor-teleop` workflow before starting. The service supplies the simulated
scissors scene. The [versioned request](request.json) uses Isaac for Healthcare
0.9.0, the listed EU-North1 L40S placement, and 600 simulation steps.

Use Nextflow 26.10.7 and Python 3 on a workstation or runner you control.
Set `SCIENTIFIC_AI_SKILLS_DIR` to the absolute installed skills path,
`SCIENTIFIC_AI_URL` to your authorized HTTPS service origin, and
`SCIENTIFIC_AI_TOKEN_FILE` to your rotating bearer file. Set
`SCIENTIFIC_AI_POSIX_ROOT` to an absolute private directory on your POSIX
storage and `SCIENTIFIC_AI_SUBMISSION_KEY` to a unique key for this session.
Use a separate launch directory for each session.

```sh
set -eu
umask 077
mkdir -p "$SCIENTIFIC_AI_POSIX_ROOT/work"
cd "$SCIENTIFIC_AI_POSIX_ROOT"
export NXF_HOME="$PWD/.nextflow-home"
stage="$SCIENTIFIC_AI_SKILLS_DIR/runai-scientific-gateway/nextflow/v1"
nextflow run "$stage/main.nf" \
  --request "$SCIENTIFIC_AI_SKILLS_DIR/runai-isaac-healthcare-interactive/request.json" \
  --service_url "$SCIENTIFIC_AI_URL" --submission_key "$SCIENTIFIC_AI_SUBMISSION_KEY" \
  -work-dir "$PWD/work"
```

Read `sciai-run-id.txt` in the stage work directory while Nextflow waits.
Sign in as the session owner and open **Runs → Open viewer** for that ID.
Complete the episode in the viewer. The stage emits the run ID, verified
manifest, and exactly two files. `data/demos.hdf5` contains the pose and
control recording. `data/recording.json` contains the recording receipt.

Rerun with `-resume` from the same launch directory using the original
request, key and work directory. A completed stage reuses its cached outputs.
After a wrapper interruption the same key reattaches to the active session.
To cancel the session explicitly, supply its stage work-file path to
`python3 "$stage/client.py" cancel-interactive PATH_TO/sciai-run-id.txt`.
