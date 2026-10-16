import csv
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3


def normal(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(value)) if not unicodedata.combining(c)).casefold().split())


TYPES = {
    'fonoaudiologo': 'Evolução Fonoaudiologia',
    'enfermeiro': 'Evolução de Enfermagem',
    'medico': 'Evolução Médica',
    'nutricionista': 'Evolução da Nutrição',
    'fisioterapeuta': 'Evolução Fisioterapia Unimed Lar',
    'terapeuta ocupacional': 'Evolução Terapia Ocupacional Unimed Lar',
}
ALIASES = {'fonoaudiologia': 'fonoaudiologo', 'enfermagem': 'enfermeiro', 'medicina': 'medico', 'nutricao': 'nutricionista', 'fisioterapia': 'fisioterapeuta', 'terapia ocupacional': 'terapeuta ocupacional', 'enfermeira': 'enfermeiro', 'medica': 'medico', 'fonoaudiologa': 'fonoaudiologo'}


def profession(value):
    value = normal(value)
    value = ALIASES.get(value, value)
    if value not in TYPES:
        raise ValueError('Profissão não reconhecida: ' + value)
    return value


HEADERS = ['Carimbo de data/hora', 'Nome do Paciente', 'Data da Evolução', 'Especialidade', 'Evolução', 'Profissional / Conselho Regional', 'Importado?']


@dataclass
class Record:
    key: str
    patient: str
    date: str
    function: str
    content: str
    author: str
    status: str


def fingerprint(values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def parse(values, indices):
    fields = [values[i] if i < len(values) else '' for i in indices]
    if not all(str(x).strip() for x in fields[:6]):
        raise ValueError('Registro com campo obrigatório vazio.')
    date = None
    # The Forms source is month/day/year. Never guess ambiguous dates.
    for fmt in ('%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M'):
        try:
            date = datetime.strptime(fields[2].strip(), fmt)
            break
        except ValueError:
            pass
    if date is None or date.second != 0:
        raise ValueError('Data da Evolução inválida na origem: use MM/DD/AAAA HH:mm ou MM/DD/AAAA HH:mm:00. A exibição será DD/MM/AAAA HH:mm.')
    content = fields[4] + '\n' + fields[5]
    return Record(fingerprint(fields[:6]), fields[1].strip(), date.strftime('%d/%m/%Y %H:%M:%S'), profession(fields[3]), content, fields[5], fields[6].strip())


def load_professionals(path):
    import keyring
    result = {}
    with open(path, encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle, delimiter=';')
        if not {'funcao', 'responsavel_tasy', 'login', 'senha'} <= set(reader.fieldnames or []):
            raise ValueError('Cabeçalho do TXT inválido.')
        for row in reader:
            function = profession(row['funcao'])
            if function in result:
                raise ValueError('Mais de um responsável pela mesma profissão.')
            if not row['login'].strip() or not row['responsavel_tasy'].strip():
                raise ValueError('Responsável e login são obrigatórios.')
            login = row['login'].strip()
            if row['senha']:
                keyring.set_password('RoboEvolutivo', login, row['senha'])
            if not keyring.get_password('RoboEvolutivo', login):
                raise ValueError('Senha ausente no TXT e no cofre para ' + login)
            result[function] = {'login': login, 'name': row['responsavel_tasy'].strip()}
    return result


class Ledger:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, updated TEXT NOT NULL)')
        self.db.execute("UPDATE jobs SET status='Conferir' WHERE status='Em processamento'")
        self.db.commit()

    def get(self, key):
        row = self.db.execute('SELECT status FROM jobs WHERE id=?', (key,)).fetchone()
        return row[0] if row else ''

    def set(self, key, status):
        self.db.execute('INSERT OR REPLACE INTO jobs VALUES (?, ?, ?)', (key, status, datetime.now().isoformat()))
        self.db.commit()
