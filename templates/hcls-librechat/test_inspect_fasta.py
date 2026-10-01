import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('inspect_fasta', Path(__file__).with_name('inspect-fasta.py'))
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class FastaTest(unittest.TestCase):
    def test_measured_denominators_and_missing_gc(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'source.fa', Path(folder) / 'out.csv'
            source.write_text('>one\nACGTACGTNN\n>all-ambiguous\nNNNN\n>lowercase\ngcat\n')
            rows = MOD.inspect(source, target)['rows']
            self.assertEqual(rows[0], {'sequence_id': 'one', 'length': 10, 'valid_acgt_bases': 8,
                'gc_bases': 4, 'gc_percent': 50., 'ambiguous_bases': 2})
            self.assertIsNone(rows[1]['gc_percent'])
            self.assertEqual(rows[2]['gc_percent'], 50.)
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                MOD.inspect(source, target)
            self.assertEqual(target.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
