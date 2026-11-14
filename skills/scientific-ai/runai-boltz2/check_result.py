"""Independent, predeclared CA-reference and confidence gate for the 1UBQ fixture."""
import argparse
import hashlib
import json
from pathlib import Path

import gemmi
import numpy as np

EXPECTED = 'MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG'
THRESHOLDS = {'full_76_CA_RMSD_max_A': 3.0, 'first_71_CA_RMSD_max_A': 2.0,
    'full_76_CA_lDDT_min': 0.8, 'native_complex_pLDDT_min': 0.8}


def ca_values(structure, predicted):
    assert len(structure) == 1
    if predicted:
        assert [chain.name for chain in structure[0]] == ['A']
    residues = [r for r in structure[0]['A'] if r.het_flag == 'A']
    assert len(residues) == 76
    assert ''.join(gemmi.find_tabulated_residue(r.name).one_letter_code for r in residues) == EXPECTED
    ca = []
    for residue in residues:
        assert all(residue.find_atom(name, '\0') is not None for name in ('N', 'CA', 'C', 'O'))
        for atom in residue:
            assert np.isfinite([atom.pos.x, atom.pos.y, atom.pos.z]).all()
        atom = residue.find_atom('CA', '\0')
        ca.append([atom.pos.x, atom.pos.y, atom.pos.z])
    return np.asarray(ca)


def rmsd(moving, fixed):
    moving, fixed = moving - moving.mean(axis=0), fixed - fixed.mean(axis=0)
    u, _, vt = np.linalg.svd(moving.T @ fixed)
    if np.linalg.det(u @ vt) < 0:
        u[:, -1] *= -1
    return float(np.sqrt(np.mean(np.sum((moving @ (u @ vt) - fixed) ** 2, axis=1))))


def ca_lddt(predicted, reference):
    ref_dist = np.linalg.norm(reference[:, None] - reference[None, :], axis=-1)
    pred_dist = np.linalg.norm(predicted[:, None] - predicted[None, :], axis=-1)
    pairs = (ref_dist < 15.0) & ~np.eye(len(reference), dtype=bool)
    delta = np.abs(pred_dist - ref_dist)[pairs]
    return float(np.mean([np.mean(delta < cutoff) for cutoff in (0.5, 1.0, 2.0, 4.0)]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--outputs', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    assert hashlib.sha256(args.reference.read_bytes()).hexdigest() == '056f98710cb2b36f633c45e41902a02eb446e82871da21ff2dd44f74a56ca0f6'
    files = list(args.outputs.glob('data/outputs/boltz2/boltz_results_boltz2-inputs/predictions/prediction/prediction_model_*.cif'))
    assert len(files) == 1
    predicted = ca_values(gemmi.read_structure(str(files[0])), True)
    reference = ca_values(gemmi.read_structure(str(args.reference)), False)
    adjacent = np.linalg.norm(np.diff(predicted, axis=0), axis=1)
    assert (adjacent > 2.7).all() and (adjacent < 4.5).all()
    science = json.loads((args.outputs / 'data/outputs/boltz2/science.json').read_text())
    assert science['tool_version'] == '2.2.1' and science['structures'] == 1
    assert len(science['targets']) == 1 and len(science['targets'][0]['samples']) == 1
    confidence = science['targets'][0]['samples'][0]['confidence']
    plddt = float(confidence['complex_plddt'])
    assert 0 <= plddt <= 1
    metrics = {'full_76_CA_RMSD_A': rmsd(predicted, reference),
        'first_71_CA_RMSD_A': rmsd(predicted[:71], reference[:71]),
        'full_76_CA_lDDT': ca_lddt(predicted, reference), 'native_complex_pLDDT': plddt,
        'CA_adjacent_min_A': float(adjacent.min()), 'CA_adjacent_max_A': float(adjacent.max())}
    gates = {'full_76_CA_RMSD': metrics['full_76_CA_RMSD_A'] <= THRESHOLDS['full_76_CA_RMSD_max_A'],
        'first_71_CA_RMSD': metrics['first_71_CA_RMSD_A'] <= THRESHOLDS['first_71_CA_RMSD_max_A'],
        'full_76_CA_lDDT': metrics['full_76_CA_lDDT'] >= THRESHOLDS['full_76_CA_lDDT_min'],
        'native_complex_pLDDT': plddt >= THRESHOLDS['native_complex_pLDDT_min']}
    result = {'status': 'PASS_POSITIVE_REFERENCE_SCIENCE' if all(gates.values()) else 'FAIL_POSITIVE_REFERENCE_SCIENCE',
        'reference': 'PDB 1UBQ chain A', 'residues': 76, 'sequence': EXPECTED,
        'metrics': metrics, 'predeclared_thresholds': THRESHOLDS, 'gates': gates,
        'structure_sha256': hashlib.sha256(files[0].read_bytes()).hexdigest(),
        'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        'scope': 'One predeclared known-structure control, no templates; not unseen-target accuracy or paired performance proof.'}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(gates.values()) else 1)


if __name__ == '__main__':
    main()
