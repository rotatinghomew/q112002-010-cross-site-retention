import unittest

from record_reader import read_records


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self.tables = read_records()

    def references(self, left, left_key, right, right_key):
        candidates = {row[right_key] for row in self.tables[right]}
        self.assertTrue(all(row[left_key] in candidates for row in self.tables[left]))

    def test_documents_reference_source_records(self):
        self.references('certificates','form','forms','form')
        self.references('appointments','session','agenda','session')
        self.references('stock','form','forms','form')
        self.references('availability','session','agenda','session')
        forms = {row['form']: row['family'] for row in self.tables['forms']}
        self.assertEqual(forms['f1'], forms['f2'])
        exposure = next(row for row in self.tables['exposures'] if row['kind']=='讲解')
        lock = next(row for row in self.tables['locks'] if row['room']==exposure['room'])
        self.assertLess(exposure['day'], lock['cutoff'])
        self.assertLess(lock['cutoff'], exposure['received'])
