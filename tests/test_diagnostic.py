import json
import unittest
from pathlib import Path
from unittest.mock import Mock
from app.diagnostic import diagnose
from app.tasy import Tasy

CONFIG = Path(__file__).resolve().parents[1] / 'config/tasy.json'


class DiagnosticTest(unittest.TestCase):
    def test_orchestrator_never_saves_or_writes_status(self):
        robot = Mock()
        record, user, report = object(), object(), Mock()
        diagnose(robot, record, user, report)
        self.assertEqual([call[0] for call in robot.method_calls], ['start', 'login', 'prepare'])
        robot.save.assert_not_called()

    def test_unvalidated_config_allows_diagnosis_but_not_batch(self):
        self.assertFalse(json.loads(CONFIG.read_text(encoding='utf-8'))['validated'])
        with self.assertRaises(ValueError):
            Tasy(CONFIG, {})
        robot = Tasy(CONFIG, {}, diagnostic=True)
        with self.assertRaisesRegex(ValueError, 'não permite'):
            robot.save(object(), {})

    def test_supervised_test_does_not_validate_batch(self):
        robot = Tasy(CONFIG, {}, allow_import=True)
        self.assertFalse(robot.diagnostic)
        self.assertFalse(robot.config['validated'])

    def test_preparation_failure_does_not_continue(self):
        robot = Mock()
        robot.prepare.side_effect = ValueError('Paciente incorreto')
        with self.assertRaises(ValueError):
            diagnose(robot, object(), {}, Mock())
        robot.save.assert_not_called()
