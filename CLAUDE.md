# Padrões deste projeto

Agente para a competição [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture).
Este arquivo define as convenções que qualquer sessão do Claude Code (ou
qualquer pessoa) deve seguir ao mexer neste repositório. Leia também o
[README](README.md) — é a única fonte de explicação sobre como o agente
funciona e como o projeto evoluiu; este arquivo cobre só convenções de
trabalho.

## Regra de ouro: nunca confie em teoria, meça contra o motor real

Este projeto já foi enganado várias vezes por documentação de terceiros e
por hipóteses "razoáveis" que pareciam corretas mas não eram (ver README §
Como foi desenvolvido). **Toda** mudança de lógica em `src/main.py` precisa
ser validada, nesta ordem, antes de ser considerada pronta:

1. `python -c "import py_compile; py_compile.compile('src/main.py', doraise=True)"`
   — checagem de sintaxe.
2. Confirmar que `agent` continua sendo o **último** `def` de nível superior
   no arquivo. O carregador do Kaggle executa o último callable definido no
   arquivo, não uma função chamada especificamente `agent` — se você
   adicionar uma função depois de `agent`, ela vira a que roda de verdade,
   silenciosamente, sem erro nenhum avisando.
3. `python analysis/bench.py 15` (várias partidas reais contra o motor
   oficial, `kaggle-environments` — nunca um mock) — compare a
   média/mínimo/máximo do saldo final antes e depois da mudança. Se piorar,
   reverta, mesmo que a mudança "faça sentido" teoricamente.
4. `python analysis/check_rules.py` — confirma que as 4 regras de negócio
   abaixo continuam 100% respeitadas.

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
valia a pena (ver README). Não relaxe de novo sem pedir.

## Fonte de verdade sobre as regras do jogo

**Nunca confie em documentação de terceiros sobre a mecânica do jogo.** A
fonte de verdade é o código-fonte do motor oficial, instalado junto com o
pacote `kaggle-environments`:

```
<caminho-do-venv>/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py
```

Se uma mecânica parece incerta, leia esse arquivo antes de supor.

## Estrutura do projeto

```
src/
  main.py              # o agente — arquivo único, ponto de entrada da submissão
  test_smoke.py         # smoke test simplificado, não é o motor oficial
requirements.txt        # dependências pinadas (kaggle-environments, kaggle)
analysis/                # scripts de medição contra o motor oficial
  bench.py               # roda N partidas reais, reporta saldo médio/mín/máx
  check_rules.py          # confere as 4 regras turno a turno numa partida real
.claude/skills/            # skills do Claude Code para tarefas recorrentes
  bench/                   # /bench
  check-rules/              # /check-rules
  kaggle-submit/            # /kaggle-submit
```

`src/main.py` **não deve** ser dividido em múltiplos módulos — o Kaggle
espera receber um único arquivo (ou um `.tar.gz` com `main.py` na raiz do
pacote, mas hoje o agente cabe em um arquivo só e deve continuar assim
enquanto for viável).

## Estilo de código

- **Sem comentários explicativos no código.** Toda explicação de como e por
  que o agente funciona vai no README, não em `src/main.py` — o código deve
  ser lido junto com o README, não sozinho. A única exceção: cada uma das 4
  regras de negócio tem exatamente **um comentário de uma linha** no ponto
  do código onde é aplicada (ex: `# rule 1: ...`), só o suficiente para
  achar rapidamente onde cada regra está implementada.
- Ao mudar essa convenção — adicionar de volta um comentário maior, por
  exemplo — atualize o README na mesma mudança, não deixe as duas fontes
  divergirem.
- Sem abstrações prematuras. O arquivo é deliberadamente um único módulo
  plano com funções pequenas — não crie classes ou camadas de indireção sem
  necessidade concreta.

## Antes de submeter para a competição

1. Rodar os 4 passos da "Regra de ouro" acima.
2. Ver o [README § Submissão](README.md#submissão) para os comandos exatos
   (ou usar a skill `/kaggle-submit`).
3. Depois de submeter, sempre conferir o status (`PENDING` → `COMPLETE`) e o
   resultado da partida de validação antes de considerar a submissão boa.
