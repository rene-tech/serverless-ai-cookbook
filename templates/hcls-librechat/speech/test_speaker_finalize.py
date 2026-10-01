import importlib.util
from pathlib import Path
import pytest
import hashlib
import json
import sys
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('speaker_finalize', Path(__file__).with_name('speaker-finalize.py'))
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

def word(text, start, end):
    return {'text': text, 'start_seconds': start, 'end_seconds': end}

def events(probabilities):
    return [{'type': 'speaker.activity', 'start_seconds': 0, 'frame_duration_seconds': .1, 'probabilities': probabilities}]

def test_actual_time_overlap_gives_anonymous_turns():
    result = module.attribute_words([word('Hello', 0, .2), word('doctor', .2, .4), word('Welcome', .4, .6)], events([[.9, .05, 0, 0]] * 4 + [[.05, .9, 0, 0]] * 2), .6)
    assert [turn['speaker'] for turn in result['turns']] == ['speaker_0', 'speaker_1']
    assert result['turns'][0]['text'] == 'Hello doctor'

def test_overlap_and_low_confidence_are_not_forced_to_a_person():
    result = module.attribute_words([word('both', 0, .1), word('unclear', .1, .2)], events([[.8, .7, 0, 0], [.4, .38, .3, .1]]), .2)
    assert result['words'][0]['speaker'] == 'speaker_0+speaker_1'
    assert result['words'][0]['flag'] == 'overlap'
    assert result['words'][1]['speaker'] == 'uncertain'

def test_exact_asr_rendering_keeps_midword_final_chunks_and_spaces():
    words = [{**word(text, i * .1, (i + 1) * .1), 'render_text': rendered}
             for i, (text, rendered) in enumerate([(' sor', ' sor'), ('ry', 'ry'), ('to', ' to'), ('hear', ' hear')])]
    result = module.attribute_words(words, events([[.9, 0, 0, 0]] * 4), .4)
    assert result['turns'][0]['text'] == 'sorry to hear'

@pytest.mark.parametrize('words', [[word('bad', 1, 0)], [word('bad', 0, 50)], [], [word('bad', float('nan'), .1)]])
def test_invalid_or_absent_asr_timings_never_fabricate_alignment(words):
    with pytest.raises(ValueError):
        module.attribute_words(words, events([[.9, 0, 0, 0]]), .1)

def test_completed_live_operation_is_reused_without_a_second_diarization(tmp_path, monkeypatch):
    calls = []
    result = {'model': 'diar-streaming-sortformer-4spk-v2-1', 'audio_seconds': .2,
              'events': events([[.9, 0, 0, 0]] * 2)}
    streamed = {'receipt': {'operation_id': 'original-live-operation'}, 'result': result}
    raw = json.dumps(streamed).encode()
    (tmp_path / 'streamed-diarization.json').write_bytes(raw)
    (tmp_path / 'input.wav').write_bytes(b'exact-audio')
    request = {'id': 'request', 'words': [word('No fever', 0, .2)], 'asr_model': 'same-medical',
               'audio_seconds': .2, 'stream_operation_id': 'original-live-operation',
               'streamed_result_sha256': hashlib.sha256(raw).hexdigest()}
    (tmp_path / 'request.json').write_text(json.dumps(request))
    def forbidden(**kwargs):
        raise AssertionError('A retained live result must never submit another diarization')
    monkeypatch.setitem(sys.modules, 'recording_pipeline', SimpleNamespace(
        upload_source=lambda **kwargs: (calls.append('audio-artifact') or {'artifact_id': 'source'}, 0),
        invoke=forbidden, immutable_input=forbidden, unwrap=lambda value: value,
        file_identity=lambda source: {'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}))
    monkeypatch.setitem(sys.modules, 'scientific_receipts', SimpleNamespace(
        load=lambda path: json.loads(path.read_text()),
        save=lambda path, value: path.write_text(json.dumps(value))))
    monkeypatch.setattr(sys, 'argv', ['speaker-finalize', str(tmp_path)])
    assert module.main() == 0
    saved = json.loads((tmp_path / 'result.json').read_text())
    assert saved['operation_id'] == 'original-live-operation'
    assert saved['diarization_mode'] == 'retained-live-stream'
    assert calls == ['audio-artifact']
    (tmp_path / 'streamed-diarization.json').write_bytes(b'changed')
    with pytest.raises(ValueError, match='bytes changed'):
        module.main()
