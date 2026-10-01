"""CPU helper integration checks. Requires the operator-provisioned OpenFF env.

Set OPENFF_PREPARATION_FIXTURE to a real completed helper directory for independent
artifact checks; no new parameterization is performed by the fixture tests.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('prepare_openff', Path(__file__).with_name('prepare-openff.py'))
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


OPENFF_AVAILABLE = (importlib.util.find_spec('openff') is not None
                    and importlib.util.find_spec('openff.toolkit') is not None)


@unittest.skipUnless(OPENFF_AVAILABLE, 'optional OpenFF environment required')
class PreparationTests(unittest.TestCase):
    def test_stereo_choices_are_computed_not_guessed_from_at_signs(self):
        from rdkit import Chem
        result = HELPER.inspect_identity('CC(O)CC')
        self.assertEqual(result['status'], 'needs_user_input')
        self.assertFalse(result['outputs_created'])
        self.assertEqual(len(result['choices']), 2)
        labels = set()
        for choice in result['choices']:
            actual = Chem.FindMolChiralCenters(Chem.MolFromSmiles(choice['isomeric_smiles']),
                                               useLegacyImplementation=False)
            self.assertEqual(choice['chiral_centers_zero_based'], actual)
            labels.update(label for _, label in actual)
        self.assertEqual(labels, {'R','S'})
        self.assertEqual(HELPER.inspect_identity('C[C@H](O)CC')['chiral_centers'][0][1], 'S')
        self.assertEqual(HELPER.inspect_identity('C[C@@H](O)CC')['chiral_centers'][0][1], 'R')

    def test_identity_probe_preserves_charge_and_rejects_invalid_input(self):
        result = HELPER.inspect_identity('C[NH3+]')
        self.assertEqual(result['formal_charge_e'], 1)
        self.assertEqual(result['status'], 'identity_defined')
        with self.assertRaises(ValueError):
            HELPER.inspect_identity('invalid-not-a-smiles')

    def test_undefined_stereochemistry_is_not_silently_assigned(self):
        from openff.toolkit.utils.exceptions import UndefinedStereochemistryError
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(UndefinedStereochemistryError):
                HELPER.prepare('CC(O)CC', Path(folder) / 'out', 'openff-2.2.1.offxml')
            self.assertFalse((Path(folder) / 'out').exists())

    def test_existing_results_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / 'customer.txt'
            original.write_text('preserve me')
            with self.assertRaisesRegex(ValueError, 'fresh output'):
                HELPER.prepare('CCO', folder, 'openff-2.2.1.offxml')
            self.assertEqual(original.read_text(), 'preserve me')

    @unittest.skipUnless(os.environ.get('OPENFF_PREPARATION_FIXTURE'), 'completed output fixture required')
    def test_real_export_hashes_chemistry_coordinates_and_charges(self):
        import numpy as np
        from openff.toolkit import Molecule
        root = Path(os.environ['OPENFF_PREPARATION_FIXTURE'])
        manifest = json.loads((root / 'manifest.json').read_text())
        for name, expected in manifest['files'].items():
            data = (root / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected['sha256'])
            self.assertEqual(len(data), expected['bytes'])
        measured = json.loads((root / 'preparation.json').read_text())
        source = Molecule.from_smiles(measured['input_smiles'], allow_undefined_stereo=False)
        exported = Molecule.from_file(str(root / 'ligand.sdf'))
        self.assertEqual(source.to_smiles(), exported.to_smiles())
        gro = (root / 'ligand.gro').read_text().splitlines()
        self.assertEqual(int(gro[1]), source.n_atoms)
        self.assertEqual(len(gro), source.n_atoms + 3)
        self.assertTrue(all(float(value) > 0 for value in gro[-1].split()))
        section, atom_rows = None, []
        for line in (root / 'ligand.top').read_text().splitlines():
            value = line.split(';', 1)[0].strip()
            if value.startswith('['):
                section = value.strip('[] ').strip()
            elif section == 'atoms' and value:
                atom_rows.append(value.split())
        self.assertEqual(len(atom_rows), source.n_atoms)
        np.testing.assert_allclose([float(row[6]) for row in atom_rows],
                                   measured['partial_charges_e'], atol=1e-7, rtol=0)
        self.assertAlmostEqual(sum(float(row[6]) for row in atom_rows), measured['formal_charge_e'], places=5)
        self.assertEqual(measured['gromacs_grompp_validation'], 'not performed by this helper')
        self.assertTrue(np.isfinite(measured['cpu_reference_energy_kj_mol']))


if __name__ == '__main__':
    unittest.main()
