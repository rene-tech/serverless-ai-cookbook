#!/usr/bin/env python3
"""CPU ligand parameterization in an operator-provisioned OpenFF environment.

Produces a standalone ligand, not a solvated/protein/membrane MD system. No
package installation, model-service submission or force-field substitution.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import sys
from urllib.parse import urlencode


def package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        records = list((Path(sys.prefix) / 'conda-meta').glob(name + '-*.json'))
        matching = [json.loads(p.read_text()) for p in records]
        matching = [r for r in matching if r.get('name') == name]
        if len(matching) != 1:
            raise ValueError('Cannot establish installed version of ' + name)
        return matching[0]['version']


def prepare(smiles, output, force_field):
    # AmberTools subprocesses must resolve from the same provisioned environment
    # as this interpreter, not the web server's unrelated system PATH.
    os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
    import numpy as np
    import openmm
    from openff.toolkit import ForceField, Molecule
    from openff.toolkit.utils import AmberToolsToolkitWrapper, RDKitToolkitWrapper, ToolkitRegistry
    from openff.units import unit

    if not force_field.startswith('openff-2.') or not force_field.endswith('.offxml'):
        raise ValueError('Choose an explicit installed Sage 2.x .offxml, not another force-field family')
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a fresh output directory; existing customer results are not overwritten')
    started = time.monotonic()
    registry = ToolkitRegistry([RDKitToolkitWrapper(), AmberToolsToolkitWrapper()])
    molecule = Molecule.from_smiles(smiles, allow_undefined_stereo=False, toolkit_registry=registry)
    molecule.generate_conformers(n_conformers=1, toolkit_registry=registry, clear_existing=True)
    charge_start = time.monotonic()
    molecule.assign_partial_charges('am1bcc', use_conformers=molecule.conformers,
                                    toolkit_registry=registry)
    charge_seconds = time.monotonic() - charge_start
    charges = np.asarray(molecule.partial_charges.m_as(unit.elementary_charge))
    formal = float(molecule.total_charge.m_as(unit.elementary_charge))
    if not np.isfinite(charges).all() or abs(float(charges.sum()) - formal) > 1e-5:
        raise ValueError('Assigned charge sum is not finite or does not match formal charge')
    output.mkdir(parents=True, exist_ok=True)
    # Preserve the expensive result even if an export/reporting step fails.
    (output / 'charges.json').write_text(json.dumps({'input_smiles': smiles,
        'charge_method': 'AmberTools AM1-BCC', 'partial_charges_e': charges.tolist(),
        'charge_seconds': charge_seconds}, indent=2) + '\n')
    molecule.to_file(str(output / 'charged-ligand.sdf'), file_format='sdf', toolkit_registry=registry)
    # Modern GROMACS export requires a box. This artificial empty box is only
    # an export scaffold, explicitly NOT solvent or a proposed simulation setup.
    positions = molecule.conformers[0].m_as(unit.nanometer)
    lengths = np.ptp(positions, axis=0) + 2.0
    positions = positions - positions.min(axis=0) + 1.0
    topology = molecule.to_topology()
    topology.box_vectors = np.diag(lengths) * unit.nanometer
    forcefield = ForceField(force_field)
    interchange = forcefield.create_interchange(topology,
                         charge_from_molecules=[molecule], toolkit_registry=registry)
    interchange.positions = positions * unit.nanometer
    system = interchange.to_openmm()
    integrator = openmm.VerletIntegrator(0.001 * openmm.unit.picoseconds)
    context = openmm.Context(system, integrator, openmm.Platform.getPlatformByName('Reference'))
    context.setPositions(interchange.positions.to_openmm())
    energy = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(openmm.unit.kilojoule_per_mole)
    if not np.isfinite(energy) or system.getNumParticles() != molecule.n_atoms:
        raise ValueError('Particle count or initial CPU reference energy check failed')
    del context, integrator
    with tempfile.TemporaryDirectory(prefix='openff-prepare-') as folder:
        scratch = Path(folder)
        interchange.to_gromacs(prefix=str(scratch / 'ligand'))
        (scratch / 'system.xml').write_text(openmm.XmlSerializer.serialize(system))
        (scratch / 'force-field.offxml').write_text(forcefield.to_string())
        molecule.to_file(str(scratch / 'ligand.sdf'), file_format='sdf', toolkit_registry=registry)
        versions = {name: package_version(name) for name in
                    ('openff-toolkit', 'openff-interchange', 'openff-forcefields', 'openmm', 'rdkit', 'ambertools')}
        measurements = {'schema': 'scientific-openff-preparation/v1',
            'scope': 'standalone ligand parameterization, not an MD-ready receptor/membrane system',
            'input_smiles': smiles, 'canonical_smiles': molecule.to_smiles(toolkit_registry=registry),
            'force_field': force_field, 'charge_method': 'AmberTools AM1-BCC',
            'atom_count': molecule.n_atoms, 'formal_charge_e': formal,
            'partial_charges_e': charges.tolist(), 'charge_sum_e': float(charges.sum()),
            'charge_seconds': charge_seconds, 'cpu_reference_energy_kj_mol': float(energy),
            'energy_platform': 'OpenMM Reference (CPU)', 'versions': versions,
            'export_box_nm': lengths.tolist(),
            'box_purpose': 'artificial empty export box; 1 nm padding, not a solvated MD system',
            'conformer_seed': 'Toolkit RDKit default; not caller-selected',
            'elapsed_seconds': time.monotonic() - started,
            'gromacs_grompp_validation': 'not performed by this helper',
            'conversion_validation': 'Interchange export; particle/charge/finite OpenMM energy checks only'}
        (scratch / 'preparation.json').write_text(json.dumps(measurements, indent=2, allow_nan=False) + '\n')
        (scratch / 'README.md').write_text(
            '# OpenFF ligand preparation\n\n'
            'See preparation.json for input, exact versions, charges and measured checks.\n'
            'ligand.top and ligand.gro are a standalone ligand, not a complete MD system.\n'
            'No protein, membrane, solvent, equilibration or production run is included.\n'
            'The artificial empty export box has 1 nm padding, not a validated MD setup.\n'
            'SDF retains original conformer coordinates; GRO is translated into the export box.\n'
            'GROMACS preprocessing and matched-engine energy validation remain necessary.\n')
        files = {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                 for p in scratch.iterdir() if p.is_file()}
        if not {'ligand.top', 'ligand.gro', 'preparation.json'}.issubset(files):
            raise ValueError('Required GROMACS/measurement outputs were not produced')
        output.mkdir(parents=True, exist_ok=True)
        for name, expected in files.items():
            shutil.copyfile(scratch / name, output / name)
            if hashlib.sha256((output / name).read_bytes()).hexdigest() != expected['sha256']:
                raise ValueError('Output readback mismatch: ' + name)
        for name in ('charges.json', 'charged-ligand.sdf'):
            data = (output / name).read_bytes()
            files[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        manifest = {'schema': 'scientific-openff-files/v1', 'files': files}
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    links = {}
    if output.is_absolute() and output.is_relative_to('/workspace'):
        for name in files:
            relative = (output / name).relative_to('/workspace')
            links[name] = '/demos?' + urlencode({'tab': 'workspace', 'path': str(relative.parent), 'file': str(relative)})
    return {'status': 'completed', 'output_directory': str(output), 'workspace_links': links, 'atom_count': molecule.n_atoms,
            'charge_sum_e': float(charges.sum()), 'charge_seconds': charge_seconds,
            'force_field': force_field, 'files': list(files),
            'limitation': measurements['scope'] + '; GROMACS preprocessing/energy equivalence untested'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smiles', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--force-field', required=True)
    args = parser.parse_args()
    from openff.toolkit.utils.exceptions import UndefinedStereochemistryError
    try:
        result = prepare(args.smiles, args.output, args.force_field)
    except UndefinedStereochemistryError:
        print(json.dumps({'status': 'needs_user_input', 'code': 'undefined_stereochemistry',
            'question': 'Which stereoisomer should be used? Please supply isomeric SMILES or an explicit stereoisomer choice.',
            'next_step': 'Ask the user before preparation; do not assign or enumerate stereoisomers without their choice.',
            'outputs_created': False}))
        return 2
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
