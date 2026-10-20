# EvolucaoIntensihome

Aplicação Windows/Python com interface Tkinter para carregar respostas do Google Sheets e lançar notas no Tasy pelo navegador, agrupadas por profissão. O responsável pelo login pode ser diferente do autor do Forms.

## Instalação

Para usar sem Python, copie a pasta `dist/EvolucaoIntensihome` inteira e execute `EvolucaoIntensihome.exe`. Existe uma única distribuição final; ZIPs e versões anteriores foram removidos. Consulte `USAR_EM_OUTRO_PC.md`. O pacote inclui Chromium, cadastro de pacientes e histórico, mas não inclui chaves Google nem senhas. O antigo `profissionais.exemplo.txt` foi removido; o cadastro utilizado é `DB/profissionais.txt`.

Para gerar novamente o pacote no computador de desenvolvimento, instale `requirements-build.txt` e execute `.\.venv\Scripts\python.exe build_windows.py`. O ícone é mantido em `assets/robot.ico`.

Execute no PowerShell dentro desta pasta:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python main.py
```

## Conectar Google Sheets

1. No Google Cloud, crie um projeto, habilite a Google Sheets API e crie uma conta de serviço.
2. Crie uma chave JSON dessa conta e guarde fora do repositório.
3. Compartilhe a planilha com o endereço `client_email` do JSON com permissão **Editor**.
4. Na aplicação, selecione esse JSON e informe o link da planilha. A aba é fixa: **Form Responses 1**.
5. Edite os responsáveis em `DB/profissionais.txt` (botão **Profissionais**) e clique **Conectar e carregar**. O caminho é fixo e não precisa ser selecionado.

O link fornecido já está preenchido na interface. A conexão real exige o JSON e o compartilhamento; não há credenciais incluídas. As solicitações usam somente o escopo Sheets.

Cabeçalhos obrigatórios: `Carimbo de data/hora`, `Nome do Paciente`, `Data da Evolução`, `Especialidade`, `Evolução`, `Profissional / Conselho Regional`, `Importado?`.

O conteúdo enviado ao Tasy é **Evolução (coluna E) + quebra de linha + Profissional / Conselho Regional (coluna F)**. A prévia, o diagnóstico e a conferência da nota gravada usam esse mesmo texto completo. Os valores originais das duas colunas são preservados, sem remover uma assinatura já existente na coluna E. A identidade da resposta continua sendo calculada pelos campos de origem, sem permitir reimportar automaticamente registros já confirmados.

A data recebida do Forms é interpretada explicitamente como `MM/DD/AAAA HH:mm` ou `MM/DD/AAAA HH:mm:00`. A tabela da aplicação exibe `DD/MM/AAAA HH:mm` e o Tasy recebe `DD/MM/AAAA HH:mm:00`, com os segundos obrigatórios. Datas ambíguas também seguem mês/dia na origem: `03/04/2026` representa 4 de março. Não há tentativa automática de inverter formatos. O carimbo do envio não é usado como data clínica. O texto original é preservado.

## Responsáveis

Edite `DB/profissionais.txt`. Na primeira inicialização, o TXT já existente na raiz é copiado para esse caminho, sem substituir um cadastro existente em DB. Use UTF-8 e separador ponto e vírgula, com cabeçalho `funcao;responsavel_tasy;login;senha`. Campos com ponto e vírgula devem estar entre aspas. Uma linha por profissão. As senhas são importadas para o cofre do Windows pelo keyring. Depois do primeiro carregamento, remova os valores da coluna `senha` do TXT; mantenha o cabeçalho e a coluna vazia. O nome deve corresponder ao usuário e ao profissional exibidos no Tasy.

## Mapear Tasy antes de executar

Todos os seletores em `config/tasy.json` devem identificar um único elemento visível. A GUI permite a importação direta pelo botão Importar linhas selecionadas, sem diagnóstico prévio ou edição da opção `validated`. As conferências de usuário, paciente, atendimento, prontuário, campos e persistência são executadas em cada evolução.

Use o inspetor Playwright para obter seletores sem gravar credenciais em código:

```powershell
.venv\Scripts\python -m playwright codegen https://tasy.unimedflorianopolis.com.br/#/login
```

Não salve o código gerado com senhas. Campos de cabeçalho precisam retornar apenas o valor completo esperado, sem rótulos. `content` precisa selecionar o editor editável. `note_type` suporta `<select>` nativo ou dropdown personalizado por `note_option`. Elementos em iframe podem ser configurados no objeto `frames` após inspecionar o DOM.

O seletor `patient` usa `{patient}` com o nome de exibição e o atendimento entre parênteses. Se o nome no Tasy for diferente do Forms, configure `name` ou `display` no cadastro de pacientes. `saved_note` deve usar obrigatoriamente `{attendance}`, `{date}`, `{professional}` e `{note_type}` para identificar **a nova linha na tabela de notas**, não o título da tela. A linha precisa mostrar atendimento, data e responsável. Após **Salvar**, o robô clica em **Liberar** no diálogo (`release`), aguarda a nova linha, seleciona essa linha e compara o texto exibido em `saved_content` com o conteúdo enviado. `saved_content` deve identificar o painel de leitura da nota selecionada; o seletor de conteúdo salvo já usa os atributos do editor em modo de leitura, sem fixar o número do ID; a linha completa já foi mapeada por atendimento, data, responsável e tipo nas células SlickGrid, sem depender do índice da linha. A validação no Tasy real permanece pendente. A comparação ignora espaços de formatação e caracteres invisíveis do editor, preservando diferenças de letras, acentos e números. Os placeholders são substituídos por strings entre aspas compatíveis com seletores de texto Playwright. Feche o PEP usando o X da aba do módulo, não o X do painel Conteúdo. Para dropdown personalizado, configure também `note_option` com `{note_type}`; para elementos dentro de iframe, configure `frames` como um objeto que associa a chave do seletor ao seletor CSS do iframe.

Em `config/pacientes.json`, cadastre nomes com identificadores confirmados, por exemplo (dados fictícios):

```json
{
  "Paciente de teste": {
    "display": "PACIENTE DE TESTE (123)",
    "attendance": "123",
    "chart": "456"
  }
}
```

## Uso e recuperação

Clique na seta **▾** do cabeçalho de Paciente, Data, Profissão, Autor / Conselho ou Estado para filtrar essa coluna. Busque um valor, marque/desmarque opções ou clique **Somente exibidos** para selecionar apenas os resultados da busca; finalize com **Aplicar**. Filtros de várias colunas são combinados. **Limpar coluna** remove um filtro; **Limpar filtros** restaura a tabela completa. Uma coluna filtrada recebe o indicador ● e o contador mostra linhas visíveis e total. Linhas ocultadas deixam de estar selecionadas, portanto não entram em uma nova importação. Filtros não alteram a planilha e ficam indisponíveis durante uma execução.

Selecione profissões e linhas, revise o texto e clique **Importar linhas selecionadas**. Para marcar um intervalo, clique na primeira linha e use **Shift + clique** na última, ou mantenha **Shift** pressionado enquanto usa as setas **para baixo / para cima**. O intervalo pode ser ampliado ou reduzido a partir da mesma primeira linha. Ctrl + clique mantém a seleção individual do controle. A descrição acompanha a linha em foco. A importação salva e libera automaticamente as respostas selecionadas e mostra as quantidades importada e ignorada ao terminar. A aplicação interrompe o lote ao primeiro erro. Reinicie e recarregue antes de repetir após correção.

`Sim` é escrito no Sheets somente após confirmação configurada da nota salva. `Em processamento` indica reserva; `Erro` indica falha antes de salvar; `Conferir` exige verificação manual, pois o salvamento pode ter acontecido. A recuperação local transforma tarefas interrompidas em `Conferir`. Se a atualização no Sheets falhar depois de salvar, o SQLite mantém `Sim`, bloqueando repetição local. Corrija a coluna manualmente após conferir o prontuário.

A conclusão lista o motivo de cada linha ignorada, inclusive bloqueios locais em Conferir. Em caso de erro, a mensagem identifica paciente, data, etapa e quantidade já confirmada. Ao reabrir o PEP para outro paciente, a categoria não é recolhida se o paciente já está visível na lista; a confirmação de retorno ao PEP é aguardada após fechar cada evolução.

Execute **uma única instância**, sem outros robôs processando a mesma planilha. O Sheets não fornece transação entre reserva e salvamento. Não ordene, edite nem exclua respostas durante um lote. Cada atualização relocaliza o registro por hash dos campos originais e rejeita duplicações ou alterações. Alterar uma resposta já importada muda sua identidade: revise manualmente antes de nova execução.

O cadastro de profissionais e o banco de estados ficam em `DB/`. Configurações da interface e bloqueio de instância ficam em `data/`. O histórico antigo em `data/jobs.sqlite3` é migrado por backup SQLite quando ainda não existe `DB/jobs.sqlite3`, preservando o original. As respostas clínicas ficam em memória durante a revisão. Não há gravação de screenshots ou logs com conteúdo clínico. As configurações de mapeamento de pacientes também contêm dados sensíveis e não devem ser versionadas. O fluxo aciona Liberar no diálogo após Salvar, conforme autorizado. O diálogo é localizado pelo prefixo ngdialog e pelo botão Liberar visível, sem fixar o número do ID.

A interface sempre inicia no modo claro. O checkbox **Modo noturno**, no canto superior direito junto ao campo Planilha, alterna o tema durante a sessão, incluindo a visualização do conteúdo. A descrição da evolução possui rolagem e um divisor ajustável para ampliar sua área em relação à tabela. A escolha não é persistida. Os guias continuam no projeto, mas seus botões foram removidos da GUI. `iniciar.bat` inicia pelo `pythonw.exe` e encerra o prompt imediatamente, sem deixar uma janela de terminal rodando no fundo.

## Importação agrupada

1. Carregue as respostas do Sheets, habilite as profissões e selecione as linhas desejadas.
2. Clique **Importar linhas selecionadas**. Esse é o único botão de execução; não há etapa de diagnóstico nem confirmação manual por nota na GUI.
3. As respostas são agrupadas por login responsável e paciente, com datas em ordem cronológica dentro de cada paciente. Não há fusão dos textos: cada resposta gera sua própria nota. Profissões com o mesmo login e o mesmo responsável reutilizam a sessão; cadastros contraditórios para um mesmo login são rejeitados antes de iniciar.
4. Para cada resposta, abra PEP, categoria e paciente; confira identificadores; preencha data, tipo e conteúdo; clique Salvar e Liberar no diálogo; selecione a linha gravada e confira seu conteúdo.
5. Ao final de **cada evolução**, feche o PEP pelo X da aba. A próxima resposta percorre novamente o caminho completo, mesmo que seja do mesmo paciente. A sessão só é trocada quando muda o login responsável.
6. Após confirmar a gravação, registre Sim no Sheets. Ao concluir, mostre a quantidade de linhas importadas e ignoradas. Uma confirmação incerta resulta em Conferir e interrompe o processamento. A identidade do usuário é relida no elemento capturado ao fazer login, evitando confusão com assinaturas ou nomes na tabela.

Ao trocar de conta, o robô mantém o menu aberto se Sair já estiver visível, ou reabre o menu pelo nome completo do responsável. Se o cabeçalho tiver sido recriado, a identificação é refeita apenas quando existe uma correspondência única. Somente o Sair visível é acionado. Confirmações nativas reconhecidas de saída são aceitas durante essa etapa; confirmações não reconhecidas interrompem a troca. Se a tela de entrada não aparecer, a rota configurada de login é reaberta. Os campos de usuário e senha precisam estar visíveis antes de encerrar o contexto antigo e iniciar a nova conta; uma página que permaneça autenticada continua bloqueando a troca. Se a saída não puder ser confirmada, o lote é interrompido.

Os botões Executar selecionados, Interromper após etapa atual, Diagnosticar Tasy, Encerrar diagnóstico e Confirmar salvamento foram retirados. Fechar a aplicação durante uma tarefa solicita a interrupção antes do próximo salvamento; aguarde o encerramento da tarefa antes de fechar novamente.

## Validação

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

Os testes verificam datas, preservação do texto, identidade independente do status, recuperação após interrupção, atualização simulada da planilha e navegação/preenchimento/salvamento em uma página HTML fictícia usando Chromium. A autenticação Google e a execução real no Tasy exigem validação com acesso fornecido pelo usuário.

