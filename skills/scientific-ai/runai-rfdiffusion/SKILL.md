---
name: runai-rfdiffusion
description: Run reviewed RFdiffusion backbone, motif and partial-diffusion workflows on the managed Scientific AI Run:ai service. Use for receptor-conditioned binder design, hotspots, qualified checkpoint families, symmetry, inpainting and supported guiding controls.
license: Apache-2.0
---

# rfdiffusion on Scientific AI Run:ai

Read [the Run:ai scientific gateway](../runai-scientific-gateway/SKILL.md) and
[portable client procedure](../runai-scientific-gateway/references/client.md).
Model ID: `rfdiffusion`. Documented scientific version: `1.1.0+symmetry.8810bf28.dimerrog.0b96ce0f`; confirm
the live supported versions and workflow schema before submitting. This skill
targets the managed scientific API, not native Run:ai administration or the
other backend's scientific-batch artifact-manifest API.

## Prepare scientific inputs

Archive `target.pdb` (`chemical/x-pdb`, coordinates in ångströms) and
`settings.json` (`application/json`) at the root of `input.tar.gz`
(`application/gzip`). They stage below `data/inputs/`. Required scaffold/motif scientific files must also be present
under that input tree. Inspect real chain/residue identifiers before defining
contigs or hotspots; do not silently renumber, crop or substitute targets.

## Choose the scientific workflow

Select `operation`: `design-backbone`, `scaffold-motif` or `partial-diffusion`.
Preserve native significant whitespace in a **single** contig string. A receptor
plus separate binder can use syntax such as `"A1-47/0 100-100"` only when those
receptor residues exist in the supplied target. Splitting that into separate
array entries or removing its space changes the scientific meaning.

Hotspots use chain/residue strings such as `A20` and must map to the receptor.
Choose `checkpoint_family` (`auto`, `Base`, `Complex_base`, `InpaintSeq`,
`ActiveSite`, `Complex_beta`) for the actual task; a PPI-specialized checkpoint is not silently interchangeable with another.
Partial diffusion needs its compatible timestep and input mapping. Symmetry,
guiding potentials, noise, inpainting and scaffold controls must remain mutually
compatible; read the complete live schema instead of guessing Hydra strings.
`noise_scale_ca` and `noise_scale_frame` independently select translational and
rotational noise; an omitted component inherits the existing `noise_scale`.
Use the same scientific settings when comparing runs. Lower noise does not
guarantee improved binding or design quality.

For partial diffusion, input length and contig mapping must cover the complete
input structure. The full schedule requires `diffuser_T >= 15`; `partial_T`
may be below 15 but cannot exceed `diffuser_T`. `provide_seq` uses
zero-based inclusive input positions, and requires `InpaintSeq` or compatible
`auto` selection. PDB motif ranges use the actual chain and residue identifiers.
Do not confuse these numbering conventions or pretrained checkpoint variants
with resumable execution checkpoints.

## Submit the selected workflow

The following REST bodies use the owner's published example inputs when
`inputs` is omitted. For caller data, add the exact archive reference from
the portable upload procedure. Named MCP tools take the same fields without
`model`/`workflow`, plus the saved `idempotency_key`. Preserve the key on retries.

### backbone-and-motif

MCP tool: `rfdiffusion_backbone_and_motif`. Execution: GPU.

```json
{"model":"rfdiffusion","workflow":"backbone-and-motif","version":"1.1.0+symmetry.8810bf28.dimerrog.0b96ce0f","parameters":{}}
```

## Worked scientific controls

