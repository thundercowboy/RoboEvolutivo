import json
import unittest
from pathlib import Path
from app.core import Record, normal, parse
from app.tasy import Tasy, REQUIRED, editor_text


HTML = '''<!doctype html><html><body>
<span id="user">Responsável Teste</span>
<button id="pep">PEP</button><button id="category">Categoria</button>
<button id="patient">Paciente Teste (123)</button><button id="notes">Notas clínicas</button>
<span id="patient_header">Paciente Teste</span><span id="attendance_header">123</span><span id="chart_header">456</span>
<button id="add">Adicionar</button><input id="date">
<input id="professional" value="Responsável Teste">
<select id="note_type"><option>---</option><option>Evolução Fisioterapia Unimed Lar</option></select>
<div id="content" contenteditable="true"></div><button id="close_pep">Fechar</button>
<button id="save" onclick="document.querySelector('#ngdialog3').style.display='block';">Salvar</button>
<div id="ngdialog3" style="display:none"><button id="release" onclick="
const persisted = document.createElement('div'); persisted.id='persisted';
persisted.innerText = '123\\n' + document.querySelector('#date').value + '\\n' + document.querySelector('#professional').value;
persisted.onclick = () => {document.querySelector('#saved_content').innerText = document.querySelector('#content').innerText;};
document.body.appendChild(persisted); document.querySelector('#save').style.display='none'; document.querySelector('#ngdialog3').style.display='none';">Liberar</button></div>
<div id="saved_content"></div>
</body></html>'''


class BrowserFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.engine = sync_playwright().start()
        cls.browser = cls.engine.chromium.launch(channel='chromium', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.engine.stop()

    def setUp(self):
        self.robot = Tasy.__new__(Tasy)
        self.robot.config = {}
        self.robot.selectors = {key: '#' + key for key in REQUIRED}
        self.robot.selectors['saved_note'] = '#persisted:has-text({date}):has-text({professional})'
        self.robot.mappings = {normal('Paciente Teste'): {'attendance': '123', 'chart': '456', 'display': 'Paciente Teste (123)'}}
        self.robot.page = self.browser.new_page()
        self.robot.page.set_default_timeout(5000)
        self.robot.page.set_content(HTML)
        self.record = Record('teste', 'Paciente Teste', '09/10/2026 10:30:00', 'fisioterapeuta', 'Texto de teste\nSegunda linha com acentuação.', 'Autor diferente / 123', '')
        self.user = {'name': 'Responsável Teste'}

    def tearDown(self):
        self.robot.page.close()

    def test_complete_visual_flow(self):
        self.robot.prepare(self.record, self.user)
        self.assertEqual(self.robot.page.locator('#date').input_value(), self.record.date)
        self.robot.save(self.record, self.user)
        self.assertEqual(self.record.content, self.robot.page.locator('#saved_content').inner_text())
        self.assertFalse(self.robot.page.locator('#ngdialog3').is_visible())

    def test_each_note_saves_releases_closes_and_reopens_pep(self):
        from dataclasses import replace
        config = json.loads((Path(__file__).resolve().parents[1] / 'config/tasy.json').read_text(encoding='utf-8'))
        self.robot.selectors['release'] = config['selectors']['release']
        self.robot.page.evaluate('''() => {
            window.navigation = [];
            document.querySelector('#pep').onclick = () => window.navigation.push('abrir');
            document.querySelector('#close_pep').onclick = () => window.navigation.push('fechar');
            document.querySelector('#add').onclick = () => document.querySelector('#save').style.display = 'block';
        }''')
        for index, record in enumerate([self.record, replace(self.record, key='segunda', date='09/10/2026 10:31:00', content='Segunda evolução fictícia')]):
            if index:
                self.robot.page.locator('#ngdialog3').evaluate('(e) => e.id = "ngdialog44"')
                for key in ('save', 'release'):
                    button = self.robot.page.locator('#' + key)
                    button.evaluate('(e, handler) => e.setAttribute("onclick", handler)', button.get_attribute('onclick').replace('ngdialog3', 'ngdialog44'))
            self.robot.prepare(record, self.user)
            self.robot.save(record, self.user)
            self.assertFalse(self.robot.page.locator('[id^="ngdialog"]').is_visible())
            self.assertEqual(self.robot.text('saved_content'), record.content)
        self.assertEqual(self.robot.page.evaluate('window.navigation'), ['abrir', 'fechar', 'abrir', 'fechar'])

    def test_two_patients_reuse_expanded_category_without_collapsing_it(self):
        from dataclasses import replace
        self.robot.selectors['patient'] = 'text={patient}'
        self.robot.mappings[normal('Paciente Segundo')] = {'attendance': '789', 'chart': '987'}
        self.robot.page.evaluate('''() => {
            window.categoryClicks = 0; window.pepCloses = 0;
            const panel = document.createElement('div'); panel.id = 'patient-list'; panel.style.display = 'none';
            const patients = [['Paciente Teste', '123', '456'], ['Paciente Segundo', '789', '987']];
            for (const [name, attendance, chart] of patients) {
                const button = document.createElement('button');
                button.textContent = name + ' (' + attendance + ')';
                button.onclick = () => {
                    document.querySelector('#patient_header').textContent = name;
                    document.querySelector('#attendance_header').textContent = attendance;
                    document.querySelector('#chart_header').textContent = chart;
                }; panel.appendChild(button);
            }
            document.querySelector('#patient').replaceWith(panel);
            document.querySelector('#category').onclick = () => {
                window.categoryClicks++;
                panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
            };
            document.querySelector('#close_pep').onclick = () => window.pepCloses++;
            document.querySelector('#add').onclick = () => document.querySelector('#save').style.display = 'block';
            document.querySelector('#release').onclick = () => {
                const row = document.createElement('div'); row.id = 'persisted';
                row.innerText = document.querySelector('#attendance_header').innerText + '\\n' + document.querySelector('#date').value + '\\n' + document.querySelector('#professional').value;
                row.onclick = () => document.querySelector('#saved_content').innerText = document.querySelector('#content').innerText;
                document.body.appendChild(row);
                document.querySelector('#save').style.display = 'none';
                document.querySelector('#ngdialog3').style.display = 'none';
            };
        }''')
        second = replace(self.record, key='segunda', patient='Paciente Segundo', date='09/10/2026 10:31:00', content='Texto do segundo paciente')
        for record in (self.record, second):
            self.robot.prepare(record, self.user)
            self.robot.save(record, self.user)
            self.assertEqual(self.robot.text('saved_content'), record.content)
        self.assertEqual(self.robot.page.evaluate('window.categoryClicks'), 1)
        self.assertEqual(self.robot.page.evaluate('window.pepCloses'), 2)

    def test_forms_evolution_and_author_are_both_saved(self):
        record = parse(['10/15/2026 11:00', 'Paciente Teste', '10/09/2026 10:30', 'Fisioterapeuta', 'Evolução fictícia.\nSegunda linha.', 'Autor fictício / Conselho 123', ''], list(range(7)))
        self.robot.prepare(record, self.user)
        expected = 'Evolução fictícia.\nSegunda linha.\nAutor fictício / Conselho 123'
        self.assertEqual(self.robot.text('content'), expected)
        self.robot.save(record, self.user)
        self.assertEqual(self.robot.text('saved_content'), expected)

    def test_existing_row_blocks_save_and_release(self):
        self.robot.prepare(self.record, self.user)
        self.robot.page.evaluate('''() => {
          const row = document.createElement('div'); row.id = 'persisted';
          row.innerText = '123 09/10/2026 10:30:00 Responsável Teste';
          document.body.appendChild(row);
        }''')
        with self.assertRaises(ValueError):
            self.robot.save(self.record, self.user)
        self.assertFalse(self.robot.save_started)
        self.assertFalse(self.robot.page.locator('#ngdialog3').is_visible())

    def test_real_grid_selector_matches_cells_and_ignores_row_position(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config/tasy.json').read_text(encoding='utf-8'))
        self.robot.selectors['saved_note'] = config['selectors']['saved_note']
        self.robot.page.evaluate('''() => {
            const row = document.createElement('div');
            row.className = 'ui-widget-content slick-row odd selected-row';
            row.dataset.rowIdx = '99';
            row.innerHTML = '<div class="slick-cell l1 r1"><span>123</span></div>' +
              '<div class="slick-cell l2 r2"><span>\\u202a09/10/2026 10:30:00\\u202c</span></div>' +
              '<div class="slick-cell l3 r3"><span>Responsável Teste</span></div>' +
              '<div class="slick-cell l6 r6"><span>Evolução Fisioterapia Unimed Lar</span></div>';
            document.body.appendChild(row);
        }''')
        args = dict(attendance='123', date=self.record.date, professional=self.user['name'], note_type='Evolução Fisioterapia Unimed Lar')
        self.assertEqual(self.robot.locator('saved_note', **args).count(), 1)
        for key, value in [('attendance', '12'), ('date', '09/10/2026 10:31:00'), ('professional', 'Outro responsável'), ('note_type', 'Evolução Médica')]:
            with self.subTest(field=key):
                self.assertEqual(self.robot.locator('saved_note', **{**args, key: value}).count(), 0)

    def test_user_name_ignores_case_and_visual_spaces_but_rejects_partial_name(self):
        self.robot.selectors['user'] = 'text={professional}'
        self.robot.page.locator('#user').evaluate('(e) => e.textContent = "\\u200eRESPONSÁVEL   TESTE\\u200f"')
        self.assertEqual(self.robot.locator('user', professional='Responsável Teste').count(), 1)
        self.assertEqual(self.robot.locator('user', professional='Responsável').count(), 0)
        self.assertEqual(self.robot.locator('user', professional='Outro Teste').count(), 0)

    def test_account_identity_is_not_confused_with_note_signature(self):
        self.robot.selectors['user'] = 'text={professional}'
        self.robot.selectors['user_menu'] = 'text={professional}'
        self.robot.remember_user_identity(self.user)
        self.robot.page.evaluate('''() => {
            const signature = document.createElement('p');
            signature.textContent = 'Responsável Teste';
            document.body.appendChild(signature);
        }''')
        self.assertEqual(self.robot.locator('user', professional=self.user['name']).get_attribute('id'), 'user')
        self.assertEqual(self.robot.locator('user_menu', professional=self.user['name']).get_attribute('id'), 'user')
        self.robot.page.locator('#user').evaluate('(e) => e.textContent = "Outro usuário"')
        self.assertEqual(self.robot.locator('user', professional=self.user['name']).count(), 0)

    def setup_logout_page(self, menu_open=False):
        from unittest.mock import Mock
        self.robot.selectors['user'] = 'text={professional}'
        self.robot.selectors['user_menu'] = 'text={professional}'
        self.robot.selectors['logout'] = 'text=/^\\s*sair\\s*$/i'
        self.robot.selectors['login'] = '#login'
        self.robot.selectors['password'] = '#password'
        self.robot.current_professional = self.user['name']
        self.robot.context = Mock()
        self.robot.user_identity_selector = '#header-antigo'
        self.robot.page.set_content('''<div style="display:none">Sair</div>
          <button id="account" onclick="const m=document.querySelector('#menu'); m.style.display=m.style.display==='none'?'block':'none';">Responsável Teste</button>
          <div id="menu" style="display:none"><button onclick="document.querySelector('#login').style.display='block'; document.querySelector('#password').style.display='block'; document.querySelector('#menu').style.display='none';"> Sair </button></div>
          <input id="login" style="display:none"><input id="password" style="display:none">''')
        if menu_open:
            self.robot.page.locator('#menu').evaluate('(e) => e.style.display="block"')
        return self.robot.context

    def test_logout_reacquires_header_and_confirms_login_screen(self):
        context = self.setup_logout_page()
        self.robot.logout()
        context.close.assert_called_once()
        self.assertIsNone(self.robot.context)
        self.assertTrue(self.robot.page.locator('#login').is_visible())

    def test_logout_does_not_close_an_already_open_account_menu(self):
        context = self.setup_logout_page(menu_open=True)
        self.robot.logout()
        context.close.assert_called_once()

    def test_logout_accepts_native_exit_confirmation(self):
        context = self.setup_logout_page(menu_open=True)
        self.robot.page.locator('#menu button').evaluate('''e => {
            const previous = e.onclick;
            e.onclick = () => {if (confirm('Deseja sair do sistema?')) previous();};
        }''')
        self.robot.logout()
        context.close.assert_called_once()

    def test_logout_reopens_login_route_when_landing_page_does_not_redirect(self):
        context = self.setup_logout_page(menu_open=True)
        self.robot.config.update(url='https://tasy-ficticio.invalid/#/login', logout_timeout_ms=500)
        self.robot.page.locator('#menu button').evaluate('(e) => e.onclick = () => document.querySelector("#menu").style.display="none"')
        self.robot.page.route('https://tasy-ficticio.invalid/**', lambda route: route.fulfill(content_type='text/html', body='<input id="login"><input id="password">'))
        self.robot.logout()
        context.close.assert_called_once()
        self.assertTrue(self.robot.page.locator('#password').is_visible())

    def test_logout_blocks_next_account_if_login_route_stays_authenticated(self):
        from unittest.mock import Mock
        context = self.setup_logout_page(menu_open=True)
        self.robot.browser = Mock()
        self.robot.config.update(url='https://tasy-ficticio.invalid/#/login', logout_timeout_ms=100)
        self.robot.page.locator('#menu button').evaluate('(e) => e.onclick = () => document.querySelector("#menu").style.display="none"')
        self.robot.page.route('https://tasy-ficticio.invalid/**', lambda route: route.fulfill(content_type='text/html', body='<span>Responsável Teste</span> Página de módulos'))
        with self.assertRaisesRegex(ValueError, 'sessão ativa'):
            self.robot.login({'name': 'Outra pessoa', 'login': 'outro'})
        context.close.assert_not_called()
        self.robot.browser.new_context.assert_not_called()

    def test_failed_logout_blocks_start_of_next_account(self):
        from unittest.mock import Mock
        self.setup_logout_page(menu_open=True)
        self.robot.page.locator('#menu button').evaluate('(e) => e.textContent="Outra ação"')
        self.robot.page.set_default_timeout(100)
        self.robot.browser = Mock()
        with self.assertRaisesRegex(ValueError, 'Sair'):
            self.robot.login({'name': 'Outra pessoa', 'login': 'outro'})
        self.robot.browser.new_context.assert_not_called()

    def test_user_timeout_identifies_expected_full_name(self):
        self.robot.selectors['user'] = 'text={professional}'
        self.robot.page.set_default_timeout(100)
        with self.assertRaisesRegex(ValueError, 'responsavel_tasy'):
            self.robot.check('user', professional='Outro Responsável Completo')

    def test_patient_text_can_be_nested_and_omit_final_parenthesis(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config/tasy.json').read_text(encoding='utf-8'))
        self.robot.selectors['patient'] = config['selectors']['patient']
        self.robot.page.set_content('<div id="title_1_4_2"><span>PACIENTE TESTE (123</span></div><div id="title_1_4_3"><span>PACIENTE TESTE (1234)</span></div>')
        loc = self.robot.check('patient', patient='Paciente Teste (123)', attendance='123')
        self.assertEqual(loc.inner_text(), 'PACIENTE TESTE (123')
        self.assertEqual(self.robot.locator('patient', patient='Paciente Teste (12)', attendance='12').count(), 0)
        self.robot.page.locator('#title_1_4_2 span').evaluate('(e) => e.textContent = "PACIENTE TESTE (123)"')
        self.assertEqual(self.robot.locator('patient', patient='Paciente Teste (123)', attendance='123').count(), 1)

    def test_wrong_patient_attendance_reports_candidate_without_clicking(self):
        self.robot.selectors['patient'] = 'text={patient}'
        self.robot.page.set_default_timeout(100)
        self.robot.page.set_content('<div id="title_1_4_2"><span>Paciente Teste (999)</span></div>')
        with self.assertRaisesRegex(ValueError, 'Atendimentos encontrados para esse nome: 999'):
            self.robot.check('patient', patient='Paciente Teste (123)', attendance='123')

    def test_tree_patient_ignores_same_text_outside_tree(self):
        self.robot.selectors['patient'] = 'tree_text={patient}'
        self.robot.page.set_content('<div id="title_1_4_2"><span>Paciente Teste (123)</span></div><w-person-bar>Paciente Teste (123)</w-person-bar>')
        found = self.robot.check('patient', patient='Paciente Teste (123)', attendance='123')
        self.assertEqual(found.get_attribute('id'), 'title_1_4_2')
        self.robot.page.locator('body').evaluate('''e => e.insertAdjacentHTML('beforeend', '<div id="title_2_4_2">Paciente Teste (123)</div>')''')
        with self.assertRaisesRegex(ValueError, 'Seletor ambíguo: patient'):
            self.robot.check('patient', patient='Paciente Teste (123)', attendance='123')

    def test_patient_ignores_hidden_duplicate_but_rejects_two_visible_matches(self):
        self.robot.selectors['patient'] = 'text={patient}'
        self.robot.page.set_content('<div style="display:none">Paciente Teste (123)</div><div id="visible">Paciente Teste (123)</div>')
        found = self.robot.check('patient', patient='Paciente Teste (123)', attendance='123')
        self.assertEqual(found.get_attribute('id'), 'visible')
        self.robot.page.evaluate('''() => {
            const duplicate = document.createElement('div');
            duplicate.textContent = 'Paciente Teste (123)';
            document.body.appendChild(duplicate);
        }''')
        with self.assertRaisesRegex(ValueError, 'Seletor ambíguo: patient'):
            self.robot.check('patient', patient='Paciente Teste (123)', attendance='123')

    def test_patient_replaced_after_visibility_check_is_resolved_again_for_click(self):
        from unittest.mock import patch
        self.robot.selectors['patient'] = 'text={patient}'
        self.robot.page.set_content('<button id="old">Paciente Teste (123)</button>')
        original = self.robot.locator('patient', patient='Paciente Teste (123)', attendance='123')
        page = self.robot.page
        class RerenderedLocator:
            def wait_for(self, **kwargs):
                original.wait_for(**kwargs)
                page.evaluate('''() => {
                    document.querySelector('#old').remove();
                    setTimeout(() => {
                        const button = document.createElement('button');
                        button.textContent = 'Paciente Teste (123)';
                        button.onclick = () => document.body.dataset.clicked = 'true';
                        document.body.appendChild(button);
                    }, 150);
                }''')

            def __getattr__(self, name):
                return getattr(original, name)
        with patch.object(self.robot, 'locator', return_value=RerenderedLocator()):
            self.robot.check('patient', patient='Paciente Teste (123)', attendance='123').click()
        self.assertEqual(page.locator('body').get_attribute('data-clicked'), 'true')

    def test_saved_editor_with_dynamic_id_and_invisible_characters(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config/tasy.json').read_text(encoding='utf-8'))
        self.robot.selectors['saved_content'] = config['selectors']['saved_content']
        self.robot.page.locator('#saved_content').evaluate('''e => {
            e.id = 'DS_EVOLUCAO999_0';
            e.className = 'wrichedit-editor';
            e.setAttribute('role', 'textbox');
            e.setAttribute('contenteditable', 'false');
        }''')
        self.robot.prepare(self.record, self.user)
        self.robot.page.locator('#release').evaluate('''button => {
            button.onclick = () => {
                const row = document.createElement('div'); row.id = 'persisted';
                row.innerText = '123 09/10/2026 10:30:00 Responsável Teste';
                row.onclick = () => {
                    document.querySelector('#DS_EVOLUCAO999_0').innerText = '\\u200b' + document.querySelector('#content').innerText + '\\u200b\\u00a0';
                };
                document.body.appendChild(row);
                document.querySelector('#save').style.display = 'none';
                document.querySelector('#ngdialog3').style.display = 'none';
            };
        }''')
        self.robot.save(self.record, self.user)
        self.assertEqual(editor_text(self.robot.text('saved_content')), editor_text(self.record.content))

    def test_wrong_patient_blocks_fill(self):
        self.robot.page.locator('#chart_header').evaluate('(e) => e.textContent = "999"')
        with self.assertRaises(ValueError):
            self.robot.prepare(self.record, self.user)
        self.assertEqual(self.robot.page.locator('#content').inner_text(), '')

    def test_diagnostic_can_fill_but_cannot_save(self):
        self.robot.diagnostic = True
        self.robot.prepare(self.record, self.user)
        self.assertEqual(self.robot.text('content'), self.record.content)
        with self.assertRaisesRegex(ValueError, 'não permite'):
            self.robot.save(self.record, self.user)
        self.assertFalse(self.robot.page.locator('#ngdialog3').is_visible())
        self.assertEqual(self.robot.page.locator('#persisted').count(), 0)

    def test_diagnostic_reads_missing_chart_before_adding(self):
        self.robot.diagnostic = True
        self.robot.mappings[normal(self.record.patient)]['chart'] = ''
        reports = []
        self.robot.reporter = lambda *args: reports.append(args)
        self.robot.page.locator('#add').evaluate('(button) => {button.onclick = () => button.dataset.clicked = "true";}')
        with self.assertRaisesRegex(ValueError, 'Prontuário pendente'):
            self.robot.prepare(self.record, self.user)
        self.assertIsNone(self.robot.page.locator('#add').get_attribute('data-clicked'))
        self.assertEqual(self.robot.text('content'), '')
        self.assertTrue(any(state == 'Pendente' and '456' in detail for _, state, detail in reports))

    def test_responsible_changed_blocks_save(self):
        self.robot.prepare(self.record, self.user)
        self.robot.page.locator('#professional').fill('Outro responsável')
        with self.assertRaises(ValueError):
            self.robot.save(self.record, self.user)
        self.assertFalse(self.robot.save_started)

    def test_professional_mismatch_reports_both_names(self):
        self.robot.page.locator('#professional').fill('Outro Responsável Completo')
        with self.assertRaisesRegex(ValueError, 'Esperado: Responsável Teste.*Encontrado: Outro Responsável Completo'):
            self.robot.verify_professional(self.user)

    def test_professional_ignores_invisible_editor_characters(self):
        self.robot.page.locator('#professional').fill('\u200eRESPONSÁVEL   TESTE\u200f')
        self.robot.verify_professional(self.user)

    def test_disabled_professional_is_read_after_async_population(self):
        self.robot.page.locator('#professional').evaluate('''e => {
            e.disabled = true;
            e.value = 'Carregando';
            setTimeout(() => {e.value = 'Responsável Teste';}, 300);
        }''')
        self.robot.verify_professional(self.user)
        self.assertTrue(self.robot.page.locator('#professional').is_disabled())
        self.assertEqual(self.robot.text('professional'), 'Responsável Teste')

    def test_editable_content_dynamic_id_does_not_target_readonly_or_hidden_editor(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config/tasy.json').read_text(encoding='utf-8'))
        self.robot.selectors['content'] = config['selectors']['content']
        self.robot.page.locator('#content').evaluate('''e => {
            e.id = 'DS_EVOLUCAO12345_0';
            e.className = 'wrichedit-editor';
            e.setAttribute('role', 'textbox');
            e.style.minHeight = '100px';
        }''')
        self.robot.page.evaluate('''() => {
            const readonly = document.createElement('div');
            readonly.id = 'DS_EVOLUCAO888_0'; readonly.className = 'wrichedit-editor';
            readonly.setAttribute('role', 'textbox'); readonly.contentEditable = 'false';
            readonly.innerText = 'Nota salva fictícia'; document.body.appendChild(readonly);
            const hidden = readonly.cloneNode(true); hidden.id = 'DS_EVOLUCAO777_0';
            hidden.contentEditable = 'true'; hidden.style.display = 'none'; document.body.appendChild(hidden);
        }''')
        editor = self.robot.check('content')
        self.assertEqual(editor.count(), 1)
        editor.fill(self.record.content)
        self.assertEqual(self.robot.text('content'), self.record.content)
        self.assertEqual(self.robot.page.locator('#DS_EVOLUCAO888_0').inner_text(), 'Nota salva fictícia')

    def test_content_timeout_describes_editable_editor(self):
        self.robot.selectors['content'] = '#editor-inexistente'
        self.robot.page.set_default_timeout(100)
        with self.assertRaisesRegex(ValueError, 'área editável'):
            self.robot.check('content')

    def test_content_changed_blocks_save(self):
        self.robot.prepare(self.record, self.user)
        self.robot.page.locator('#content').fill('Texto modificado')
        with self.assertRaises(ValueError):
            self.robot.save(self.record, self.user)
        self.assertFalse(self.robot.save_started)


class ConfigurationTest(unittest.TestCase):
    def test_editor_formatting_does_not_hide_text_changes(self):
        self.assertEqual(editor_text('\u200bTexto\u00a0original\n\nAssinatura\u200b'), editor_text('Texto original\nAssinatura'))
        self.assertNotEqual(editor_text('Dose: 10 mg'), editor_text('Dose: 100 mg'))
        self.assertNotEqual(editor_text('Sem alteração'), editor_text('Com alteração'))
        self.assertNotEqual(editor_text('avó'), editor_text('avo'))

    def test_unmapped_site_is_blocked(self):
        with self.assertRaises(ValueError):
            Tasy(Path(__file__).resolve().parents[1] / 'config/tasy.json', {})
