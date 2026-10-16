"""Local GUI checks with synthetic records; no network or clinical writes."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from app.core import Record, HEADERS, parse
from main import Application


class InterfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = Application()
        cls.window.update()

    @classmethod
    def tearDownClass(cls):
        for timer in cls.window.tk.call('after', 'info'):
            cls.window.after_cancel(timer)
        cls.window.destroy()

    def setUp(self):
        self.window.tree.delete(*self.window.tree.get_children())
        self.window.selection_anchor = None
        self.window.column_filters.clear()
        self.window.row_states.clear()
        self.window.records = [Record(f'test-{n}', 'Paciente fictício', '15/10/2026 09:05:00', 'fisioterapeuta', f'Texto fictício {n}', 'Autor fictício', '') for n in range(6)]
        for r in self.window.records:
            self.window.tree.insert('', 'end', iid=r.key, values=(r.patient, r.date[:-3], r.function, r.author, 'Pendente'))
        self.window.update()

    def click(self, row, shift=False):
        tree = self.window.tree
        tree.see(row)
        self.window.update()
        x, y, width, height = tree.bbox(row)
        state = 1 if shift else 0
        tree.event_generate('<Button-1>', x=x + 12, y=y + height // 2, state=state)
        tree.event_generate('<ButtonRelease-1>', x=x + 12, y=y + height // 2, state=state)
        self.window.update()

    def test_shift_click_selects_complete_interval(self):
        self.click('test-1')
        self.click('test-4', shift=True)
        self.assertEqual(self.window.tree.selection(), ('test-1', 'test-2', 'test-3', 'test-4'))
        self.assertEqual(self.window.content.get('1.0', 'end').strip(), 'Texto fictício 4')
        self.click('test-2', shift=True)
        self.assertEqual(self.window.tree.selection(), ('test-1', 'test-2'))

    def test_shift_arrows_expand_and_contract_from_same_anchor(self):
        self.click('test-1')
        self.window.tree.focus_force()
        self.window.update()
        for _ in range(2):
            self.window.tree.event_generate('<Shift-Down>')
            self.window.update()
        self.assertEqual(self.window.tree.selection(), ('test-1', 'test-2', 'test-3'))
        self.window.tree.event_generate('<Shift-Up>')
        self.window.update()
        self.assertEqual(self.window.tree.selection(), ('test-1', 'test-2'))

    def test_theme_checkbox_is_right_of_sheet_and_light_at_start(self):
        self.assertFalse(self.window.dark_mode)
        info = self.window.theme_checkbox.grid_info()
        self.assertEqual((info['row'], info['column']), (0, 2))
        self.window.theme_checkbox.invoke()
        self.assertTrue(self.window.dark_mode)
        self.window.theme_checkbox.invoke()
        self.assertFalse(self.window.dark_mode)

    def test_column_filters_intersect_and_remove_hidden_selections(self):
        self.window.records[0].patient = 'Paciente A'
        self.window.records[1].patient = 'Paciente B'
        self.window.records[2].patient = 'Paciente A'
        self.window.row_states['test-2'] = 'Sim'
        self.window.tree.selection_set('test-0', 'test-1', 'test-2')
        self.window.column_filters = {'patient': {'Paciente A'}, 'status': {'Pendente'}}
        self.window.render_records()
        self.window.update()
        self.assertEqual(self.window.tree.get_children(), ('test-0',))
        self.assertEqual(self.window.tree.selection(), ('test-0',))
        self.assertIn('●', self.window.tree.heading('patient', 'text'))
        self.assertEqual(self.window.visible_count.get(), '1 de 6 linhas')
        self.window.clear_filters()
        self.assertEqual(len(self.window.tree.get_children()), 6)

    def test_filter_popup_search_and_only_shown_applies_column(self):
        from tkinter import ttk, Toplevel
        self.window.records[0].patient = 'Paciente A'
        self.window.records[1].patient = 'Paciente B'
        self.assertTrue(self.window.tree.heading('patient', 'command'))
        self.window.open_filter('patient')
        dialog = next(child for child in self.window.winfo_children() if isinstance(child, Toplevel))
        controls = []
        def collect(widget):
            controls.append(widget)
            for child in widget.winfo_children():
                collect(child)
        collect(dialog)
        next(w for w in controls if isinstance(w, ttk.Entry)).insert(0, 'Paciente A')
        next(w for w in controls if isinstance(w, ttk.Button) and w.cget('text') == 'Somente exibidos').invoke()
        next(w for w in controls if isinstance(w, ttk.Button) and w.cget('text') == 'Aplicar').invoke()
        self.window.update()
        self.assertEqual(self.window.column_filters['patient'], {'Paciente A'})
        self.assertEqual(self.window.tree.get_children(), ('test-0',))

    def test_month_first_source_displayed_day_first_without_seconds(self):
        record = parse(['10/15/2026 10:00', 'Paciente fictício', '10/15/2026 09:05', 'Fisioterapeuta', 'Texto fictício', 'Autor fictício', ''], list(range(len(HEADERS))))
        self.window.events.put(('loaded', ({}, {}, [record])))
        self.window.poll()
        self.window.update()
        self.assertEqual(self.window.tree.item(record.key, 'values')[1], '15/10/2026 09:05')
        self.assertEqual(record.date, '15/10/2026 09:05:00')

    def test_real_launch_automatically_saves_two_selected_rows_and_reports_count(self):
        window = self.window
        window.settings = {'Planilha': 'https://docs.google.com/spreadsheets/d/ficticio/edit', 'Credenciais Google': 'ficticio.json'}
        window.professionals = {'fisioterapeuta': {'name': 'Responsável fictício', 'login': 'ficticio'}}
        window.professionals['fonoaudiologo'] = dict(window.professionals['fisioterapeuta'])
        window.records[1].function = 'fonoaudiologo'
        window.tree.selection_set('test-0', 'test-1')
        robot, sheet, ledger = Mock(), Mock(), Mock()
        ledger.get.return_value = ''
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            (root / 'config').mkdir()
            (root / 'config/pacientes.json').write_text(json.dumps({'Paciente fictício': {'attendance': '123', 'chart': '456'}}), encoding='utf-8')
            with patch('main.ROOT', root), patch('main.Tasy', return_value=robot), patch('main.Sheets', return_value=sheet), patch('main.Ledger', return_value=ledger), patch('main.ledger_path', return_value='unused'), patch.object(window, 'launch', side_effect=lambda task: task()):
                window.run()
        self.assertEqual(robot.login.call_count, 1)
        self.assertEqual(robot.prepare.call_count, 2)
        self.assertEqual(robot.save.call_count, 2)
        self.assertEqual(sheet.claim.call_count, 2)
        self.assertEqual(sheet.status.call_count, 2)
        self.assertTrue(all(call.args[1] == 'Sim' for call in sheet.status.call_args_list))
        events = list(window.events.queue)
        self.assertFalse(any(kind == 'review' for kind, _ in events))
        self.assertIn(('run_completed', (2, 0, False)), events)
        with patch('main.messagebox.showinfo') as notice:
            window.poll()
        self.assertIn('Linhas importadas: 2', notice.call_args.args[1])

    def test_uncertain_record_is_not_repeated_and_completion_explains_skip(self):
        window = self.window
        window.settings = {'Planilha': 'https://docs.google.com/spreadsheets/d/ficticio/edit', 'Credenciais Google': 'ficticio.json'}
        window.professionals = {'fisioterapeuta': {'name': 'Responsável fictício', 'login': 'ficticio'}}
        window.tree.selection_set('test-0', 'test-1')
        robot, sheet, ledger = Mock(), Mock(), Mock()
        ledger.get.side_effect = lambda key: 'Conferir' if key.endswith(':test-0') else ''
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            (root / 'config').mkdir()
            (root / 'config/pacientes.json').write_text(json.dumps({'Paciente fictício': {'attendance': '123', 'chart': '456'}}), encoding='utf-8')
            with patch('main.ROOT', root), patch('main.Tasy', return_value=robot), patch('main.Sheets', return_value=sheet), patch('main.Ledger', return_value=ledger), patch('main.ledger_path', return_value='unused'), patch.object(window, 'launch', side_effect=lambda task: task()):
                window.run()
        self.assertEqual(robot.save.call_count, 1)
        self.assertEqual(sheet.claim.call_count, 1)
        self.assertEqual(sheet.claim.call_args.args[0].key, 'test-1')
        self.assertFalse(any(call.args[0].endswith(':test-0') for call in ledger.set.call_args_list))
        with patch('main.messagebox.showinfo') as notice:
            window.poll()
        self.assertIn('Linhas importadas: 1', notice.call_args.args[1])
        self.assertIn('Gravação anterior incerta', notice.call_args.args[1])

    def test_only_one_import_button_and_no_obsolete_controls(self):
        from tkinter import ttk
        labels = []
        def visit(widget):
            if isinstance(widget, ttk.Button):
                labels.append(widget.cget('text'))
            for child in widget.winfo_children():
                visit(child)
        visit(self.window)
        self.assertEqual(labels.count('Importar linhas selecionadas'), 1)
        for label in ('Executar selecionados', 'Diagnosticar Tasy', 'Encerrar diagnóstico', 'Interromper após etapa atual', 'Confirmar salvamento'):
            self.assertNotIn(label, labels)
