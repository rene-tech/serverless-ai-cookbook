"""Run frozen common CPU analysis against readonly, already downloaded files.

The external analysis source and spec are hashed evidence inputs, not installed
client features. No app supervisor, bucket mount, network or GPU is used.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


REAL_TOPOLOGY_CHECK = r'''
import hashlib, json, sys
from pathlib import Path
import numpy as np
import parmed
import netCDF4
spec = json.loads(Path(sys.argv[1]).read_text())
topology = Path(spec["master_directory"]) / "system.prmtop"
before = hashlib.sha256(topology.read_bytes()).hexdigest()
structure = parmed.load_file(str(topology))
assert len(structure.atoms) == 6598
assert len(structure.bonds) == 6597
assert len(structure.residues) == 2195
assert np.isfinite([atom.charge for atom in structure.atoms]).all()
assert abs(sum(atom.charge for atom in structure.atoms)) < 1e-5
assert hashlib.sha256(topology.read_bytes()).hexdigest() == before
rows = []
for run in spec["runs"]:
    if run["engine"] != "amber":
        continue
    path = Path(run["trajectory"])
    original = hashlib.sha256(path.read_bytes()).hexdigest()
    with netCDF4.Dataset(str(path), "r") as dataset:
        assert len(dataset.dimensions["atom"]) == 6598
        assert len(dataset.dimensions["frame"]) == 1000
        for name in ("coordinates", "time", "cell_lengths", "cell_angles"):
            variable = dataset.variables[name]
            assert np.isfinite(variable[:]).all(), name
        times = np.asarray(dataset.variables["time"][:])
        np.testing.assert_allclose(times, np.arange(1, 1001) + run["production_origin_time_ps"], atol=.001, rtol=0)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original
    rows.append({"path": str(path), "sha256": original, "frames": 1000, "all_coordinates_finite": True})
print(json.dumps({"status": "passed", "scope": "real ParmEd and netCDF4 input readers",
                  "master_sha256": before, "atoms": 6598, "bonds": 6597, "residues": 2195,
                  "netcdf": rows, "raw_inputs_unchanged": True, "customer_ready": False}))
'''


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--analysis-source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--render-engine', choices=('gromacs', 'namd', 'amber'), default='gromacs')
    args = parser.parse_args()
    args.spec = args.spec.resolve(strict=True)
    args.analysis_source = args.analysis_source.resolve(strict=True)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = json.loads(args.spec.read_text())
    if spec.get('path_base', 'absolute') != 'absolute':
        raise ValueError('Qualification spec must use explicit absolute paths')
    inputs = {args.spec, args.analysis_source, Path(spec['master_directory']).resolve(strict=True)}
    for run in spec['runs']:
        values = [run['trajectory'], run['native_topology'], run['production_log'],
                  run['thermo']['path'], *run.get('provenance_files', [])]
        inputs.update(Path(path).resolve(strict=True) for path in values)
    mounts = sorted(path for path in inputs if not any(other != path and other in path.parents for other in inputs))
    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
               '--tmpfs', '/tmp:rw,nosuid,size=1g', '--cpus', '4', '--memory', '4g',
               '-e', 'MPLCONFIGDIR=/tmp/matplotlib', '-e', 'PYTHONDONTWRITEBYTECODE=1',
               '-e', 'OMP_NUM_THREADS=1', '-e', 'OPENBLAS_NUM_THREADS=1',
               '--entrypoint', '/opt/md-analysis/bin/python']
    for path in mounts:
        command += ['--mount', f'type=bind,source={path},target={path},readonly']
    command += ['--mount', f'type=bind,source={args.output},target=/qualification', args.image]
    steps = [
        ('dependency-inventory', ['/opt/md-analysis/inventory.py']),
        ('pip-check', ['-m', 'pip', 'check']),
        ('synthetic-reader-tests', ['-m', 'unittest', 'discover', '-s', str(args.analysis_source / 'tests'), '-v']),
        ('real-parmed-netcdf', ['-c', REAL_TOPOLOGY_CHECK, str(args.spec)]),
        ('real-analysis', [str(args.analysis_source / 'compare.py'), '--spec', str(args.spec), '--output', '/qualification/analysis']),
        ('real-render', [str(args.analysis_source / 'render.py'), '/qualification/analysis', '--output', '/qualification/video', '--engines', args.render_engine]),
    ]
    receipt = {'image': args.image, 'recorded_at': datetime.now(timezone.utc).isoformat(),
               'spec_sha256': digest(args.spec), 'analysis_source': str(args.analysis_source),
               'source_files': {str(path.relative_to(args.analysis_source)): digest(path)
                                for path in sorted(args.analysis_source.rglob('*.py'))},
               'raw_inputs_readonly': True, 'network': 'none', 'gpu': False,
               'new_scientific_operations': 0, 'customer_ready': False, 'steps': []}
    for name, arguments in steps:
        with (args.output / (name + '.log')).open('x') as log:
            result = subprocess.run(command + arguments, stdout=log, stderr=subprocess.STDOUT)
        receipt['steps'].append({'name': name, 'exit_code': result.returncode,
                                 'log_sha256': digest(args.output / (name + '.log'))})
        receipt['status'] = 'failed' if result.returncode else 'in_progress'
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt['steps'][-1]), flush=True)
        if result.returncode:
            sys.exit(result.returncode)
    receipt['status'] = 'passed'
    receipt['artifacts'] = {str(path.relative_to(args.output)): digest(path)
                            for path in sorted(args.output.rglob('*')) if path.is_file() and path.name != 'receipt.json'}
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'output': str(args.output), 'customer_ready': False}))


if __name__ == '__main__':
    main()
