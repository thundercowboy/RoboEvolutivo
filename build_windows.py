"""Build a Windows folder distribution; never bundle private Google keys/passwords."""
import csv
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed',
                '--onedir', '--name', 'EvolucaoIntensihome', '--icon', 'assets/robot.ico',
                '--collect-all', 'playwright', '--hidden-import', 'keyring.backends.Windows',
                'main.py'], check=True)
out = ROOT / 'dist/EvolucaoIntensihome'
for folder in ('assets', 'config'):
    shutil.copytree(ROOT / folder, out / folder, dirs_exist_ok=True)
(out / 'DB').mkdir(exist_ok=True)
(out / 'data').mkdir(exist_ok=True)
with (ROOT / 'DB/profissionais.txt').open(encoding='utf-8-sig', newline='') as source:
    reader = csv.DictReader(source, delimiter=';')
    with (out / 'DB/profissionais.txt').open('w', encoding='utf-8', newline='') as target:
        writer = csv.DictWriter(target, reader.fieldnames, delimiter=';')
        writer.writeheader()
        for row in reader:
            row['senha'] = ''
            writer.writerow(row)
if (ROOT / 'DB/jobs.sqlite3').exists():
    with sqlite3.connect(ROOT / 'DB/jobs.sqlite3') as source, sqlite3.connect(out / 'DB/jobs.sqlite3') as target:
        source.backup(target)
settings = json.loads((ROOT / 'data/settings.json').read_text(encoding='utf-8'))
settings['Credenciais Google'] = ''
(out / 'data/settings.json').write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
import playwright
browser_info = json.loads((Path(playwright.__file__).parent / 'driver/package/browsers.json').read_text())
revision = next(b['revision'] for b in browser_info['browsers'] if b['name'] == 'chromium')
browser_dir = Path(os.environ['LOCALAPPDATA']) / 'ms-playwright' / ('chromium-' + revision)
shutil.copytree(browser_dir, out / 'browsers' / browser_dir.name, dirs_exist_ok=True)
for filename in ('USAR_EM_OUTRO_PC.md', 'CONFIGURAR_GOOGLE.md'):
    shutil.copy2(ROOT / filename, out / filename)
shutil.make_archive(str(ROOT / 'dist/EvolucaoIntensihome-Windows'), 'zip', ROOT / 'dist', 'EvolucaoIntensihome')
print('Distribuicao concluida:', out)
