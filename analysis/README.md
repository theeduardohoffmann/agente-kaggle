# Scripts de análise

Scripts usados para medir e validar o agente (`../main.py`) contra o **motor
oficial** do jogo (`kaggle-environments`), não contra suposições ou
documentação de terceiros. Veja `../CLAUDE.md` para a regra de ouro deste
projeto: nenhuma mudança em `main.py` é considerada melhoria sem passar por
esses dois scripts.

## `bench.py`

Roda N partidas completas (padrão: contra o agente `"random"` do próprio
motor) e reporta o saldo final médio, mínimo e máximo.

```bash
python bench.py 15
```

## `check_rules.py`

Roda uma partida completa e confere, turno a turno, as 4 regras de negócio
do usuário (reserva mínima de $1000, expandir terreno só quando cheio,
máximo 13 vacas, respeitar o tempo de safra). Imprime qualquer violação
encontrada, além de um resumo final (saldo mínimo observado, máximo de vacas,
etc.).

```bash
python check_rules.py
```

Ambos os scripts esperam ser rodados com o Python do ambiente virtual do
projeto (ver `../README.md` § Testando localmente) e a partir da raiz do
repositório ou desta pasta — eles ajustam o `sys.path` automaticamente para
importar `main.py` da raiz.
