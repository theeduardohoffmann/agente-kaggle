# Agente Kaggriculture

Agente autônomo para a competição
[**Kaggriculture**](https://www.kaggle.com/competitions/kaggriculture)
(Kaggle × Google): uma simulação de fazenda 1x1 onde dois jogadores
competem, ao longo de 30 dias de jogo (720 turnos), para terminar com o
maior saldo em dinheiro. Cada jogador administra uma fazenda 10×10 —
plantando, colhendo, criando animais, contratando ajudantes, expandindo
terreno e negociando num mercado dinâmico compartilhado.

**Resultado atual** (medido contra o motor oficial do jogo, não uma
simulação aproximada): saldo final médio de **~$5.000** partindo de $3.000
iniciais (chegando a $12.500+ em partidas favoráveis), respeitando com
precisão as 4 regras de negócio definidas pelo usuário. Veja
[`docs/DEVELOPMENT_LOG.md`](docs/DEVELOPMENT_LOG.md) para o histórico
completo de como esse número evoluiu.

## Como o agente funciona

O `main.py` é uma única função `agent(obs)` que decide, a cada turno, as
ações do fazendeiro principal, de cada ajudante contratado, e as ordens de
mercado. A estratégia é dividida em papéis:

- **Trabalhadores de cultivo** — cada unidade (fazendeiro ou diarista) cuida
  de um lote de ~4 tiles próximas entre si, em ciclo: plantar → regar →
  colher → (se acumular carga) levar ao paiol. A escolha de safra prioriza
  trigo/cenoura no começo da temporada (retorno rápido, baixo risco) e
  diversifica para melão/morango/tomate depois que a fazenda já tem alguma
  folga de caixa — melão sozinho rende ~5x mais por tile-dia que trigo, mas
  leva 12 dias até a primeira colheita.
- **Cuidador de animais** — uma unidade dedicada, uma vez que a fazenda tenha
  diaristas e caixa suficientes, constrói pastos, compra vacas, e prioriza
  sempre alimentar os animais já existentes antes de expandir o rebanho
  (perder um animal por fome é irreversível).
- **Contratação e expansão de terreno** — diaristas são recontratados do
  zero todo dia (o motor não mantém eles de um dia para o outro), então o
  agente hire em lotes pela manhã; terreno novo só é comprado quando o
  quadrante atual está inteiramente ocupado.
- **Mercado** — vendas são feitas aos poucos (drip-sell) para não derrubar o
  preço, com lotes menores para bens premium e maiores para básicos; perto
  do fim da temporada, tudo em estoque é liquidado, já que estoque não
  vendido não conta para a pontuação final.

A lógica de todo o motor (preços, prazos de colheita, mecânica de
plantio/contratação) foi extraída diretamente do **código-fonte oficial** do
motor de jogo, não de documentação de terceiros — ver a nota em
`CLAUDE.md` § Fonte de verdade.

## Como foi desenvolvido

Este agente passou por 4 rodadas de investigação e ajuste, cada uma medida
contra o motor oficial do jogo (não contra suposições). Resumo:

1. **Rodada 1** — primeira vez rodando contra o motor real expôs 5 bugs
   sérios (incluindo um em que o próprio código de proteção contra erros
   nunca era executado pelo carregador do Kaggle). Corrigidos, saldo médio
   foi de instável para ~$3.600.
2. **Rodada 2** — a fazenda ficava presa num único campo; a causa era um lote
   de trabalho mal agrupado (tiles à mesma distância do paiol mas em lados
   opostos do campo viravam erva daninha por falta de rega). Corrigido,
   saldo médio subiu para ~$6.500.
3. **Rodada 3** — testadas várias otimizações adicionais; a maioria piorou o
   resultado (expandir terreno mais cedo, investir em gado mais cedo), mas
   vender em lotes maiores ajudou de verdade.
4. **Rodada 4** — depois de uma derrota real na competição, o replay do
   oponente foi analisado (via `kaggle competitions replay`) e mostrou uma
   estratégia bem mais agressiva. Tentativas de replicá-la pioraram o
   resultado aqui (e uma delas chegou a violar a própria regra de reserva
   mínima do usuário) — revertidas, mas um bug real e independente da
   estratégia foi encontrado e corrigido no processo.

Veja [`docs/DEVELOPMENT_LOG.md`](docs/DEVELOPMENT_LOG.md) para o relato
completo de cada rodada, incluindo o que foi tentado e não funcionou.

## Estrutura do projeto

```
main.py                 # o agente — arquivo único, pronto para submissão
test_smoke.py            # smoke test simplificado (não é o motor oficial)
requirements.txt         # dependências pinadas
analysis/
  bench.py               # roda N partidas reais, reporta saldo médio/mín/máx
  check_rules.py          # confere as 4 regras de negócio turno a turno
docs/
  DEVELOPMENT_LOG.md       # histórico detalhado de desenvolvimento
CLAUDE.md                 # padrões e convenções do projeto
.claude/skills/            # skills do Claude Code (/bench, /check-rules, /kaggle-submit)
```

`main.py` fica na raiz de propósito e não é dividido em módulos — é o que o
Kaggle espera receber na submissão (ver `CLAUDE.md`).

## Regras de negócio (definidas pelo usuário, implementadas em `main.py`)

1. **Reserva mínima de $1.000** — nenhuma compra pode deixar o saldo abaixo
   disso.
2. **Só expandir terreno quando o campo atual estiver inteiramente
   ocupado.**
3. **Máximo de 13 vacas.**
4. **Respeitar o tempo de temporada** — não iniciar um plantio ou ciclo
   animal que não teria tempo de terminar e ser vendido antes do dia 30;
   liquidar tudo que sobrar no paiol perto do fim.

Todas as 4 são reconferidas automaticamente, turno a turno, por
`analysis/check_rules.py` contra o motor oficial.

## Testando localmente (passo a passo, terminal do VS Code)

O Python padrão pode não instalar o `kaggle-environments` diretamente (uma
das suas dependências, `pygame`, nem sempre tem wheel pré-compilada para a
versão mais recente do Python no Windows). Se a instalação travar tentando
compilar do zero, use uma versão de Python mais antiga (3.12 é a testada e
validada neste projeto) via `py -3.12`. Todos os comandos abaixo são para o
terminal **PowerShell** do VS Code (padrão no Windows) — rode-os sempre a
partir da pasta do projeto.

### 1. Abrir a pasta certa no terminal

```powershell
cd "C:\Users\eduar\Desktop\agente-kaggle"
```

### 2. Criar um ambiente virtual (só precisa fazer uma vez)

```powershell
py -3.12 -m venv .venv
```

Isso cria uma pasta `.venv` isolada, sem mexer no Python que você já usa
para outras coisas.

### 3. Ativar o ambiente virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear com um erro de "execution policy", rode uma vez
(autoriza scripts só para o seu usuário):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

e tente ativar de novo. Quando ativado, o prompt passa a mostrar `(.venv)`
no início da linha. **Repita este passo toda vez que abrir um terminal
novo** (o passo 2 é só uma vez).

### 4. Instalar as dependências (só precisa fazer uma vez por ambiente)

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Rodar um episódio completo localmente

Com o ambiente ativado (prompt mostrando `(.venv)`):

```powershell
python -c "from kaggle_environments import make; env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True); env.run(['main.py', 'random']); print([(i, s.reward, s.status) for i, s in enumerate(env.steps[-1])])"
```

Isso joga uma partida completa (720 turnos) do seu `main.py` contra o agente
`"random"` e imprime, para cada jogador, `(índice, saldo final, status)`.
`status` deve ser `"DONE"` — se aparecer `"ERROR"` ou `"INVALID"`, algo no
agente quebrou (o Kaggle mostra o traceback nesse caso).

Ou, de forma mais direta, use a skill `/bench` (roda várias partidas de uma
vez e resume o resultado) ou `analysis/bench.py` diretamente.

### 6. Ver a partida visualmente (renderiza um HTML e abre num servidor local)

O `env.render(mode="ipython", ...)` só funciona dentro de um notebook
Jupyter. Do terminal puro, gere o replay como HTML autossuficiente e sirva
localmente:

```powershell
python -c "from kaggle_environments import make; env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True); env.run(['main.py', 'random']); open('replay.html', 'w', encoding='utf-8').write(env.render(mode='html'))"
python -m http.server 8000
```

Depois abra `http://localhost:8000/replay.html` no navegador — o
visualizador oficial do jogo abre com um controle de linha do tempo (play,
pular pro fim, arrastar a barra) mostrando os dois tabuleiros lado a lado.
`Ctrl+C` no terminal encerra o servidor quando terminar.

### 7. (Opcional) Smoke test rápido

Não é o motor oficial — uma simulação simplificada usada como teste rápido
adicional:

```powershell
python test_smoke.py
```

## Submissão (passo a passo)

Ou use a skill `/kaggle-submit`, que automatiza estes passos com uma
confirmação antes do envio em si.

### 1. Configurar as credenciais da API do Kaggle (só uma vez)

1. Acesse https://www.kaggle.com/settings/api e clique em **"Create New
   Token"**. Isso baixa um arquivo `kaggle.json`.
2. Mova esse arquivo para a pasta que o CLI espera:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.kaggle" | Out-Null
Move-Item "$env:USERPROFILE\Downloads\kaggle.json" "$env:USERPROFILE\.kaggle\kaggle.json" -Force
```

(ajuste o caminho se você baixou o arquivo em outra pasta)

### 2. Aceitar as regras da competição

Isso só pode ser feito pelo navegador — abra
https://www.kaggle.com/competitions/kaggriculture, faça login e clique em
**"Join Competition"** / **"I Understand and Accept"**. Sem isso, o `submit`
abaixo falha com erro de permissão.

### 3. Confirmar que está inscrito

```powershell
.\.venv\Scripts\Activate.ps1
kaggle competitions list --group entered
```

Você deve ver `kaggriculture` na lista.

### 4. Enviar o agente

```powershell
kaggle competitions submit kaggriculture -f main.py -m "descrição da mudança"
```

Se `main.py` precisar de outros arquivos junto no futuro, empacote tudo em
um `.tar.gz` com `main.py` na raiz e submeta o pacote em vez do arquivo
único (hoje não é necessário — o agente é um único arquivo, de propósito,
ver `CLAUDE.md`).

### 5. Acompanhar a submissão

```powershell
kaggle competitions submissions kaggriculture
```

Anote o `ID` da submissão que aparecer, e use nos comandos abaixo:

```powershell
kaggle competitions episodes <ID_DA_SUBMISSAO>
kaggle competitions leaderboard kaggriculture -s
```

Para baixar o replay ou os logs de uma partida específica (para depurar por
que uma decisão foi tomada), pegue o `EPISODE_ID` do comando `episodes`
acima:

```powershell
kaggle competitions replay <EPISODE_ID> -p .\replays
kaggle competitions logs <EPISODE_ID> 0 -p .\logs
```

## Contribuindo

Veja [`CLAUDE.md`](CLAUDE.md) para os padrões deste projeto: como validar
qualquer mudança antes de considerá-la pronta, onde está a fonte de verdade
sobre as regras do jogo, e o estilo de código esperado.
