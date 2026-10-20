# Dados locais

O arquivo de responsáveis fica em `DB/profissionais.txt` e é carregado automaticamente. Use UTF-8 e o cabeçalho:

```text
funcao;responsavel_tasy;login;senha
```

Uma linha por profissão. As senhas são guardadas no cofre do Windows após o primeiro carregamento; depois disso, a coluna senha pode ficar vazia. O botão **Profissionais** abre o arquivo para edição.

Na primeira inicialização, a aplicação copia o TXT existente na raiz para esta pasta, se houver. Arquivos existentes em DB nunca são substituídos por essa inicialização.

`DB/jobs.sqlite3` armazena os estados de importação. O histórico antigo em `data/jobs.sqlite3`, se existir, é copiado usando o backup do SQLite quando não houver um banco novo. O arquivo original é preservado.

Os arquivos locais desta pasta são ignorados pelo Git, exceto este documento.
