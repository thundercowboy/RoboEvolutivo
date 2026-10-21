# EvolucaoIntensihome — Windows portátil

1. Copie toda a pasta dist/EvolucaoIntensihome para uma pasta com permissão de escrita, por exemplo Documentos/EvolucaoIntensihome. Use Windows 10 ou 11 de 64 bits.
2. Abra EvolucaoIntensihome.exe. Mantenha todas as pastas junto ao executável, inclusive _internal e browsers. Python e instalação do navegador não são necessários.
3. Copie seu JSON de autenticação Google por um meio privado para esse computador e selecione-o em Credenciais Google. A planilha já está configurada, com aba Form Responses 1.
4. Clique em Profissionais e preencha a coluna senha para cada login em DB/profissionais.txt. O cadastro é fornecido sem senhas; o cofre Windows é específico de cada computador. Após carregar com sucesso, pode apagar somente os valores das senhas do TXT, mantendo as colunas.
5. Clique em Conectar e carregar e revise os dados antes de importar.

O cadastro de pacientes e uma cópia do histórico SQLite acompanham o pacote. Não execute importações simultâneas em computadores diferentes. Para mudar de computador futuramente, feche a aplicação e transfira a pasta DB atualizada junto com config e data; cada cópia contém somente o histórico existente quando foi transferida. Senhas no cofre precisam ser cadastradas novamente na nova máquina.

Internet e acesso ao Tasy são necessários. O aplicativo não altera a instalação do computador e não solicita administrador. Não coloque a pasta em Arquivos de Programas.

Para atualizar o executável, preserve DB, config e data do computador em uso. Não substitua essas pastas por cópias antigas do pacote.

Após conferir manualmente uma nota salva e liberada no Tasy, selecione sua linha e use Confirmar Registro. Confirme os itens exibidos para marcar Importado? como Sim na planilha e preservar o bloqueio no SQLite, sem lançar novamente. A confirmação aceita várias linhas selecionadas.

Na seta da coluna Data, informe De e Até em DD/MM/AAAA, com horário HH:mm opcional. A data final sem horário inclui o dia inteiro; um limite vazio não restringe esse lado do período.

Use o botão Calendário ao lado de De ou Até para selecionar o dia com um clique. As setas mudam o mês e o botão Hoje seleciona a data atual. Um horário já digitado é mantido ao trocar a data.
