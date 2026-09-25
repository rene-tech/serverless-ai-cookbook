#!/usr/bin/env python3
"""Align actual ASR acoustic word times with anonymous Sortformer activity."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

# Existing durable, tenant-scoped artifact upload and MCP invocation helpers.
sys.path.insert(0, '/opt/bionemo')


def attribute_words(words, events, duration):
    frames = []
    for event in events:
        if event.get('type') != 'speaker.activity':
            continue
        start = float(event.get('start_seconds', 0))
        step = float(event.get('frame_duration_seconds', .08))
        if not math.isfinite(start) or not 0 < step <= 1:
            raise ValueError('Invalid speaker frame times')
        for index, probabilities in enumerate(event.get('probabilities', [])):
            if len(probabilities) != 4 or not all(isinstance(p, (int, float)) and math.isfinite(p) and 0 <= p <= 1 for p in probabilities):
                raise ValueError('Invalid speaker probabilities')
            frames.append((start + index * step, start + (index + 1) * step, probabilities))
    if not frames:
        raise ValueError('No model-produced speaker activity')
    frames.sort(key=lambda frame: frame[0])
    attributed = []
    previous = -1
    cursor = 0
    for word in words:
        start, end = float(word['start_seconds']), float(word['end_seconds'])
        text = word['text']
        if not isinstance(text, str) or not text.strip() or not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= duration + .2 or start < previous:
            raise ValueError('Missing or invalid acoustic word timestamps; no speaker transcript was fabricated')
        previous = start
        while cursor < len(frames) and frames[cursor][1] <= start:
            cursor += 1
        scores, coverage = [0.] * 4, 0.
        for index in range(cursor, len(frames)):
            a, b, probs = frames[index]
            if a >= end:
                break
            overlap = max(0., min(end, b) - max(start, a))
            coverage += overlap
            for i in range(4):
                scores[i] += overlap * probs[i]
        scores = [score / coverage for score in scores] if coverage else scores
        rank = sorted(range(4), key=lambda i: scores[i], reverse=True)
        active = [i for i in rank if scores[i] >= .5]
        if coverage < (end - start) * .5 or scores[rank[0]] < .5 or (len(active) < 2 and scores[rank[0]] - scores[rank[1]] < .1):
            speaker, flag = 'uncertain', 'insufficient_or_ambiguous_activity'
        elif len(active) > 1:
            speaker, flag = '+'.join(f'speaker_{i}' for i in sorted(active)), 'overlap'
        else:
            speaker, flag = f'speaker_{rank[0]}', None
        attributed.append({**word, 'speaker': speaker, 'speaker_probabilities': [round(score, 4) for score in scores], 'flag': flag})
    if not attributed:
        raise ValueError('ASR did not return acoustic word timestamps')
    turns = []
    for word in attributed:
        if turns and turns[-1]['speaker'] == word['speaker'] and word['start_seconds'] - turns[-1]['end_seconds'] < 1.5:
            turns[-1]['text'] += ' ' + word['text'].strip()
            turns[-1]['end_seconds'] = word['end_seconds']
        else:
            turns.append({name: word[name] for name in ('speaker', 'start_seconds', 'end_seconds', 'text', 'flag')})
    return {'words': attributed, 'turns': turns,
            'thresholds': {'active_probability': .5, 'minimum_margin': .1, 'minimum_time_coverage': .5},
            'limitations': ['Anonymous speaker channels are not identities or clinician/patient roles.',
                           'Timing and attribution are model estimates; overlap and uncertainty require review.']}


def main():
    from recording_pipeline import upload_source, invoke, immutable_input, unwrap, file_identity
    from scientific_receipts import load, save
    parser = argparse.ArgumentParser(); parser.add_argument('directory', type=Path); args = parser.parse_args()
    root = args.directory
    source = root / 'input.wav'
    request = load(root / 'request.json')
    model = 'diar-streaming-sortformer-4spk-v2-1'
    artifact, code = upload_source(source=source, model=model, media_type='audio/wav', directory=root / 'upload', idempotency_key=request['id'] + '-source')
    if code:
        return code
    immutable_input(root / 'input.json', {'audio': artifact})
    receipt, code = invoke(model=model, tool='infer_diar_streaming_sortformer_4spk_v2_1_native', input_path=root / 'input.json', directory=root / 'run', idempotency_key=request['id'] + '-diar', wait_seconds=120, recover_only=False)
    if code:
        return code
    result = unwrap(load(root / 'run' / 'result.json'))
    duration = float(result['audio_seconds'])
    if abs(duration - float(request['audio_seconds'])) > .2:
        raise ValueError('Diarization duration differs from captured audio')
    value = attribute_words(request['words'], result['events'], duration)
    value.update(schema='scientific-clinical/speaker-transcript/v1', audio=file_identity(source),
                 audio_seconds=duration, asr_model=request['asr_model'], diarization_model=model,
                 operation_id=receipt.get('operation_id'), clinical_validation=False)
    save(root / 'result.json', value)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # No raw remote provider errors / patient text in process logs.
        print(json.dumps({'error': type(exc).__name__, 'detail': 'Speaker finalization failed; inspect retained private receipts.'}))
        raise SystemExit(1)
