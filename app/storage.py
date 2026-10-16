"""Fixed local paths and non-destructive migration of existing files."""
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
DB = ROOT / 'DB'
PROFESSIONALS = DB / 'profissionais.txt'
SHEET_TAB = 'Form Responses 1'


def prepare_storage():
    DB.mkdir(exist_ok=True)
    if not PROFESSIONALS.exists():
        # Preserve the existing user-maintained file, including its contents.
        source = next((p for p in (ROOT / 'profissionais.txt',) if p.exists()), None)
        if source:
            shutil.copy2(source, PROFESSIONALS)
        else:
            PROFESSIONALS.write_text('funcao;responsavel_tasy;login;senha\n', encoding='utf-8')


def ledger_path():
    target = DB / 'jobs.sqlite3'
    legacy = ROOT / 'data/jobs.sqlite3'
    if legacy.exists() and not target.exists():
        with sqlite3.connect(legacy) as source, sqlite3.connect(target) as destination:
            source.backup(destination)
    return target
