import unittest
from app.core import HEADERS
from app.sheets import Sheets


class FakeWorksheet:
    def __init__(self):
        self.rows = [HEADERS.copy(), ['14/10/2026 11:28:07', 'Teste', '10/09/2026 10:30:00', 'Fisioterapeuta', 'Texto', 'Autor / 123', '']]
        self.updates = []

    def get_all_values(self):
        return self.rows

    def update_cell(self, row, column, value):
        self.updates.append((row, column, value))
        self.rows[row - 1][column - 1] = value


class SheetsTest(unittest.TestCase):
    def setUp(self):
        self.client = Sheets.__new__(Sheets)
        self.client.sheet = FakeWorksheet()

    def test_claim_and_block_repeat(self):
        record = self.client.read()[0]
        self.client.claim(record)
        self.assertEqual(self.client.sheet.updates, [(2, 7, 'Em processamento')])
        with self.assertRaises(ValueError):
            self.client.claim(record)
        self.client.status(record, 'Sim')
        self.assertEqual(self.client.read()[0].status, 'Sim')

    def test_relocate_moved_row(self):
        record = self.client.read()[0]
        self.client.sheet.rows.insert(1, [''] * 7)
        self.client.status(record, 'Sim')
        self.assertEqual(self.client.sheet.updates[-1], (3, 7, 'Sim'))

    def test_changed_or_duplicated_record_rejected(self):
        record = self.client.read()[0]
        self.client.sheet.rows.append(self.client.sheet.rows[1].copy())
        with self.assertRaises(ValueError):
            self.client.status(record, 'Sim')
        self.client.sheet.rows.pop()
        self.client.sheet.rows[1][4] = 'Alterado'
        with self.assertRaises(ValueError):
            self.client.status(record, 'Sim')

    def test_missing_headers(self):
        self.client.sheet.rows[0][-1] = 'Outra coluna'
        with self.assertRaises(ValueError):
            self.client.read()
