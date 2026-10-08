"""Generate non-customer fixtures for the real browser upload qualification."""
import hashlib
import io
import json
from pathlib import Path
import sys
import wave

root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=True)
cif = b'data_upload_test\nloop_\n_atom_site.label_atom_id\n_atom_site.type_symbol\n_atom_site.Cartn_x\n_atom_site.Cartn_y\n_atom_site.Cartn_z\nC1 C 0 0 0\nO1 O 1.2 0 0\n'
audio = io.BytesIO()
with wave.open(audio, 'wb') as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000)
    wav.writeframes(b'\x00\x00' * 8000)
fixtures = {'structure.cif': cif, 'structure.mmcif': cif, 'opaque.custom-format': bytes(range(256)) * 40960,
            'NO_EXTENSION': b'extensionless\n', 'empty.unusual': b'', 'Molek\u00fcl-\u03b1.dat': b'unicode filename\n',
            'audio-test.wav': audio.getvalue()}
records = []
for name, content in fixtures.items():
    (root / name).write_bytes(content)
    records.append({'name': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
(root / 'manifest.json').write_text(json.dumps(records, indent=2))
print(json.dumps({'fixtures': len(records), 'bytes': sum(row['bytes'] for row in records)}))
