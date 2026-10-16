# Conectar sua planilha ao RoboEvolutivo

Planilha configurada: https://docs.google.com/spreadsheets/d/1J-5Z5jE1O3pfsewoGkjWCfH362KgnI7r3-IMEAfVMnI/edit?usp=sharing

## 1. Criar o projeto

Acesse https://console.cloud.google.com/ com a conta que administra a planilha. No seletor de projetos, crie um projeto chamado RoboEvolutivo. Selecione esse projeto antes dos próximos passos.

## 2. Habilitar a API

Em **APIs e serviços → Biblioteca**, procure **Google Sheets API** e clique em **Ativar**. A aplicação não precisa da API do Tasy nem do banco clínico.

## 3. Criar a conta de serviço

Em **IAM e administrador → Contas de serviço → Criar conta de serviço**, informe `robo-evolutivo`. Conclua a criação. Para acessar somente a planilha compartilhada, não é necessário conceder papel de administrador do projeto nem delegação de domínio.

Abra a conta criada e copie o endereço semelhante a:

`robo-evolutivo@SEU-PROJETO.iam.gserviceaccount.com`

## 4. Baixar a credencial JSON

Na conta de serviço, abra **Chaves → Adicionar chave → Criar nova chave → JSON → Criar**. O arquivo será baixado. Guarde em uma pasta privada, fora do repositório, por exemplo em Documentos/RoboEvolutivo/credencial-google.json. Não cole o conteúdo do JSON no chat. Se a organização bloquear a criação de chaves, peça ao administrador a forma de autenticação autorizada; esta versão utiliza conta de serviço com chave JSON.

## 5. Compartilhar a planilha

Abra sua planilha e clique **Compartilhar**. Adicione o e-mail da conta de serviço como **Editor**. Desmarque a notificação por e-mail e confirme o compartilhamento. A conta precisa editar a coluna `Importado?`.

Não é necessário tornar a planilha pública.

## 6. Configurar a aplicação

1. Abra `iniciar.bat`.
2. Em **Credenciais Google**, selecione o arquivo JSON baixado.
3. Confirme que a guia da planilha tem o nome **Form Responses 1**. Essa aba é fixa na aplicação.
4. Edite `DB/profissionais.txt` pelo botão **Profissionais**. O arquivo é carregado automaticamente, sem seleção de caminho.
5. Clique **Conectar e carregar**. A conexão será confirmada quando as respostas aparecerem na tabela.

O cadastro de profissionais e os identificadores dos pacientes são configurações separadas da autenticação Google. O robô confere o mapeamento e os identificadores a cada lançamento pelo botão Importar linhas selecionadas.

## Se não conectar

- **Arquivo incorreto:** selecione o JSON de uma conta de serviço, não um JSON OAuth ou outro arquivo.
- **Permissão negada / planilha não encontrada:** confira o compartilhamento com o `client_email` do arquivo e a ativação da API no projeto correto.
- **Aba não encontrada:** a guia inferior precisa se chamar exatamente `Form Responses 1`. `Form_Responses` pode ser o nome da tabela, não o nome da aba.
- **Coluna ausente:** confira os sete cabeçalhos documentados no README. `Profissional / Conselho Regional` e `Importado?` devem existir uma única vez.

Referência oficial: https://developers.google.com/workspace/guides/create-credentials#service-account
