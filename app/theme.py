"""Light and dark themes for ttk widgets and text previews."""
import tkinter as tk
from tkinter import ttk

BACKGROUND = '#171b24'
SURFACE = '#222938'
TEXT = '#e5eaf3'
MUTED = '#98a5ba'
ACCENT = '#315c93'


def apply_theme(window, dark=False):
    BACKGROUND = '#171b24' if dark else '#f4f6fa'
    SURFACE = '#222938' if dark else '#ffffff'
    TEXT = '#e5eaf3' if dark else '#192338'
    MUTED = '#98a5ba' if dark else '#607087'
    border = '#3a4559' if dark else '#c9d2df'
    active = '#344159' if dark else '#dbe6f5'
    disabled = '#202633' if dark else '#e7ebf1'
    window.configure(background=BACKGROUND)
    window.option_add('*Background', BACKGROUND)
    window.option_add('*Foreground', TEXT)
    window.option_add('*selectBackground', ACCENT)
    window.option_add('*selectForeground', '#ffffff')
    style = ttk.Style(window)
    style.theme_use('clam')
    style.configure('.', background=BACKGROUND, foreground=TEXT,
                    fieldbackground=SURFACE, bordercolor=border,
                    lightcolor=BACKGROUND, darkcolor=BACKGROUND,
                    troughcolor=BACKGROUND, font=('Segoe UI', 10))
    style.configure('TFrame', background=BACKGROUND)
    style.configure('TLabel', background=BACKGROUND, foreground=TEXT)
    style.configure('TLabelframe', background=BACKGROUND, bordercolor=border)
    style.configure('TLabelframe.Label', background=BACKGROUND, foreground=MUTED)
    style.configure('TEntry', fieldbackground=SURFACE, foreground=TEXT, insertcolor=TEXT, padding=6)
    style.map('TEntry', fieldbackground=[('disabled', SURFACE), ('readonly', SURFACE)], foreground=[('disabled', MUTED)])
    style.configure('TButton', background=SURFACE, foreground=TEXT, padding=(10, 7))
    style.map('TButton', background=[('disabled', disabled), ('pressed', ACCENT), ('active', active)], foreground=[('disabled', MUTED)])
    style.configure('TCheckbutton', background=BACKGROUND, foreground=TEXT, indicatorbackground=SURFACE, indicatorforeground=TEXT)
    style.map('TCheckbutton', background=[('active', BACKGROUND)], foreground=[('disabled', MUTED)], indicatorbackground=[('selected', ACCENT), ('active', active)])
    style.configure('Treeview', background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, rowheight=30)
    style.configure('Treeview.Heading', background='#2b3547' if dark else '#e5ebf4', foreground=TEXT, padding=7)
    style.map('Treeview', background=[('selected', ACCENT)], foreground=[('selected', '#ffffff')])
    style.map('Treeview.Heading', background=[('active', active)])
    def visit(widget):
        if isinstance(widget, tk.Text):
            widget.configure(background=SURFACE, foreground=TEXT, insertbackground=TEXT,
                             selectbackground=ACCENT, selectforeground='#ffffff')
        if isinstance(widget, tk.Toplevel):
            widget.configure(background=BACKGROUND)
        for child in widget.winfo_children():
            visit(child)
    visit(window)
    # Ask Windows to draw the title bar in dark colors when supported.
    if window.tk.call('tk', 'windowingsystem') == 'win32':
        try:
            import ctypes
            window.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            enabled = ctypes.c_int(int(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(enabled), ctypes.sizeof(enabled))
        except (AttributeError, OSError):
            pass
