# Padrões deste projeto

Agente para a competição [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture).
Este arquivo define as convenções que qualquer sessão do Claude Code (ou
qualquer pessoa) deve seguir ao mexer neste repositório. Leia também o
[README](README.md) (visão geral) e o [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md)
(histórico detalhado de decisões) antes de propor mudanças de estratégia.

## Regra de ouro: nunca confie em teoria, meça contra o motor real

Este projeto já foi enganado várias vezes por documentação de terceiros e
por hipóteses "razoáveis" que pareciam corretas mas não eram. **Toda**
mudança de lógica em `main.py` precisa ser validada, nesta ordem, antes de
ser considerada pronta:

1. `python -c "import py_compile; py_compile.compile('main.py', doraise=True)"`
   — checagem de sintaxe.
2. Confirmar que `agent` continua sendo o **último** `def` de nível superior
   no arquivo (o carregador do Kaggle executa o último callable definido, não
   uma função chamada especificamente `agent` — ver o comentário na própria
   função). Se você adicionar uma função depois de `agent`, ela vira a que
   roda de verdade, silenciosamente.
3. `analysis/bench.py` (várias partidas reais contra o motor oficial,
   `kaggle-environments` — não um mock) — compare a média/mínimo/máximo do
   saldo final antes e depois da mudança. Se piorar, reverta, mesmo que a
   mudança "faça sentido" teoricamente (isso já aconteceu — ver rodada 4 do
   development log).
4. `analysis/check_rules.py` — confirma que as 4 regras de negócio abaixo
   continuam 100% respeitadas.

Nunca declare uma mudança como "melhoria" sem os números do passo 3.

## As 4 regras de negócio (do usuário, não negociáveis sem autorização explícita)

1. Nunca deixar o saldo em conta cair abaixo de `RESERVE` ($1000) depois de
   qualquer compra.
2. Só comprar um novo quadrante de terreno quando o atual estiver
   inteiramente ocupado.
3. Nunca ter mais que `MAX_COWS` (13) vacas.
4. Respeitar o tempo de temporada — não iniciar um ciclo de plantio/animal
   que não teria tempo de terminar e ser vendido antes do fim dos 30 dias.

Essas regras só foram relaxadas uma vez, temporariamente, com autorização
explícita do usuário, para testar uma estratégia mais agressiva inspirada em
um oponente real — e foram revertidas depois que a medição mostrou que não
valia a pena (rodada 4 do development log). Não relaxe de novo sem pedir.

## Fonte de verdade sobre as regras do jogo

**Nunca confie em documentação de terceiros sobre a mecânica do jogo.** A
fonte de verdade é o código-fonte do motor oficial, instalado junto com o
pacote `kaggle-environments`:

```
<caminho-do-venv>/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py
```

Documentação de comunidade (READMEs de terceiros, etc.) já levou a pelo
menos dois bugs sérios nas rodadas 1-2 do development log. Se uma mecânica
parece incerta, leia esse arquivo antes de supor.

## Estrutura do projeto

```
main.py              # o agente — precisa ficar na raiz e ser um único arquivo
                      # (é isso que o Kaggle recebe na submissão)
test_smoke.py         # smoke test simplificado, não é o motor oficial
requirements.txt      # dependências pinadas (kaggle-environments, kaggle)
analysis/             # scripts de medição contra o motor oficial
  bench.py            # roda N partidas reais, reporta saldo médio/mín/máx
  check_rules.py       # confere as 4 regras turno a turno numa partida real
docs/
  DEVELOPMENT_LOG.md    # histórico detalhado, rodada a rodada
.claude/skills/         # skills do Claude Code para tarefas recorrentes
  bench/                # /bench
  check-rules/           # /check-rules
  kaggle-submit/         # /kaggle-submit
```

`main.py` **não deve** ser dividido em múltiplos módulos nem movido para uma
subpasta — o Kaggle espera receber um único arquivo (ou um `.tar.gz` com
`main.py` na raiz, mas hoje o agente cabe em um arquivo só e deve continuar
assim enquanto for viável).

## Estilo de código em `main.py`

- Comentários só onde o *porquê* não é óbvio (uma regra do motor não
  documentada, um bug real que foi corrigido, uma decisão de trade-off). Não
  comente o óbvio.
- Ao reverter uma mudança que não funcionou, é aceitável deixar um comentário
  curto dizendo o que foi tentado e por que foi revertido — isso já evitou
  retrabalho (ver rodada 4). Mas mantenha conciso: uma frase ou duas, não um
  parágrafo por decisão. Detalhes longos vão para `docs/DEVELOPMENT_LOG.md`,
  não para dentro do código.
- Sem abstrações prematuras. O arquivo é deliberadamente um único módulo
  plano com funções pequenas — não crie classes ou camadas de indireção sem
  necessidade concreta.

## Antes de submeter para a competição

1. Rodar os 4 passos da "Regra de ouro" acima.
2. Ver o [README § Submissão](README.md#submissão) para os comandos exatos
   (ou usar a skill `/kaggle-submit`).
3. Depois de submeter, sempre conferir o status (`PENDING` → `COMPLETE`) e o
   resultado da partida de validação antes de considerar a submissão boa.