Prepare the 20-residue first NMR model of public [PDB 1L2Y](https://www.rcsb.org/structure/1L2Y)
with Python 3 standard library in a new caller-owned directory. The coordinates
are [CC0](https://www.wwpdb.org/about/usage-policies); retain the structure citation.
This preserves chain A residues 1–20 and all their atom records, normalizing only
model/termination records to reproduce the reviewed structure. Stop if either
source or prepared-structure checksum differs.

```python
import gzip, hashlib, io, tarfile, urllib.request
from pathlib import Path

raw = urllib.request.urlopen('https://files.rcsb.org/download/1L2Y.pdb', timeout=60).read()
assert hashlib.sha256(raw).hexdigest() == '5d1bbb545a312dfff1ae1e64b6d8addecb2f561ddc4011aeb5bee9d1dfcd4438'
lines = raw.decode().splitlines()
start = next(i for i, line in enumerate(lines) if line.startswith('MODEL '))
end = next(i for i in range(start, len(lines)) if lines[i].startswith('ENDMDL'))
model = lines[start + 1:end]
assert {(line[21:22], int(line[22:26])) for line in model if line.startswith('ATOM  ')} == {('A', n) for n in range(1, 21)}
target = '\n'.join(['MODEL      1'] +
                   [line.ljust(81) if line.startswith('TER   ') else line for line in model] +
                   ['ENDMDL', 'END   ']) + '\n'
assert hashlib.sha256(target.encode()).hexdigest() == '1dd1d31524f2575fef6b52a8021c15e98df75103109508b52a5810a59109e055'
Path('target.pdb').write_text(target)
Path('settings.json').write_text('{}\n')
with Path('input.tar.gz').open('wb') as destination:
    with gzip.GzipFile(fileobj=destination, mode='wb', filename='', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name in ['settings.json', 'target.pdb']:
                data = Path(name).read_bytes()
                member = tarfile.TarInfo(name)
                member.size, member.mode, member.mtime = len(data), 0o600, 0
                archive.addfile(member, io.BytesIO(data))
```

Upload this archive using the gateway procedure and add its exact owned `inputs`
reference to each worked request below; compute its complete compressed SHA-256
and byte count. The empty settings preserve the explicit request controls. For
caller structures, derive contigs and hotspots from their actual identifiers;
do not apply these fixture residue ranges to an unrelated target.

Unconditional Base backbone with independent denoising controls:

```json
{"model":"rfdiffusion","workflow":"backbone-and-motif","version":"1.1.0+symmetry.8810bf28.dimerrog.0b96ce0f","parameters":{"contigs":["76-76"],"num_designs":1,"seed":8100,"diffuser_T":50,"checkpoint_family":"Base","noise_scale_ca":0.25,"noise_scale_frame":0.75}}
```

Receptor-conditioned binder transport smoke test:

```json
{"model":"rfdiffusion","workflow":"backbone-and-motif","version":"1.1.0+symmetry.8810bf28.dimerrog.0b96ce0f","parameters":{"operation":"scaffold-motif","contigs":["A1-20/0 20-20"],"hotspot_residues":["A4"],"checkpoint_family":"Complex_base","num_designs":1,"seed":8200,"noise_scale_ca":0.25,"noise_scale_frame":0.75}}
```

This creates a 20-residue candidate binder beside a 20-residue retained
receptor. It verifies staging, conditioning and output interpretation; it does
not qualify a larger therapeutic binder campaign or establish binding.

Partial diffusion on the complete 20-residue fixture, with a fixed PDB motif
and retained input sequence at zero-based positions 10–19:

```json
{"model":"rfdiffusion","workflow":"backbone-and-motif","version":"1.1.0+symmetry.8810bf28.dimerrog.0b96ce0f","parameters":{"operation":"partial-diffusion","contigs":["A1-4/16-16"],"partial_T":10,"provide_seq":["10-19"],"checkpoint_family":"InpaintSeq","num_designs":1,"seed":8300,"diffuser_T":50,"noise_scale_ca":0.25,"noise_scale_frame":0.75}}
```

Inspect the actual selected checkpoint, retained sequence/mapping and trajectory
step count. These requests intentionally choose different scientific controls;
they are not an optimization comparison. Use only options qualified for the
current release. The corrected `dimer_ROG` potential in this scientific version
averages the independent clamped C-alpha radii of gyration of the two monomers.
It encourages monomer compactness and does not establish binding or affinity.

## Interpret and retain results

Independently read designed structures and metadata. Confirm retained receptor,
new binder/motif mapping, requested lengths, hotspot conditioning, constraints
and actual design count. A target-only PDB is not binder design. Downstream
sequence design/refolding is a separate qualified workflow; a backbone does not
prove binding.

Recovery preserves completed native design units; an unfinished denoising unit
may recompute. Do not promise restoration of mid-denoising GPU/RNG state.

After stopping, private scratch is deleted following at most 300 seconds of
final owner-bucket upload retries; report any unsynced tail loss.

Poll the returned owned run, verify downloaded artifact sizes/SHA-256 and
retain scientific provenance in the owner's store. Report public errors and
partial results without secrets, signed links or private image/deployment IDs.
Skills do not grant licences, access to another owner or untested capabilities.
