"""Order individual notes to reuse each responsible account's session."""
from datetime import datetime
from collections import Counter
from .core import normal


def ordered_imports(records, professionals):
    accounts = {}
    for record in records:
        user = professionals.get(record.function)
        if not user or not user.get('login') or not user.get('name'):
            raise ValueError('Sem responsável configurado para ' + record.function)
        login, name = user['login'], normal(user['name'])
        if login in accounts and accounts[login] != name:
            raise ValueError('O mesmo login foi cadastrado com responsáveis diferentes. Confira o TXT.')
        accounts[login] = name
    counts = Counter(professionals[r.function]['login'] for r in records)
    return sorted(records, key=lambda r: (-counts[professionals[r.function]['login']], professionals[r.function]['login'], normal(r.patient), datetime.strptime(r.date, '%d/%m/%Y %H:%M:%S'), r.key))
