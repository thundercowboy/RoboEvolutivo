import tempfile
import unittest
from pathlib import Path
from app.core import HEADERS, Ledger, parse


class RulesTest(unittest.TestCase):
    def row(self):
        return ['14/10/2026 11:28:07', 'Paciente fictício', '10/09/2026 10:30', 'Fisioterapeuta', 'Texto\nSegunda linha', 'Autor / Conselho', '']

    def test_date_author_and_text(self):
        record = parse(self.row(), list(range(7)))
        self.assertEqual(record.date, '09/10/2026 10:30:00')
        self.assertEqual(record.content, 'Texto\nSegunda linha\nAutor / Conselho')
        self.assertEqual(record.author, 'Autor / Conselho')

    def test_note_includes_author_without_changing_source_identity(self):
        from app.core import fingerprint
        row = self.row()
        row[4] = 'Evolução com acentuação.\nSegunda linha.\n'
        row[5] = 'Profissional fictício / Conselho 123'
        record = parse(row, list(range(7)))
        self.assertEqual(record.content, row[4] + '\n' + row[5])
        self.assertEqual(record.key, fingerprint(row[:6]))

    def test_invalid_date_and_profession(self):
        for column, value in [(2, '31/02/2026 10:30:00'), (2, '09/10/2026 10:30:01'), (3, 'Outra')]:
            row = self.row()
            row[column] = value
            with self.assertRaises(ValueError):
                parse(row, list(range(7)))

    def test_month_first_dates_and_unambiguous_day_first_output(self):
        for source, expected in [('10/15/2026 09:05', '15/10/2026 09:05:00'), ('03/04/2026 14:30', '04/03/2026 14:30:00'), ('12/31/2026 23:59:00', '31/12/2026 23:59:00')]:
            with self.subTest(source=source):
                row = self.row()
                row[2] = source
                self.assertEqual(parse(row, list(range(7))).date, expected)

    def test_no_day_first_fallback_or_invalid_us_date(self):
        for source in ('15/10/2026 09:05', '02/30/2026 09:05', '10/15/2026 09:05:01'):
            row = self.row()
            row[2] = source
            with self.assertRaises(ValueError):
                parse(row, list(range(7)))

    def test_status_not_part_of_identity(self):
        row = self.row()
        first = parse(row, list(range(7)))
        row[-1] = 'Sim'
        self.assertEqual(first.key, parse(row, list(range(7))).key)

    def test_crash_recovery(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            ledger = Ledger(Path(folder) / 'jobs.sqlite3')
            ledger.set('record', 'Em processamento')
            ledger.db.close()
            ledger = Ledger(Path(folder) / 'jobs.sqlite3')
            self.assertEqual(ledger.get('record'), 'Conferir')
            ledger.db.close()


if __name__ == '__main__':
    unittest.main()
