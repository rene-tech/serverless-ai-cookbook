"""Portable pinned public-model-card example; no network or credentials."""
import argparse, csv, gzip, hashlib, io, json, tarfile
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--workflow', required=True, choices=['embed', 'score-sequences', 'extract-representations', 'logits', 'masked-completion', 'attention-maps'])
p.add_argument('--key', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); a.output.mkdir(parents=True)
heavy = 'VQLAQSGSELRKPGASVKVSCDTSGHSFTSNAIHWVRQAPGQGLEWMGWINTDTGTPTYAQGFTGRFVFSLDTSARTAYLQISSLKADDTAVFYCARERDYSDYFFDYWGQGTLVTVSS'
light = 'EVVMTQSPASLSVSPGERATLSCRARASLGISTDLAWYQQRPGQAPRLLIYGASTRATGIPARFSGSGSGTEFTLTISSLQSEDSAVYYCQQYSNWPLTFGGGTKVEIK'
assert len(heavy) == 119 and len(light) == 109
buffer = io.StringIO(newline=''); writer = csv.writer(buffer)
writer.writerow(['id', 'heavy', 'light']); writer.writerow(['official-pair-1', heavy, light])
data = buffer.getvalue().encode()
archive = a.output / 'input.tar.gz'
with archive.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as zipped, tarfile.open(fileobj=zipped, mode='w|') as tar:
    info = tarfile.TarInfo('sequences.csv'); info.size = len(data); info.mtime = 0; info.mode = 0o444
    tar.addfile(info, io.BytesIO(data))
parameters = ({'layers': [0, 1, 30]} if a.workflow == 'extract-representations'
              else {'masked_positions': [{'sequence_id': 'official-pair-1', 'heavy': [31], 'light': [44]}], 'top_k': 5} if a.workflow == 'masked-completion'
              else {'layers': [1, 30], 'heads': [0, 7, 15]} if a.workflow == 'attention-maps' else {})
reference = {'name': 'input.tar.gz', 'key': a.key, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'size_bytes': archive.stat().st_size}
for name, value in [('parameters.json', parameters), ('input-reference.json', reference)]:
    (a.output / name).write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps({'workflow': a.workflow, 'parameters': parameters, 'input': reference}))
