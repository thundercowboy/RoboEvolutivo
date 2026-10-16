from .core import HEADERS, normal, parse, fingerprint


class Sheets:
    def __init__(self, credentials, url, tab):
        import json
        import gspread
        with open(credentials, encoding='utf-8') as handle:
            info = json.load(handle)
        if info.get('type') != 'service_account':
            raise ValueError('Selecione um JSON de conta de serviço do Google.')
        client = gspread.service_account(filename=credentials, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client.set_timeout(30)
        book = client.open_by_url(url)
        self.sheet = book.worksheet(tab) if tab.strip() else book.get_worksheet(0)

    def snapshot(self):
        values = self.sheet.get_all_values()
        if not values:
            raise ValueError('Planilha vazia.')
        headers = [normal(v) for v in values[0]]
        indices = []
        for header in HEADERS:
            if headers.count(normal(header)) != 1:
                raise ValueError('Coluna ausente ou repetida: ' + header)
            indices.append(headers.index(normal(header)))
        return values, indices

    def read(self):
        values, indices = self.snapshot()
        records, errors, seen = [], [], set()
        for row_number, row in enumerate(values[1:], 2):
            if not any(row):
                continue
            try:
                record = parse(row, indices)
                if record.key in seen:
                    raise ValueError('Resposta duplicada; corrija a planilha antes de executar.')
                seen.add(record.key)
                records.append(record)
            except ValueError as error:
                errors.append(f'Linha {row_number}: {error}')
        if errors:
            raise ValueError('\n'.join(errors))
        return records

    def locate(self, record):
        values, indices = self.snapshot()
        matches = []
        for number, row in enumerate(values[1:], 2):
            fields = [row[i] if i < len(row) else '' for i in indices]
            if fingerprint(fields[:6]) == record.key:
                matches.append((number, fields[6].strip()))
        if len(matches) != 1:
            raise ValueError('Resposta alterada, removida ou duplicada na planilha. Recarregue.')
        return matches[0], indices[-1] + 1

    def claim(self, record):
        (_, status), _ = self.locate(record)
        if normal(status) not in ('', 'pendente', 'erro'):
            raise ValueError('Registro já processado ou pendente de conferência.')
        self.status(record, 'Em processamento')

    def status(self, record, status):
        (row, _), column = self.locate(record)
        self.sheet.update_cell(row, column, status)
