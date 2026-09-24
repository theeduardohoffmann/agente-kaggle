---
name: kaggle-submit
description: Valida e submete o agente Kaggriculture (src/main.py) para a competição no Kaggle, depois acompanha o status da submissão. Use quando o usuário pedir para submeter, enviar ou colocar o agente na competição.
---

Submeter consome uma das submissões diárias permitidas pela competição e
fica visível no leaderboard — **sempre confirme com o usuário antes do passo
5** (o envio em si), mesmo que os passos anteriores tenham passado limpos.

## Passos

1. Rode a checagem de sintaxe:

   ```
   python -c "import py_compile; py_compile.compile('src/main.py', doraise=True); print('OK')"
   ```

2. Rode `/bench` e `/check-rules` (ou os comandos equivalentes de
   `analysis/bench.py` e `analysis/check_rules.py`) para confirmar que o
   agente está funcionando e respeitando as regras antes de gastar uma
   submissão.

3. Confirme que as credenciais da API do Kaggle estão configuradas
   (`~/.kaggle/kaggle.json` deve existir) e que o usuário já está inscrito na
   competição:

   ```
   <venv>/Scripts/python.exe -m kaggle competitions list --group entered
   ```

   Se `kaggriculture` não aparecer na lista, o usuário precisa aceitar as
   regras da competição pelo navegador primeiro (ver README § Submissão)
   antes de continuar.

4. Peça uma mensagem curta para a submissão (ou proponha uma descrevendo a
   mudança principal desta rodada), e **pergunte ao usuário se pode
   prosseguir com o envio** antes do próximo passo.

5. Depois de confirmado, submeta:

   ```
   <venv>/Scripts/python.exe -m kaggle competitions submit kaggriculture -f src/main.py -m "MENSAGEM_AQUI"
   ```

6. Confirme o status:

   ```
   <venv>/Scripts/python.exe -m kaggle competitions submissions kaggriculture
   ```

   O status começa como `PENDING` (validação, pode levar minutos a horas) e
   depois vira `COMPLETE` (pronto para entrar na fila de partidas
   ranqueadas) ou `ERROR` (algo quebrou — nesse caso, baixe os logs da
   partida de validação com `kaggle competitions episodes <SUBMISSION_ID>`
   seguido de `kaggle competitions logs <EPISODE_ID> 0` para depurar).

7. Reporte ao usuário: ID da submissão, status atual, e os comandos para
   acompanhar depois (`kaggle competitions episodes <ID>`,
   `kaggle competitions leaderboard kaggriculture -s`).
