---
name: check-rules
description: Confere se o agente Kaggriculture (src/main.py) respeita as 4 regras de negócio do usuário (reserva mínima de $1000, expandir terreno só quando cheio, máximo 13 vacas, respeitar o tempo de safra) turno a turno numa partida real contra o motor oficial. Use depois de qualquer mudança em src/main.py, antes de submeter para a competição.
---

## Passos

1. Confirme que o ambiente virtual do projeto existe e tem as dependências
   instaladas (ver `requirements.txt`).

2. Rode a checagem de regras:

   ```
   <venv>/Scripts/python.exe analysis/check_rules.py
   ```

3. O script imprime, ao final: saldo mínimo observado, número máximo de
   vacas possuídas, se algum terreno foi comprado com tiles ainda vazias, e
   qualquer violação encontrada turno a turno.

4. Interprete o resultado:
   - `min money ever` deve ser **>= 1000**. Se for menor, é uma violação real
     da regra 1 — não ignore, mesmo que pareça pequena (ex: $998).
   - `max cows ever` deve ser **<= 13**.
   - `land bought while tiles still empty` deve ser **False**.
   - Ausência de linhas `VIOLATION:` no output.

5. Se encontrar uma violação, rode de novo 2-3 vezes (o jogo tem elementos
   aleatórios — ervas daninhas, mercado — então uma violação pode ser rara).
   Se for consistente, é um bug real em `main.py` e deve ser corrigido antes
   de considerar a mudança pronta, independente do quanto ela melhorou o
   lucro médio.
