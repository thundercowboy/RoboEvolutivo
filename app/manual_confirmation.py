from datetime import datetime
import getpass


def confirm_records(records, sheets, ledger, prefix, report):
    # Check all source identities before changing any status.
    for record in records:
        sheets.locate(record)
    ledger.db.execute('CREATE TABLE IF NOT EXISTS manual_confirmations (id TEXT, confirmed_at TEXT, operator TEXT)')
    ledger.db.commit()
    confirmed = 0
    for record in records:
        key = prefix + record.key
        ledger.set(key, 'Sim')
        ledger.db.execute('INSERT INTO manual_confirmations VALUES (?,?,?)',
                          (key, datetime.now().isoformat(), getpass.getuser()))
        ledger.db.commit()
        report(record.key, 'Sim')
        try:
            sheets.status(record, 'Sim')
        except Exception:
            raise ValueError(
                f'{record.patient} — {record.date}: confirmação preservada no SQLite, '
                f'mas o Google Sheets não foi atualizado. Linhas atualizadas no Sheets: {confirmed}. '
                'Reconecte e repita Confirmar Registro; não execute a importação novamente.'
            ) from None
        confirmed += 1
    return confirmed
