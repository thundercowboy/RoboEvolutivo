"""Preflight only: deliberately no Sheets, ledger, save or release calls."""


def diagnose(robot, record, user, report):
    report('Iniciar navegador', 'Em andamento', '')
    robot.start()
    report('Iniciar navegador', 'OK', '')
    robot.login(user)
    robot.prepare(record, user)
    report('Diagnóstico', 'OK', 'Preenchimento concluído. Confira o navegador e encerre o diagnóstico para descartar o rascunho.')
