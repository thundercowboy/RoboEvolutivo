"""Clickable Portuguese calendar using only Tk and the standard library."""
import calendar
from datetime import datetime
import tkinter as tk
from tkinter import ttk


MONTHS = ('Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
          'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro')


class DateCalendar(tk.Toplevel):
    def __init__(self, parent, variable):
        super().__init__(parent)
        self.parent, self.variable = parent, variable
        self.title('Selecionar data')
        self.resizable(False, False)
        self.transient(parent)
        try:
            selected = datetime.strptime(variable.get().strip()[:10], '%d/%m/%Y')
        except ValueError:
            selected = datetime.now()
        self.year, self.month = selected.year, selected.month
        self.selected = selected.date()
        outer = ttk.Frame(self, padding=12)
        outer.pack()
        header = ttk.Frame(outer)
        header.pack(fill='x')
        ttk.Button(header, text='◀', command=lambda: self.move(-1)).pack(side='left')
        self.caption = ttk.Label(header, anchor='center', width=24)
        self.caption.pack(side='left', fill='x', expand=True)
        ttk.Button(header, text='▶', command=lambda: self.move(1)).pack(side='right')
        self.days = ttk.Frame(outer)
        self.days.pack(pady=8)
        footer = ttk.Frame(outer)
        footer.pack(fill='x')
        ttk.Button(footer, text='Hoje', command=self.today).pack(side='left')
        ttk.Button(footer, text='Cancelar', command=self.close).pack(side='right')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Escape>', lambda event: self.close())
        self.render()
        self.grab_set()

    def render(self):
        self.caption.configure(text=f'{MONTHS[self.month - 1]} de {self.year}')
        for widget in self.days.winfo_children():
            widget.destroy()
        for col, name in enumerate(('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom')):
            ttk.Label(self.days, text=name, anchor='center', width=5).grid(row=0, column=col)
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), 1):
            for col, day in enumerate(week):
                if day:
                    button = ttk.Button(self.days, text=str(day), width=4, command=lambda d=day: self.choose(d))
                    button.grid(row=row, column=col, padx=1, pady=1)
                    if (self.year, self.month, day) == (self.selected.year, self.selected.month, self.selected.day):
                        button.state(['pressed'])

    def move(self, offset):
        index = self.year * 12 + self.month - 1 + offset
        year, month = divmod(index, 12)
        if 1 <= year <= 9999:
            self.year, self.month = year, month + 1
            self.render()

    def choose(self, day):
        # Preserve an optional time already entered in the period field.
        parts = self.variable.get().strip().split(maxsplit=1)
        suffix = ' ' + parts[1] if len(parts) > 1 else ''
        self.variable.set(f'{day:02d}/{self.month:02d}/{self.year:04d}' + suffix)
        self.close()

    def today(self):
        current = datetime.now()
        self.year, self.month = current.year, current.month
        self.choose(current.day)

    def close(self):
        self.destroy()
        if self.parent.winfo_exists():
            self.parent.grab_set()
