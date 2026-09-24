---
name: bench
description: Roda o agente Kaggriculture (src/main.py) várias vezes contra o motor oficial do jogo e reporta o saldo final médio/mínimo/máximo. Use sempre que uma mudança de lógica em src/main.py precisar ser validada antes de ser considerada uma melhoria.
---

Este projeto tem uma regra de ouro (ver `CLAUDE.md`): nenhuma mudança em
`src/main.py` deve ser tratada como melhoria sem medição real contra o motor
oficial do jogo. Esta skill automatiza essa medição.

## Passos

1. Confirme que o ambiente virtual do projeto existe e tem as dependências
   instaladas (ver `requirements.txt`). Se `.venv` não existir, siga o
   README § Testando localmente para criá-lo antes de continuar.

2. Rode a checagem de sintaxe primeiro:

   ```
   python -c "import py_compile; py_compile.compile('src/main.py', doraise=True); print('OK')"
   ```

3. Rode o benchmark (padrão: 12-15 partidas reais; ajuste o número passado a
   `analysis/bench.py` se o usuário pedir uma amostra maior ou menor):

   ```
   <venv>/Scripts/python.exe analysis/bench.py 15
   ```

4. Reporte ao usuário: saldo médio, mínimo, máximo, e quantas partidas (se
   houver) tiveram saldo suspeitosamente igual entre si ou exatamente igual
   à reserva mínima ($1000) — isso é sinal de um bug estrutural (deadlock),
   não apenas de resultado ruim (ver README § Como foi desenvolvido para um
   exemplo real).

5. Se havia um resultado "antes" da mudança sendo testada (por exemplo, de
   uma rodada anterior desta mesma conversa), compare explicitamente:
   melhorou, piorou ou ficou dentro da variância normal do jogo (o jogo tem
   variância alta por natureza — diferenças de até ~30% entre rodadas de
   15 partidas não são incomuns).
