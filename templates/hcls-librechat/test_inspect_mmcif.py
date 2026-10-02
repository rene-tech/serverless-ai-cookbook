import importlib.util
import csv
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('inspect_mmcif', Path(__file__).with_name('inspect-mmcif.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FIXTURE = '''data_test
loop_
_entity.id
_entity.type
_entity.pdbx_description
1 polymer 'Test protein'
2 non-polymer 'Ligand'
3 water 'Water'
loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
1 1 ALA
1 2 GLY
1 3 SER
loop_
_chem_comp.id
_chem_comp.name
_chem_comp.formula
LIG Ligand C
HOH Water 'H2 O'
loop_
_atom_site.label_asym_id
_atom_site.auth_asym_id
_atom_site.label_entity_id
_atom_site.label_seq_id
_atom_site.auth_seq_id
_atom_site.label_comp_id
_atom_site.type_symbol
_atom_site.pdbx_PDB_model_num
A X 1 1 1 ALA C 1
A X 1 2 500 GLY N 1
B X 2 . 900 LIG C 1
C W 3 . 1 HOH O 1
'''


class InventoryTest(unittest.TestCase):
    def inspect(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.cif'
            path.write_text(text)
            return MODULE.inventory(path)

    def test_author_number_jump_is_not_missing_sequence(self):
        result = self.inspect(FIXTURE)
        chain = result['polymer_chains'][0]
        self.assertEqual(chain['auth_asym_ids'], ['X'])
        self.assertEqual(chain['modeled_sequence_positions'], 2)
        self.assertEqual(chain['unmodeled_label_seq_id_ranges'], [[3, 3]])

    def test_ligand_is_not_merged_into_polymer_auth_chain(self):
        result = self.inspect(FIXTURE)
        self.assertEqual(result['atom_records'], 4)
        self.assertEqual(result['polymer_chains'][0]['atom_records'], 2)
        self.assertEqual(result['nonpolymer_components'][0]['components'][0]['id'], 'LIG')
        self.assertEqual(result['water_atom_records'], 1)

    def test_no_coordinates_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'No coordinate atoms'):
            self.inspect('data_empty\n_entry.id empty\n')

    def test_report_distinguishes_polymer_and_whole_file_counts(self):
        result = self.inspect(FIXTURE)
        self.assertEqual(result['polymer_chains'][0]['elements'], {'C': 1, 'N': 1})
        report = MODULE.markdown(result)
        self.assertIn('Whole file: 4 atom-site records', report)
        self.assertIn('| Test protein | 2 / 3 | 2 |', report)
        self.assertIn('Water atom-site records: 1', report)
        self.assertIn('MD readiness were not checked', report)

    def test_incomplete_entity_metadata_does_not_claim_no_water(self):
        result = self.inspect(FIXTURE.replace("3 water 'Water'\n", ''))
        self.assertFalse(result['entity_classification_complete'])
        self.assertIsNone(result['water_atom_records'])
        self.assertEqual(result['alternate_location_atom_records'], 0)

    def test_multi_block_requires_explicit_selection(self):
        with self.assertRaisesRegex(ValueError, 'single data block'):
            self.inspect(FIXTURE + '\ndata_other\n_entry.id other\n')

    def test_ranges_do_not_mutate_input(self):
        values = {1, 2, 4, 8, 9}
        self.assertEqual(MODULE.intervals(values), [[1, 2], [4, 4], [8, 9]])
        self.assertEqual(values, {1, 2, 4, 8, 9})

    def test_csv_matches_measured_chains_and_does_not_overwrite(self):
        result = self.inspect(FIXTURE)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'inventory.csv'
            receipt = MODULE.write_csv(result, target)
            with target.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(receipt['rows'], 3)
            self.assertEqual([r['label_asym_id'] for r in rows], ['A', 'B', 'C'])
            self.assertEqual(sum(int(r['atom_records']) for r in rows), result['atom_records'])
            self.assertEqual(rows[0]['modeled_sequence_positions'], '2')
            self.assertEqual(json.loads(rows[0]['unmodeled_label_seq_id_ranges']), [[3, 3]])
            self.assertEqual(rows[1]['modeled_sequence_positions'], '')
            self.assertEqual(rows[1]['source_sha256'], result['sha256'])
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                MODULE.write_csv(result, target)
            self.assertEqual(target.read_bytes(), original)
            polymer = Path(folder) / 'polymer.csv'
            self.assertEqual(MODULE.write_csv(result, polymer, polymer_only=True)['rows'], 1)
            with polymer.open() as stream:
                self.assertEqual([r['label_asym_id'] for r in csv.DictReader(stream)], ['A'])


if __name__ == '__main__':
    unittest.main()
