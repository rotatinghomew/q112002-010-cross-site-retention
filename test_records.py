import unittest

from record_reader import read_records


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self.tables = read_records()

    def references(self, left, left_key, right, right_key):
        candidates = {row[right_key] for row in self.tables[right]}
        self.assertTrue(all(row[left_key] in candidates for row in self.tables[left]))

    def test_documents_reference_source_records(self):
        self.references('links','student','cohorts','student')
        self.references('invitations','basis','links','edge')
        self.references('invitations','contact','routes','contact')
        keys = {(row['site'],row['wave'],row['token']) for row in self.tables['results']}
        self.assertTrue(all((row['site'],row['wave'],row['token']) in keys for row in self.tables['links']))
        ambiguous = [row for row in self.tables['links'] if row['site']=='西' and row['wave']==2 and row['token']=='a']
        self.assertEqual({'s1','s2'}, {row['student'] for row in ambiguous})
        withdrawal = next(row for row in self.tables['links'] if row['state']=='withdrawn')
        appointment = next(row for row in self.tables['invitations'] if row['basis']==withdrawal['edge'])
        self.assertLess(appointment['issued'],withdrawal['day'])
