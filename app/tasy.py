import json
import re
from .core import normal, TYPES


REQUIRED = ['login', 'password', 'enter', 'user', 'pep', 'category', 'patient', 'notes', 'patient_header', 'attendance_header', 'chart_header', 'add', 'date', 'professional', 'note_type', 'content', 'save', 'release', 'saved_note', 'saved_content', 'close_pep', 'user_menu', 'logout']


def editor_text(value):
    """Compare text while ignoring editor formatting, never case or accents."""
    invisible = '\u200b\ufeff\u2060\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069'
    return ' '.join(value.translate(str.maketrans('', '', invisible)).split())


class Tasy:
    def __init__(self, path, mappings, *, diagnostic=False, allow_import=False, reporter=None, cancel=None):
        with open(path, encoding='utf-8') as handle:
            self.config = json.load(handle)
        self.selectors = self.config['selectors']
        self.patient_context = {}
        self.diagnostic = diagnostic
        self.reporter = reporter
        self.cancel = cancel
        missing = [key for key in REQUIRED if not self.selectors.get(key)]
        if missing or (not self.config.get('validated') and not diagnostic and not allow_import):
            raise ValueError('Mapeamento Tasy ainda não validado. Configure tasy.json: ' + ', '.join(missing))
        if not all('{' + name + '}' in self.selectors['saved_note'] for name in ('attendance', 'date', 'professional', 'note_type')):
            raise ValueError('saved_note precisa localizar a linha por atendimento, data, profissional e tipo.')
        self.mappings = mappings
        self.save_started = False

    def report(self, step, status='Em andamento', detail=''):
        self.last_step = step
        if getattr(self, 'cancel', None) and self.cancel.is_set():
            raise ValueError('Operação interrompida pelo usuário.')
        if getattr(self, 'reporter', None):
            self.reporter(step, status, detail)

    def check(self, key, **values):
        self.report('Seletor: ' + key, detail=('Procurando: ' + values['patient']) if key == 'patient' and values.get('patient') else '')
        loc = self.locator(key, **values)
        try:
            loc.wait_for(state='visible')
        except Exception as error:
            if type(error).__name__ == 'TimeoutError' and key == 'user':
                expected = values.get('professional', '')
                raise ValueError(
                    f'Página inicial aberta, mas o nome completo esperado não foi localizado: {expected}. '
                    'Confira a coluna responsavel_tasy em DB/profissionais.txt: ela precisa conter o nome completo exibido no topo do Tasy. '
                    'Se o nome já estiver correto, capture o outerHTML desse nome para ajustar o seletor.'
                ) from None
            if type(error).__name__ == 'TimeoutError' and key == 'patient':
                expected = values.get('patient', '')
                match = re.fullmatch(r'(.*?)\s*\((\d+)\)?', editor_text(expected))
                found = set()
                if match:
                    for value in self.page.locator('[id^="title_"]:visible').all_text_contents():
                        candidate = re.fullmatch(r'(.*?)\s*\((\d+)\)?', editor_text(value))
                        if candidate and normal(candidate[1]) == normal(match[1]):
                            found.add(candidate[2])
                detail = (' Atendimentos encontrados para esse nome: ' + ', '.join(sorted(found)) + '.') if found else ''
                raise ValueError(
                    f'Paciente esperado não localizado: {expected}.' + detail +
                    ' Confira o texto na categoria aberta e o cadastro em Pacientes. Nenhum paciente foi selecionado.'
                ) from None
            if type(error).__name__ == 'TimeoutError' and key == 'content':
                raise ValueError(
                    'Editor de conteúdo em modo de edição não localizado. '
                    'O ID numérico não é mais fixo. Confira se o formulário de inclusão está aberto '
                    'e capture o outerHTML da área editável, não do conteúdo de uma nota já salva. '
                    'Se estiver dentro de iframe, será necessário mapear esse frame.'
                ) from None
            raise
        # wait_for is strict: it already requires exactly one matching element.
        # A separate count after it races with Angular replacing the tree node.
        # The subsequent click/fill re-resolves this locator and waits again.
        self.report('Seletor: ' + key, 'OK', 'Um elemento visível encontrado.')
        return loc

    def start(self):
        import os
        from .storage import ROOT
        if (ROOT / 'browsers').is_dir():
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(ROOT / 'browsers')
        from playwright.sync_api import sync_playwright
        self.engine = sync_playwright().start()
        self.browser = self.engine.chromium.launch(headless=False)
        self.context = None

    def locator(self, key, **values):
        # JSON quoting permits names, dates and line breaks inside text selectors.
        values = {**getattr(self, 'patient_context', {}), **values}
        args = {k: json.dumps(' '.join(str(v).split()), ensure_ascii=False) for k, v in values.items()}
        selector = self.selectors[key]
        for k, v in args.items():
            selector = selector.replace('{' + k + '}', v)
        frame = self.config.get('frames', {}).get(key)
        scope = self.page.frame_locator(frame) if frame else self.page
        parameter = 'patient' if key == 'patient' else 'professional'
        tree_patient = key == 'patient' and self.selectors[key] == 'tree_text={patient}'
        if key in ('user', 'user_menu', 'patient') and (self.selectors[key] == 'text={' + parameter + '}' or tree_patient):
            # Exact whole name, ignoring case and visual whitespace only.
            # Never accept a first-name substring as proof of account identity.
            name = str(values.get(parameter, '')).strip()
            if not name:
                raise ValueError('Nome completo para identificação não informado: ' + key)
            whitespace = r'[\s\u200b\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069]*'
            between = r'[\s\u200b\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069]+'
            if key == 'patient':
                match = re.fullmatch(r'(.*?)\s*\((\d+)\)?', editor_text(name))
                if not match:
                    raise ValueError('Identificação do paciente precisa conter nome completo e atendimento entre parênteses.')
                pattern = whitespace + between.join(re.escape(part) for part in match[1].split()) + whitespace + r'\(' + whitespace + re.escape(match[2]) + whitespace + r'\)?' + whitespace
            else:
                pattern = whitespace + between.join(re.escape(part) for part in name.split()) + whitespace
            loc = scope.get_by_text(re.compile('^' + pattern + '$', re.IGNORECASE))
            if tree_patient:
                # Match the tree label itself, including nested spans. A page-wide
                # text lookup can also match the patient bar or another panel.
                loc = scope.locator('[id^="title_"]').filter(has_text=re.compile('^' + pattern + '$', re.IGNORECASE))
            if key in ('user', 'user_menu'):
                identity_selector = getattr(self, 'user_identity_selector', None)
                if identity_selector:
                    loc = scope.locator(identity_selector).filter(has_text=re.compile('^' + pattern + '$', re.IGNORECASE))
                loc = loc.filter(visible=True)
            if key == 'patient':
                # Angular may keep a hidden copy of the previous tree view.
                loc = loc.filter(visible=True)
        else:
            loc = scope.locator(selector)
        if key == 'logout':
            loc = loc.filter(visible=True)
        if loc.count() > 1:
            raise ValueError('Seletor ambíguo: ' + key + '. Mais de um elemento correspondente; nenhum foi escolhido.')
        return loc

    def logout(self):
        self.logout_dialog_rejected = False
        def handle_dialog(dialog):
            message = normal(dialog.message)
            if dialog.type in ('confirm', 'alert') and re.search(r'\bsair\b|encerrar.*sess|\blogout\b|log\s*out|sign\s*out', message):
                dialog.accept()
            else:
                self.logout_dialog_rejected = True
                dialog.dismiss()
        page = self.page
        page.on('dialog', handle_dialog)
        try:
            self._logout_flow()
        finally:
            page.remove_listener('dialog', handle_dialog)

    def _logout_flow(self):
        self.report('Encerrar sessão')
        try:
            exit_option = self.locator('logout')
            if not exit_option.is_visible():
                menu = self.locator('user_menu', professional=self.current_professional)
                if not menu.count() or not menu.is_visible():
                    # Closing PEP may rebuild the header. Reacquire only an
                    # unambiguous full account name, never a signature fallback.
                    self.user_identity_selector = None
                    self.check('user', professional=self.current_professional)
                    if normal(editor_text(self.text('user', professional=self.current_professional))) != normal(editor_text(self.current_professional)):
                        raise ValueError('Usuário diverge do esperado ao encerrar a sessão.')
                    self.remember_user_identity({'name': self.current_professional})
                    menu = self.locator('user_menu', professional=self.current_professional)
                menu.click()
            # Do not toggle a menu that is already open; wait for its visible item.
            self.check('logout').click()
            if getattr(self, 'logout_dialog_rejected', False):
                raise ValueError('Apareceu uma confirmação de saída não reconhecida. A troca de conta foi interrompida; informe o texto dessa confirmação.')
        except Exception as error:
            if type(error).__name__ == 'TimeoutError':
                raise ValueError('Não foi possível abrir o menu do usuário ou localizar Sair. A troca de conta foi interrompida; envie o seletor ou outerHTML do botão Sair visível.') from None
            raise
        wait_ms = self.config.get('logout_timeout_ms', 5000)
        try:
            self.locator('login').wait_for(state='visible', timeout=wait_ms)
            self.locator('password').wait_for(state='visible', timeout=wait_ms)
        except Exception as error:
            if type(error).__name__ != 'TimeoutError':
                raise
            self.report('Retorno à entrada', detail='Reabrindo a rota de login após clicar em Sair.')
            try:
                self.page.goto(self.config['url'], wait_until='domcontentloaded')
                self.locator('login').wait_for(state='visible', timeout=wait_ms)
                self.locator('password').wait_for(state='visible', timeout=wait_ms)
                old_user = self.locator('user', professional=self.current_professional)
                if old_user.count() and old_user.is_visible():
                    raise ValueError('A sessão anterior ainda aparece ativa após Sair. A próxima conta não foi iniciada.')
            except Exception as retry_error:
                if type(retry_error).__name__ == 'TimeoutError':
                    raise ValueError('Sair foi acionado e a rota de entrada foi reaberta, mas os campos de login e senha não apareceram. O Tasy pode ter mantido a sessão ativa; a próxima conta não foi iniciada.') from None
                raise
        self.context.close()
        self.context = None
        self.user_identity_selector = None
        self.report('Encerrar sessão', 'OK', 'Saída confirmada pela tela de login.')

    def remember_user_identity(self, user):
        # Capture the unique account-name element immediately after login,
        # before the same name can appear in notes, signatures or table rows.
        self.user_identity_selector = self.locator('user', professional=user['name']).evaluate('''element => {
            const path = [];
            for (let node = element; node && node.nodeType === 1; node = node.parentElement) {
                if (node.id) {path.unshift('#' + CSS.escape(node.id)); break;}
                let index = 1;
                for (let sibling = node.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
                    if (sibling.tagName === node.tagName) index++;
                }
                path.unshift(node.tagName.toLowerCase() + ':nth-of-type(' + index + ')');
            }
            return path.join(' > ');
        }''')

    def text(self, key, **values):
        loc = self.locator(key, **values)
        loc.wait_for(state='visible')
        return loc.input_value() if loc.evaluate('(e) => ["INPUT","TEXTAREA"].includes(e.tagName)') else loc.inner_text()

    def verify_professional(self, user):
        self.report('Conferência do profissional')
        expected = editor_text(user['name'])
        loc = self.locator('professional')
        loc.wait_for(state='visible')
        actual = editor_text(self.text('professional'))
        # Disabled inputs remain readable. Wait for Angular to finish assigning
        # the full value, even if an intermediate nonempty value was displayed.
        if normal(actual) != normal(expected) and loc.evaluate('(e) => ["INPUT", "TEXTAREA"].includes(e.tagName)'):
            from playwright.sync_api import expect
            invisible_space = r'[\s\u200b\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069]*'
            between = r'[\s\u200b\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069]+'
            pattern = '^' + invisible_space + between.join(re.escape(part) for part in expected.split()) + invisible_space + '$'
            try:
                expect(loc).to_have_value(re.compile(pattern, re.IGNORECASE), timeout=5000)
            except AssertionError:
                pass
            actual = editor_text(self.text('professional'))
        detail = f'Esperado: {expected} | Encontrado: {actual or "(vazio)"}'
        if normal(actual) != normal(expected):
            self.report('Conferência do profissional', 'Falha', detail)
            raise ValueError('Profissional da nota diverge do responsável. ' + detail)
        self.report('Conferência do profissional', 'OK', detail)

    def login(self, user):
        import keyring
        self.report('Login')
        if self.context:
            self.logout()
        self.user_identity_selector = None
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(20000)
        self.page.goto(self.config['url'])
        self.check('login').fill(user['login'])
        self.check('password').fill(keyring.get_password('RoboEvolutivo', user['login']))
        self.check('enter').click()
        self.report('Abertura da página inicial')
        self.check('pep')
        self.report('Abertura da página inicial', 'OK', 'Acesso ao PEP disponível após o login.')
        self.check('user', professional=user['name'])
        if normal(editor_text(self.text('user', professional=user['name']))) != normal(editor_text(user['name'])):
            raise ValueError('Usuário conectado diverge do responsável configurado.')
        self.remember_user_identity(user)
        self.current_professional = user['name']
        self.report('Login', 'OK', 'Usuário conectado corresponde ao responsável.')

    def prepare(self, record, user):
        self.save_started = False
        identity = self.mappings.get(normal(record.patient))
        if not identity or not identity.get('attendance') or (not identity.get('chart') and not getattr(self, 'diagnostic', False)):
            raise ValueError('Cadastre atendimento e prontuário do paciente em pacientes.json.')
        self.patient_context = {
            'patient_name': identity.get('name', record.patient),
            'attendance': identity['attendance'],
            'chart': identity.get('chart', ''),
        }
        if normal(editor_text(self.text('user', professional=user['name']))) != normal(editor_text(user['name'])):
            raise ValueError('Sessão incorreta.')
        self.check('pep').click()
        category = self.check('category')
        patient_label = identity.get('display', f"{identity.get('name', record.patient)} ({identity['attendance']})")
        patient = self.locator('patient', patient=patient_label, attendance=identity['attendance'])
        try:
            patient.wait_for(state='visible', timeout=500)
        except Exception as error:
            if type(error).__name__ != 'TimeoutError':
                self.report('Seletor: patient')
                raise ValueError(
                    'Não foi possível verificar o item do paciente na árvore: ' + patient_label +
                    ('. Foram encontrados vários elementos durante o carregamento.'
                     if 'strict mode violation' in str(error) else '. O navegador recusou o seletor (' + type(error).__name__ + ').') +
                    ' Capture o outerHTML do nome na lista. Nenhuma nota foi adicionada.'
                ) from None
            expanded = category.locator('xpath=ancestor-or-self::*[@aria-expanded][1]')
            if not expanded.count() or expanded.get_attribute('aria-expanded') != 'true':
                category.click()
        try:
            self.check('patient', patient=patient_label, attendance=identity['attendance']).click()
        except ValueError:
            raise
        except Exception as error:
            if 'strict mode violation' in str(error):
                reason = 'Mais de um elemento passou a corresponder ao paciente durante o carregamento.'
            elif type(error).__name__ == 'TimeoutError':
                reason = 'O item do paciente não ficou disponível para clique.'
            else:
                reason = 'O navegador recusou a seleção do item na árvore de pacientes (' + type(error).__name__ + ').'
            raise ValueError(reason + ' Paciente esperado: ' + patient_label +
                             '. Capture o outerHTML desse item na lista para conferir o mapeamento. Nenhuma nota foi adicionada.') from None
        self.check('notes').click()
        self.report('Identificação do paciente')
        for key in ('patient_header', 'attendance_header', 'chart_header'):
            self.check(key)
        if normal(self.text('patient_header')) != normal(record.patient):
            raise ValueError('Nome do paciente diverge do esperado.')
        actual_attendance = editor_text(self.text('attendance_header'))
        actual_chart = editor_text(self.text('chart_header'))
        if actual_attendance != str(identity['attendance']):
            raise ValueError('Atendimento ou prontuário incorreto.')
        if not identity.get('chart'):
            self.report('Identificação do paciente', 'Pendente', 'Prontuário exibido: ' + actual_chart + '. Cadastre e confira esse número antes de preencher a nota.')
            raise ValueError('Prontuário pendente no cadastro. Consulte o relatório e atualize em Pacientes; nenhuma nota foi adicionada.')
        if actual_chart != str(identity['chart']):
            raise ValueError('Atendimento ou prontuário incorreto.')
        self.report('Identificação do paciente', 'OK', 'Nome, atendimento e prontuário conferidos.')
        self.check('add').click()
        self.check('professional')
        self.verify_professional(user)
        date = self.check('date')
        date.fill(record.date)
        date.press('Tab')
        if date.input_value() != record.date:
            raise ValueError('Data não preservada com segundos.')
        self.report('Preenchimento da nota')
        note = self.check('note_type')
        if note.evaluate('(e) => e.tagName') == 'SELECT':
            note.select_option(label=TYPES[record.function])
            if note.locator('option:checked').inner_text().strip() != TYPES[record.function]:
                raise ValueError('Tipo de nota incorreto.')
        else:
            if not self.selectors.get('note_option'):
                raise ValueError('Configure note_option para o dropdown personalizado.')
            note.click()
            self.check('note_option', note_type=TYPES[record.function]).click()
            if self.text('note_type').strip() != TYPES[record.function]:
                raise ValueError('Tipo de nota incorreto.')
        self.check('content').fill(record.content)
        if editor_text(self.text('content')) != editor_text(record.content):
            raise ValueError('Conteúdo não foi preenchido integralmente.')
        self.check('save')
        self.check('close_pep')
        self.report('Preenchimento da nota', 'OK', 'Data com segundos, profissional, tipo e conteúdo conferidos. Salvar não foi acionado.')

    def save(self, record, user):
        if getattr(self, 'diagnostic', False):
            raise ValueError('Modo diagnóstico não permite Salvar nem Liberar.')
        identity = self.mappings[normal(record.patient)]
        if normal(self.text('patient_header')) != normal(record.patient) or self.text('attendance_header').strip() != str(identity['attendance']) or self.text('chart_header').strip() != str(identity['chart']):
            raise ValueError('Paciente, atendimento ou prontuário mudou durante a revisão.')
        if normal(editor_text(self.text('user', professional=user['name']))) != normal(editor_text(user['name'])):
            raise ValueError('Usuário mudou antes do salvamento.')
        self.verify_professional(user)
        note = self.locator('note_type')
        selected = note.locator('option:checked').inner_text() if note.evaluate('(e) => e.tagName') == 'SELECT' else self.text('note_type')
        if selected.strip() != TYPES[record.function]:
            raise ValueError('Tipo de nota mudou durante a revisão.')
        if self.locator('date').input_value() != record.date:
            raise ValueError('Data alterada durante a revisão.')
        if editor_text(self.text('content')) != editor_text(record.content):
            raise ValueError('Conteúdo alterado durante a revisão. Corrija a fonte e recarregue.')
        result = self.locator('saved_note', attendance=identity['attendance'], date=record.date, professional=user['name'], note_type=TYPES[record.function])
        if result.count():
            raise ValueError('Já existe nota correspondente ou seletor de confirmação identifica o editor. Confira antes de repetir.')
        self.report('Salvar nota')
        self.save_started = True
        self.locator('save').click()
        # User-authorized release must target only the confirmation dialog.
        self.report('Liberar nota')
        self.locator('release').click()
        # A screen title or generic toast is not evidence of a persisted note.
        self.report('Confirmar linha gravada')
        result.wait_for(state='visible', timeout=30000)
        if result.count() != 1:
            raise ValueError('Não foi possível confirmar uma única nota salva.')
        persisted = normal(editor_text(result.inner_text()))
        if not all(normal(value) in persisted for value in (identity['attendance'], record.date, user['name'])):
            raise ValueError('A linha gravada não corresponde ao atendimento, data e responsável enviados.')
        result.click()
        self.report('Conferir conteúdo gravado')
        saved_content = editor_text(self.text('saved_content'))
        if saved_content != editor_text(record.content):
            raise ValueError('Conteúdo da nota gravada não corresponde ao texto enviado.')
        if self.locator('save').is_visible() and self.locator('save').is_enabled():
            raise ValueError('Formulário ainda aberto; confirmação da persistência inconclusiva.')
        self.report('Fechar PEP')
        self.locator('close_pep').click()
        self.check('pep')

    def close(self):
        if hasattr(self, 'browser'):
            self.browser.close()
        if hasattr(self, 'engine'):
            self.engine.stop()
