import json
import queue
import threading
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from app.core import Ledger, load_professionals, normal, TYPES
from app.sheets import Sheets
from app.tasy import Tasy
from app.storage import ROOT, PROFESSIONALS, SHEET_TAB, prepare_storage, ledger_path
from app.theme import apply_theme
from app.importing import ordered_imports
from app.filtering import date_period, within_period
from app.manual_confirmation import confirm_records
from app.calendar_picker import DateCalendar

DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
(ROOT / 'config').mkdir(exist_ok=True)
if not (ROOT / 'config/pacientes.json').exists():
    (ROOT / 'config/pacientes.json').write_text('{}\n', encoding='utf-8')


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        prepare_storage()
        self.dark_mode = False
        apply_theme(self, self.dark_mode)
        self.title('EvolucaoIntensihome — Importação de notas clínicas')
        icon = ROOT / 'assets' / 'robot.ico'
        if icon.exists():
            self.iconbitmap(str(icon))
        self.geometry('1100x760')
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        self.records = []
        self.professionals = {}
        self.skipped_details = []
        self.column_filters = {}
        self.date_period = (None, None)
        self.date_period_labels = ('', '')
        self.row_states = {}
        self.column_labels = dict(zip(('patient', 'date', 'function', 'author', 'status'), ('Paciente', 'Data', 'Profissão', 'Autor / Conselho', 'Estado')))
        self.settings = {}
        if (DATA / 'settings.json').exists():
            self.settings = json.loads((DATA / 'settings.json').read_text(encoding='utf-8'))
        top = ttk.Frame(self, padding=12)
        top.pack(fill='x')
        self.fields = {}
        defaults = {'Planilha': 'https://docs.google.com/spreadsheets/d/1XE8mgSeRxnxy0S9pnx2l-lXBlwT5bpiN46ue-PLi4SI/edit?usp=sharing', 'Credenciais Google': ''}
        for row, (label, default) in enumerate(defaults.items()):
            ttk.Label(top, text=label).grid(row=row, column=0, sticky='w', pady=4)
            value = self.settings.get(label, default)
            if label == 'Credenciais Google' and value and not Path(value).is_absolute():
                value = str(ROOT / value)
            var = tk.StringVar(value=value)
            self.fields[label] = var
            ttk.Entry(top, textvariable=var, width=100).grid(row=row, column=1, sticky='ew')
            if label == 'Credenciais Google':
                ttk.Button(top, text='Selecionar', command=lambda v=var: self.pick(v)).grid(row=row, column=2)
        top.columnconfigure(1, weight=1)
        self.theme_selected = tk.BooleanVar(value=False)
        self.theme_checkbox = ttk.Checkbutton(top, text='Modo noturno', variable=self.theme_selected, command=self.toggle_theme)
        self.theme_checkbox.grid(row=0, column=2, sticky='e', padx=(10, 0))
        setup = ttk.Frame(top)
        setup.grid(row=2, column=0, columnspan=3, sticky='w', pady=6)
        ttk.Button(setup, text='Profissionais', command=lambda: os.startfile(PROFESSIONALS)).pack(side='left', padx=3)
        self.patients_button = ttk.Button(setup, text='Pacientes', command=self.edit_patients)
        self.patients_button.pack(side='left', padx=3)
        functions = ttk.LabelFrame(self, text='Profissões a importar', padding=8)
        functions.pack(fill='x', padx=12)
        self.selected = {}
        for n, function in enumerate(f for f in TYPES if f != 'fisioterapeuta'):
            var = tk.BooleanVar(value=True)
            self.selected[function] = var
            ttk.Checkbutton(functions, text=function.title(), variable=var).grid(row=n // 3, column=n % 3, sticky='w', padx=15)
        actions = ttk.Frame(self, padding=12)
        actions.pack(fill='x')
        self.connect_button = ttk.Button(actions, text='Conectar e carregar', command=self.load)
        self.connect_button.pack(side='left')
        self.import_button = ttk.Button(actions, text='Importar linhas selecionadas', command=self.run, state='disabled')
        self.import_button.pack(side='left', padx=8)
        self.confirm_button = ttk.Button(actions, text='Confirmar Registro', command=self.confirm_selected, state='disabled')
        self.confirm_button.pack(side='left', padx=8)
        self.clear_filters_button = ttk.Button(actions, text='Limpar filtros', command=self.clear_filters, state='disabled')
        self.clear_filters_button.pack(side='left', padx=8)
        self.visible_count = tk.StringVar(value='0 linhas')
        ttk.Label(actions, textvariable=self.visible_count).pack(side='left', padx=8)
        self.preview_split = ttk.Panedwindow(self, orient='vertical')
        self.preview_split.pack(fill='both', expand=True, padx=12)
        list_frame = ttk.Frame(self.preview_split, height=160)
        content_frame = ttk.LabelFrame(self.preview_split, text='Evolução selecionada', padding=6, height=280)
        self.preview_split.add(list_frame, weight=3)
        self.preview_split.add(content_frame, weight=7)
        self.tree = ttk.Treeview(list_frame, columns=('patient', 'date', 'function', 'author', 'status'), show='headings', selectmode='extended', height=6)
        for column, label in zip(self.tree['columns'], ('Paciente', 'Data', 'Profissão', 'Autor / Conselho', 'Estado')):
            self.tree.heading(column, text=label + ' ▾', command=lambda key=column: self.open_filter(key))
            self.tree.column(column, width=180)
        table_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        table_scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=table_scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.preview)
        self.selection_anchor = None
        self.tree.bind('<Button-1>', self.anchor_selection, add='+')
        self.tree.bind('<Shift-Button-1>', self.shift_click)
        self.tree.bind('<Shift-Down>', lambda event: self.move_selection(1, extend=True))
        self.tree.bind('<Shift-Up>', lambda event: self.move_selection(-1, extend=True))
        self.tree.bind('<Down>', lambda event: self.move_selection(1))
        self.tree.bind('<Up>', lambda event: self.move_selection(-1))
        self.content = tk.Text(content_frame, height=16, wrap='word', state='disabled', relief='flat', padx=10, pady=8)
        content_scroll = ttk.Scrollbar(content_frame, orient='vertical', command=self.content.yview)
        content_scroll.pack(side='right', fill='y')
        self.content.configure(yscrollcommand=content_scroll.set)
        self.content.pack(side='left', fill='both', expand=True)
        self.status = tk.StringVar(value='Configure as credenciais e conecte à planilha. Selecione as linhas que deseja executar.')
        ttk.Label(self, textvariable=self.status, wraplength=1050).pack(fill='x', padx=12, pady=8)
        self.protocol('WM_DELETE_WINDOW', self.exit)
        apply_theme(self, self.dark_mode)
        self.after_idle(lambda: self.preview_split.sashpos(0, int(self.preview_split.winfo_height() * 0.3)))
        self.after(100, self.poll)

    def toggle_theme(self):
        self.dark_mode = self.theme_selected.get()
        apply_theme(self, self.dark_mode)

    def record_values(self, record):
        return dict(zip(self.column_labels, (record.patient, record.date[:-3], record.function, record.author, self.row_states.get(record.key, record.status) or 'Pendente')))

    def render_records(self):
        selected = set(self.tree.selection())
        focused = self.tree.focus()
        self.tree.delete(*self.tree.get_children())
        visible = []
        for record in self.records:
            values = self.record_values(record)
            if all(values[column] in allowed for column, allowed in self.column_filters.items()) and within_period(record.date, self.date_period):
                self.tree.insert('', 'end', iid=record.key, values=tuple(values.values()))
                visible.append(record.key)
        self.tree.selection_set([key for key in visible if key in selected])
        if focused in visible:
            self.tree.focus(focused)
        if self.selection_anchor not in visible:
            self.selection_anchor = None
        self.visible_count.set(f'{len(visible)} de {len(self.records)} linhas')
        for key, label in self.column_labels.items():
            active = key in self.column_filters or (key == 'date' and any(self.date_period))
            self.tree.heading(key, text=label + (' ● ▾' if active else ' ▾'))
        self.clear_filters_button.configure(state='normal' if (self.column_filters or any(self.date_period)) and not self.busy else 'disabled')
        self.preview()

    def clear_filters(self):
        if not self.busy:
            self.column_filters.clear()
            self.date_period = (None, None)
            self.date_period_labels = ('', '')
            self.render_records()

    def open_filter(self, column):
        if self.busy:
            return
        if column == 'date':
            self.open_date_filter()
            return
        dialog = tk.Toplevel(self)
        dialog.title('Filtrar: ' + self.column_labels[column])
        dialog.geometry('510x450')
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        search = tk.StringVar()
        ttk.Label(frame, text='Buscar valores').pack(anchor='w')
        entry = ttk.Entry(frame, textvariable=search)
        entry.pack(fill='x', pady=6)
        values = sorted({self.record_values(record)[column] for record in self.records}, key=normal)
        selected = self.column_filters.get(column, set(values))
        checked = {value: tk.BooleanVar(value=value in selected) for value in values}
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', pady=4)
        def mark(enabled):
            for value, var in checked.items():
                if normal(search.get()) in normal(value):
                    var.set(enabled)
            refresh()
        def only_shown():
            for value, var in checked.items():
                var.set(normal(search.get()) in normal(value))
            refresh()
        ttk.Button(toolbar, text='Marcar exibidos', command=lambda: mark(True)).pack(side='left')
        ttk.Button(toolbar, text='Desmarcar exibidos', command=lambda: mark(False)).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Somente exibidos', command=only_shown).pack(side='left')
        listing = ttk.Treeview(frame, columns=('value',), show='tree', selectmode='none', height=10)
        listing.pack(fill='both', expand=True)
        scroll = ttk.Scrollbar(listing, orient='vertical', command=listing.yview)
        scroll.pack(side='right', fill='y')
        listing.configure(yscrollcommand=scroll.set)
        def refresh(*_):
            listing.delete(*listing.get_children())
            for index, value in enumerate(values):
                if normal(search.get()) in normal(value):
                    listing.insert('', 'end', iid=str(index), text=('☑ ' if checked[value].get() else '☐ ') + value)
        search.trace_add('write', refresh)
        def toggle(event):
            row = listing.identify_row(event.y)
            if row:
                var = checked[values[int(row)]]
                var.set(not var.get())
                refresh()
            return 'break'
        listing.bind('<Button-1>', toggle)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(10, 0))
        def apply():
            allowed = {value for value, var in checked.items() if var.get()}
            if allowed == set(values):
                self.column_filters.pop(column, None)
            else:
                self.column_filters[column] = allowed
            self.render_records()
            dialog.destroy()
        def clear():
            self.column_filters.pop(column, None)
            self.render_records()
            dialog.destroy()
        ttk.Button(buttons, text='Aplicar', command=apply).pack(side='left')
        ttk.Button(buttons, text='Limpar coluna', command=clear).pack(side='left', padx=6)
        ttk.Button(buttons, text='Cancelar', command=dialog.destroy).pack(side='right')
        refresh()
        apply_theme(self, self.dark_mode)
        entry.focus_set()

    def open_date_filter(self):
        dialog = tk.Toplevel(self)
        dialog.title('Filtrar: Data por período')
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='DD/MM/AAAA ou DD/MM/AAAA HH:mm. Deixe em branco para não limitar.').pack(anchor='w')
        entries = []
        for label, value in zip(('De:', 'Até:'), self.date_period_labels):
            ttk.Label(frame, text=label).pack(anchor='w', pady=(10, 0))
            var = tk.StringVar(value=value)
            row = ttk.Frame(frame)
            row.pack(fill='x')
            ttk.Entry(row, textvariable=var, width=32).pack(side='left', fill='x', expand=True)
            def show_calendar(variable=var):
                DateCalendar(dialog, variable)
                apply_theme(self, self.dark_mode)
            ttk.Button(row, text='Calendário', command=show_calendar).pack(side='left', padx=(8, 0))
            entries.append(var)
        ttk.Label(frame, text='Sem horário, a data final inclui o dia inteiro.').pack(anchor='w', pady=10)
        def apply():
            labels = tuple(var.get().strip() for var in entries)
            try:
                period = date_period(*labels)
            except ValueError as error:
                messagebox.showerror('Período inválido', str(error), parent=dialog)
                return
            self.date_period, self.date_period_labels = period, labels
            self.column_filters.pop('date', None)
            self.render_records()
            dialog.destroy()
        def clear():
            self.date_period, self.date_period_labels = (None, None), ('', '')
            self.column_filters.pop('date', None)
            self.render_records()
            dialog.destroy()
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=8)
        ttk.Button(buttons, text='Aplicar', command=apply).pack(side='left')
        ttk.Button(buttons, text='Limpar coluna', command=clear).pack(side='left', padx=8)
        ttk.Button(buttons, text='Cancelar', command=dialog.destroy).pack(side='right')
        apply_theme(self, self.dark_mode)

    def confirm_selected(self):
        if self.busy:
            return
        keys = set(self.tree.selection())
        records = [record for record in self.records if record.key in keys]
        if not records:
            messagebox.showinfo('Seleção', 'Selecione as linhas conferidas no Tasy.')
            return
        detail = '\n'.join(f'{r.patient} — {r.date[:-3]} — {r.function}' for r in records[:10])
        if len(records) > 10:
            detail += f'\n... e mais {len(records) - 10} linha(s).'
        if not messagebox.askyesno('Confirmar Registro',
                f'Você verificou no Tasy que TODAS as {len(records)} notas selecionadas estão salvas e liberadas?\n\n'
                + detail + '\n\nConfirmar marcará Sim no SQLite e em Importado? no Sheets. Nenhuma nota será lançada no Tasy.'):
            return
        settings = dict(self.settings)
        def task():
            sheets = Sheets(settings['Credenciais Google'], settings['Planilha'], SHEET_TAB)
            ledger = Ledger(ledger_path())
            try:
                prefix = settings['Planilha'].split('/d/')[1].split('/')[0] + ':'
                count = confirm_records(records, sheets, ledger, prefix,
                                        lambda key, state: self.events.put(('status', (key, state))))
                self.events.put(('manual_completed', count))
            finally:
                ledger.db.close()
        self.launch(task)

    def anchor_selection(self, event):
        row = self.tree.identify_row(event.y)
        if row and not (event.state & 0x0005):
            self.selection_anchor = row

    def select_range(self, target):
        rows = self.tree.get_children('')
        if target not in rows:
            return 'break'
        if self.selection_anchor not in rows:
            self.selection_anchor = self.tree.focus() or next(iter(self.tree.selection()), target)
        start, end = rows.index(self.selection_anchor), rows.index(target)
        self.tree.focus(target)
        self.tree.selection_set(rows[min(start, end):max(start, end) + 1])
        self.tree.see(target)
        self.tree.focus_set()
        return 'break'

    def shift_click(self, event):
        if self.tree.identify_region(event.x, event.y) not in ('cell', 'tree'):
            return None
        return self.select_range(self.tree.identify_row(event.y))

    def move_selection(self, direction, extend=False):
        rows = self.tree.get_children('')
        if not rows:
            return 'break'
        current = self.tree.focus() or next(iter(self.tree.selection()), '')
        index = max(0, min(len(rows) - 1, rows.index(current) + direction)) if current in rows else (0 if direction > 0 else len(rows) - 1)
        target = rows[index]
        if extend:
            return self.select_range(target)
        self.selection_anchor = target
        self.tree.focus(target)
        self.tree.selection_set(target)
        self.tree.see(target)
        return 'break'

    def edit_patients(self):
        if self.busy:
            return
        path = ROOT / 'config/pacientes.json'
        patients = json.loads(path.read_text(encoding='utf-8'))
        dialog = tk.Toplevel(self)
        dialog.title('Cadastro de pacientes — conferir identificadores')
        dialog.geometry('900x360')
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Informe o prontuário exibido no cabeçalho do Tasy. Atendimento e prontuário são números distintos.').grid(row=0, column=0, columnspan=3, sticky='w', pady=8)
        for col, title in enumerate(('Paciente', 'Atendimento', 'Prontuário')):
            ttk.Label(frame, text=title).grid(row=1, column=col, sticky='w')
        entries = {}
        for row, (name, identity) in enumerate(patients.items(), 2):
            ttk.Label(frame, text=name).grid(row=row, column=0, sticky='w', padx=(0, 16), pady=5)
            attendance = tk.StringVar(value=identity.get('attendance', ''))
            chart = tk.StringVar(value=identity.get('chart', ''))
            ttk.Entry(frame, textvariable=attendance, width=18).grid(row=row, column=1, padx=4)
            ttk.Entry(frame, textvariable=chart, width=18).grid(row=row, column=2, padx=4)
            entries[name] = attendance, chart
        def save():
            for name, (attendance, chart) in entries.items():
                a, c = attendance.get().strip(), chart.get().strip()
                if not a.isdigit() or (c and not c.isdigit()):
                    messagebox.showerror('Identificadores', 'Use somente números. Prontuário ainda desconhecido pode ficar vazio.', parent=dialog)
                    return
            for name, (attendance, chart) in entries.items():
                identity = patients[name]
                identity['attendance'], identity['chart'] = attendance.get().strip(), chart.get().strip()
                identity['display'] = f"{identity.get('name', name)} ({identity['attendance']})"
            path.write_text(json.dumps(patients, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            dialog.destroy()
            self.status.set('Pacientes atualizados. Selecione as linhas que deseja importar.')
        ttk.Button(frame, text='Salvar cadastro', command=save).grid(row=len(entries) + 2, column=0, sticky='w', pady=14)
        apply_theme(self, self.dark_mode)




    def pick(self, variable):
        filename = filedialog.askopenfilename()
        if filename:
            variable.set(filename)

    def preview(self, *_):
        selected = self.tree.selection()
        if not selected:
            self.content.configure(state='normal')
            self.content.delete('1.0', 'end')
            self.content.configure(state='disabled')
        if selected:
            focused = self.tree.focus()
            key = focused if focused in selected else selected[0]
            record = next((r for r in self.records if r.key == key), None)
            if record:
                self.content.configure(state='normal')
                self.content.delete('1.0', 'end')
                self.content.insert('1.0', record.content)
                self.content.configure(state='disabled')

    def launch(self, task):
        if self.busy:
            return
        self.busy = True
        self.connect_button.configure(state='disabled')
        self.import_button.configure(state='disabled')
        self.confirm_button.configure(state='disabled')
        self.patients_button.configure(state='disabled')
        self.clear_filters_button.configure(state='disabled')
        def worker():
            try:
                task()
            except Exception as error:
                # API/browser exceptions may contain clinical text or secrets.
                self.events.put(('error', str(error) if isinstance(error, ValueError) else 'Operação falhou (' + type(error).__name__ + '). Confira acesso Google, configuração e navegador.'))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def load(self):
        settings = {k: v.get().strip() for k, v in self.fields.items()}
        (DATA / 'settings.json').write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
        def task():
            professionals = load_professionals(PROFESSIONALS)
            sheets = Sheets(settings['Credenciais Google'], settings['Planilha'], SHEET_TAB)
            records = sheets.read()
            self.events.put(('loaded', (settings, professionals, records)))
        self.launch(task)

    def run(self):
        keys = set(self.tree.selection())
        functions = {f for f, v in self.selected.items() if v.get()}
        records = [r for r in self.records if r.key in keys and r.function in functions]
        if not records:
            messagebox.showinfo('Seleção', 'Selecione as linhas e profissões desejadas.')
            return
        settings = dict(self.settings)
        professionals = dict(self.professionals)
        self.stop.clear()
        self.skipped_details = []
        def task():
            ordered = ordered_imports(records, professionals)
            mappings = json.loads((ROOT / 'config/pacientes.json').read_text(encoding='utf-8'))
            mappings = {normal(k): v for k, v in mappings.items()}
            for record in records:
                if not mappings.get(normal(record.patient), {}).get('chart'):
                    raise ValueError('Cadastre e confira o prontuário em Pacientes antes do lançamento real.')
            tasy = Tasy(ROOT / 'config/tasy.json', mappings, allow_import=True, cancel=self.stop)
            sheets = Sheets(settings['Credenciais Google'], settings['Planilha'], SHEET_TAB)
            ledger = Ledger(ledger_path())
            current = None
            imported, skipped = 0, 0
            active_record = None
            try:
                tasy.start()
                for record in ordered:
                    active_record = record
                    if self.stop.is_set():
                        break
                    local_key = settings['Planilha'].split('/d/')[1].split('/')[0] + ':' + record.key
                    local_status = ledger.get(local_key)
                    if local_status in ('Sim', 'Conferir') or normal(record.status) not in ('', 'pendente', 'erro'):
                        skipped += 1
                        self.events.put(('status', (record.key, local_status or record.status)))
                        state = local_status or record.status
                        reason = 'Gravação anterior incerta; confira a nota no Tasy antes de repetir.' if normal(state) == 'conferir' else ('Já importada e confirmada.' if normal(state) == 'sim' else 'Estado de origem não permite nova tentativa: ' + state)
                        self.events.put(('skipped_reason', f'{record.patient} — {record.date[:-3]}: {reason}'))
                        continue
                    user = professionals.get(record.function)
                    if not user:
                        raise ValueError('Sem responsável configurado para ' + record.function)
                    if not mappings.get(normal(record.patient)):
                        raise ValueError('Paciente sem cadastro de identificadores: ' + record.patient)
                    if current != user['login']:
                        tasy.login(user)
                        current = user['login']
                    sheets.claim(record)
                    ledger.set(local_key, 'Em processamento')
                    tasy.save_started = False
                    try:
                        self.events.put(('status', (record.key, 'Em processamento')))
                        tasy.prepare(record, user)
                        if self.stop.is_set():
                            raise ValueError('Execução interrompida antes do salvamento.')
                        tasy.save(record, user)
                        ledger.set(local_key, 'Sim')
                        imported += 1
                        sheets.status(record, 'Sim')
                        self.events.put(('status', (record.key, 'Sim')))
                    except Exception:
                        state = 'Sim' if ledger.get(local_key) == 'Sim' else ('Conferir' if tasy.save_started else 'Erro')
                        ledger.set(local_key, state)
                        try:
                            sheets.status(record, state)
                        except Exception:
                            self.events.put(('message', 'Estado preservado localmente; atualização no Sheets falhou.'))
                        self.events.put(('status', (record.key, state)))
                        raise
            except Exception as error:
                self.events.put(('message', f'Execução interrompida. Linhas importadas com confirmação até agora: {imported}. Ignoradas: {skipped}.'))
                context = f'{active_record.patient} — {active_record.date}' if active_record else 'Início da execução'
                detail = str(error) if isinstance(error, ValueError) else 'Falha ' + type(error).__name__
                step = getattr(tasy, 'last_step', 'Navegador')
                raise ValueError(f'{context}\nEtapa: {step}. {detail}\nLinhas confirmadas nesta execução: {imported}. Ignoradas: {skipped}.') from None
            finally:
                ledger.db.close()
                tasy.close()
            self.events.put(('run_completed', (imported, skipped, self.stop.is_set())))
        self.launch(task)


    def cancel(self):
        self.stop.set()

    def poll(self):
        while not self.events.empty():
            event, value = self.events.get()
            if event == 'loaded':
                self.settings, self.professionals, self.records = value
                self.row_states.clear()
                self.column_filters.clear()
                self.date_period = (None, None)
                self.date_period_labels = ('', '')
                self.selection_anchor = None
                self.render_records()
                self.status.set(f'Conectado. {len(self.records)} respostas carregadas. Selecione as linhas para execução.')
            elif event == 'status':
                key, state = value
                self.row_states[key] = state
                for record in self.records:
                    if record.key == key:
                        record.status = state
                        break
                self.render_records()
            elif event == 'error':
                self.status.set(value)
                messagebox.showerror('Operação interrompida', value)
            elif event == 'message':
                self.status.set(value)
            elif event == 'skipped_reason':
                self.skipped_details.append(value)
            elif event == 'manual_completed':
                text = f'{value} registro(s) confirmado(s). Importado? atualizado para Sim.'
                self.status.set(text)
                messagebox.showinfo('Confirmação concluída', text)
            elif event == 'run_completed':
                imported, skipped, interrupted = value
                title = 'Importação interrompida' if interrupted else 'Importação concluída'
                detail = f'{title}.\nLinhas importadas: {imported}.\nLinhas ignoradas: {skipped}.'
                if self.skipped_details:
                    detail += '\n\nMotivos das linhas ignoradas:\n' + '\n'.join(self.skipped_details)
                self.status.set(detail.replace('\n', ' '))
                messagebox.showinfo(title, detail)
            elif event == 'done':
                self.busy = False
                self.connect_button.configure(state='normal')
                self.import_button.configure(state='normal' if self.records else 'disabled')
                self.confirm_button.configure(state='normal' if self.records else 'disabled')
                self.patients_button.configure(state='normal')
                self.clear_filters_button.configure(state='normal' if self.column_filters or any(self.date_period) else 'disabled')
        self.after(100, self.poll)

    def exit(self):
        if self.busy:
            self.cancel()
            self.status.set('Aguarde a interrupção da tarefa antes de fechar a aplicação.')
            return
        self.destroy()


if __name__ == '__main__':
    import msvcrt
    instance_lock = open(DATA / 'instance.lock', 'a+b')
    instance_lock.seek(0)
    instance_lock.write(b'0')
    instance_lock.flush()
    instance_lock.seek(0)
    try:
        msvcrt.locking(instance_lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        raise SystemExit('EvolucaoIntensihome já está aberto nesta pasta.')
    try:
        Application().mainloop()
    finally:
        instance_lock.close()
