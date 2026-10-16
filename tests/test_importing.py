import unittest
from app.core import Record
from app.importing import ordered_imports


class ImportOrderTest(unittest.TestCase):
    def test_account_with_two_patients_runs_before_single_note_account(self):
        people = {'fonoaudiologo': {'login': 'z-fono', 'name': 'Pessoa F'}, 'terapeuta': {'login': 'a-terapia', 'name': 'Pessoa T'}}
        records = [
            Record('1', 'Paciente A', '15/10/2026 10:00:00', 'terapeuta', 'A', 'Autor', ''),
            Record('2', 'Paciente B', '15/10/2026 11:00:00', 'fonoaudiologo', 'B', 'Autor', ''),
            Record('3', 'Paciente A', '15/10/2026 12:00:00', 'fonoaudiologo', 'C', 'Autor', ''),
        ]
        self.assertEqual([r.key for r in ordered_imports(records, people)], ['3', '2', '1'])

    def test_groups_by_login_patient_and_actual_datetime(self):
        people = {'fisioterapeuta': {'login': 'conta-a', 'name': 'Responsável A'}, 'fonoaudiologo': {'login': 'conta-a', 'name': 'Responsável A'}, 'medico': {'login': 'conta-z', 'name': 'Responsável Z'}}
        records = [
            Record('a', 'Paciente X', '02/11/2026 10:00:00', 'fonoaudiologo', 'A', 'Autor', ''),
            Record('b', 'Paciente Y', '01/11/2026 10:00:00', 'fisioterapeuta', 'B', 'Autor', ''),
            Record('c', 'Paciente X', '31/10/2026 10:00:00', 'fisioterapeuta', 'C', 'Autor', ''),
            Record('d', 'Paciente X', '01/10/2026 10:00:00', 'medico', 'D', 'Autor', ''),
        ]
        self.assertEqual([r.key for r in ordered_imports(records, people)], ['c', 'a', 'b', 'd'])

    def test_same_login_with_conflicting_identity_is_rejected(self):
        records = [Record('a', 'Paciente', '15/10/2026 10:00:00', 'medico', 'A', 'Autor', ''), Record('b', 'Paciente', '15/10/2026 11:00:00', 'fisioterapeuta', 'B', 'Autor', '')]
        people = {'medico': {'login': 'mesmo', 'name': 'Pessoa A'}, 'fisioterapeuta': {'login': 'mesmo', 'name': 'Pessoa B'}}
        with self.assertRaises(ValueError):
            ordered_imports(records, people)
