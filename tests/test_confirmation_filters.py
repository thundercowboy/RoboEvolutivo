import sqlite3
import unittest
from unittest.mock import Mock
from app.core import Record
from app.manual_confirmation import confirm_records
from app.filtering import date_period, within_period


class PeriodTest(unittest.TestCase):
    def test_inclusive_days_and_cross_month(self):
        period = date_period('30/09/2026', '02/10/2026')
        self.assertTrue(within_period('02/10/2026 23:59:59', period))
        self.assertTrue(within_period('01/10/2026 00:00:00', period))
        self.assertFalse(within_period('03/10/2026 00:00:00', period))

    def test_optional_bounds_and_minutes(self):
        self.assertTrue(within_period('15/10/2026 12:30:59', date_period('', '15/10/2026 12:30')))
        self.assertFalse(within_period('15/10/2026 12:31:00', date_period('', '15/10/2026 12:30')))
        self.assertTrue(within_period('01/01/2020 00:00:00', date_period('', '')))
        self.assertFalse(within_period('14/10/2026 23:59:59', date_period('15/10/2026', '')))

    def test_invalid_period_is_rejected(self):
        for start, end in [('31/02/2026', ''), ('20/10/2026', '19/10/2026')]:
            with self.assertRaises(ValueError):
                date_period(start, end)


class ConfirmationTest(unittest.TestCase):
    def setUp(self):
        self.records = [Record(str(i), 'Paciente fictício', '15/10/2026 12:00:00', 'fonoaudiologo', 'Texto', 'Autor', 'Conferir') for i in range(2)]
        self.ledger = Mock()
        self.ledger.db = sqlite3.connect(':memory:')
        self.addCleanup(self.ledger.db.close)
        self.sheets = Mock()
        self.report = Mock()

    def test_confirmation_updates_both_stores_and_audits(self):
        self.assertEqual(confirm_records(self.records, self.sheets, self.ledger, 'sheet:', self.report), 2)
        self.assertEqual(self.ledger.set.call_args_list[0].args, ('sheet:0', 'Sim'))
        self.assertEqual(self.sheets.status.call_count, 2)
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM manual_confirmations').fetchone()[0], 2)

    def test_changed_source_blocks_all_updates(self):
        self.sheets.locate.side_effect = [None, ValueError('Resposta alterada')]
        with self.assertRaises(ValueError):
            confirm_records(self.records, self.sheets, self.ledger, 'sheet:', self.report)
        self.ledger.set.assert_not_called()
        self.sheets.status.assert_not_called()

    def test_sheet_failure_preserves_local_confirmation_and_stops(self):
        self.sheets.status.side_effect = RuntimeError('network')
        with self.assertRaisesRegex(ValueError, 'preservada no SQLite'):
            confirm_records(self.records, self.sheets, self.ledger, 'sheet:', self.report)
        self.ledger.set.assert_called_once_with('sheet:0', 'Sim')
        self.report.assert_called_once_with('0', 'Sim')
