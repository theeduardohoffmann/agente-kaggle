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
precisão as 4 regras de negócio definidas pelo usuário.

## Estrutura do projeto

```
src/
  main.py               # o agente — arquivo único, ponto de entrada da submissão
  test_smoke.py          # smoke test simplificado (não é o motor oficial)
analysis/
  bench.py               # roda N partidas reais, reporta saldo médio/mín/máx
  check_rules.py          # confere as 4 regras de negócio turno a turno
.claude/skills/           # skills do Claude Code (/bench, /check-rules, /kaggle-submit)
requirements.txt
CLAUDE.md                  # convenções do projeto para sessões futuras do Claude Code
```

`src/main.py` é intencionalmente um único arquivo sem módulos internos — é
o que o Kaggle recebe na submissão (veja a seção Submissão abaixo).

## Como o agente funciona

O `agent(obs)` em `src/main.py` decide, a cada turno, as ações do fazendeiro
principal, de cada ajudante contratado, e as ordens de mercado. A estratégia
é dividida em papéis:

- **Trabalhadores de cultivo** — cada unidade (fazendeiro ou diarista) cuida
  de um lote de ~4 tiles próximas entre si, em ciclo: plantar → regar →
  colher → (se acumular carga) levar ao paiol. A escolha de safra prioriza
  trigo/cenoura no começo da temporada (retorno rápido, baixo risco) e
  diversifica para melão/morango/tomate depois que a fazenda já tem alguma
  folga de caixa — melão sozinho rende ~5x mais por tile-dia que trigo, mas
  leva 12 dias até a primeira colheita, então plantá-lo cedo demais crashava
  a economia inteira antes de qualquer venda acontecer.
- **Cuidador de animais** — uma unidade dedicada, uma vez que a fazenda tenha
  diaristas e caixa suficientes, constrói pastos, compra vacas, e prioriza
  sempre alimentar os animais já existentes antes de expandir o rebanho
  (perder um animal por fome é irreversível — duas alimentações perdidas
  seguidas e o animal foge para sempre).
- **Contratação e expansão de terreno** — diaristas são recontratados do
  zero todo dia (o motor não mantém eles de um dia para o outro, custo
  Fibonacci reiniciando), então o agente contrata em lotes pela manhã, um
  trabalhador por lote de tiles (não um por tile — cobrir a fazenda inteira
  com 1 trabalhador por tile custaria a folha de pagamento inteira em
  contratação). Terreno novo só é comprado quando o quadrante atual está
  inteiramente ocupado.
- **Mercado** — vendas são feitas aos poucos (drip-sell) para não derrubar o
  preço, com lotes menores para bens premium e maiores para básicos; perto
  do fim da temporada, tudo em estoque é liquidado, já que estoque não
  vendido não conta para a pontuação final.

A lógica de todo o motor (preços, prazos de colheita, mecânica de
plantio/contratação) foi extraída diretamente do **código-fonte oficial** do
motor de jogo (`kaggle_environments/envs/kaggriculture/kaggriculture.py`,
instalado junto do pacote — veja o passo 4 da seção de teste abaixo), não de
documentação de terceiros. Isso importa: documentação de comunidade levou a
pelo menos dois bugs sérios no início do desenvolvimento (mecânica de
respawn diário das unidades, e uma validação atômica de plantio não
documentada — se o total de pedidos de `PLANT` de uma safra num turno passa
do estoque de sementes, o motor cancela **todos** os pedidos, não só o
excedente).

## Regras de negócio (definidas pelo usuário, implementadas em `src/main.py`)

1. **Reserva mínima de $1.000** — nenhuma compra pode deixar o saldo abaixo
   disso.
2. **Só expandir terreno quando o campo atual estiver inteiramente
   ocupado** — evita gastar em mais terra antes de conseguir cuidar da que
   já existe.
3. **Máximo de 13 vacas** — limite superior para o rebanho, não uma meta a
   forçar.
4. **Respeitar o tempo de temporada** — não iniciar um plantio ou ciclo
   animal que não teria tempo de terminar e ser vendido antes do dia 30;
   liquidar tudo que sobrar no paiol perto do fim.

Todas as 4 são reconferidas automaticamente, turno a turno, por
`analysis/check_rules.py` contra o motor oficial. No código, cada regra tem
exatamente um comentário de uma linha no ponto onde é aplicada.

## Como foi desenvolvido

O agente passou por várias rodadas de investigação e ajuste, cada uma medida
contra o motor oficial do jogo (nunca contra suposições):

- **Bugs de fundação** — a primeira vez rodando contra o motor real (não um
  harness simplificado feito à mão) expôs vários bugs sérios: o próprio
  código de proteção contra erros nunca era executado (o carregador do
  Kaggle roda o *último* `def` do arquivo, não uma função chamada `agent`
  especificamente); a validação atômica de plantio mencionada acima; e um
  deadlock de caixa em que a escolha de safra exigia reserva demais para
  sequer considerar plantar, uma vez que o saldo caísse perto do piso.
- **Fazenda presa num único campo** — a causa era um lote de trabalho mal
  agrupado: tiles à mesma distância do paiol mas em lados opostos do campo
  viravam erva daninha por falta de rega, já que os lotes eram formados por
  proximidade do paiol, não entre si.
- **Otimizações de venda** — o teto de venda por turno (para não derrubar o
  preço de mercado) estava mais conservador do que a curva real de preço do
  jogo suporta; aumentá-lo ajudou de verdade. Tentativas de expandir terreno
  ou investir em gado mais cedo, por outro lado, pioraram o resultado — o
  gargalo real do jogo é o custo de contratação diário (reinicia todo dia)
  crescendo mais rápido que a receita sempre que a fazenda expande rápido
  demais.
- **Tentativa de imitar um oponente real** — depois de uma derrota na
  competição, o replay do oponente foi baixado (`kaggle competitions
  replay`) e mostrou uma estratégia bem mais agressiva: terra, animais e
  safras premium desde o dia 0, tolerando caixa quase zero por um bom tempo
  antes de explodir exponencialmente. Reproduzir isso literalmente (reserva
  bem mais baixa, gatilhos de investimento mais soltos) piorou o resultado
  aqui em toda tentativa — a mecânica de trabalhadores deste agente não é
  eficiente o bastante ainda para sobreviver a esse nível de risco do jeito
  que o oponente sobrevive — e uma das tentativas chegou a violar a própria
  regra de reserva mínima do usuário. Revertido para os valores validados,
  mantendo apenas um bug real e independente da estratégia que foi
  encontrado no processo (um trabalhador sem sementes ficava parado numa
  tile vazia, abandonando as outras tiles do seu lote mesmo com colheita
  pronta esperando).

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
python -c "from kaggle_environments import make; env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True); env.run(['src/main.py', 'random']); print([(i, s.reward, s.status) for i, s in enumerate(env.steps[-1])])"
```

Isso joga uma partida completa (720 turnos) do agente contra o agente
`"random"` e imprime, para cada jogador, `(índice, saldo final, status)`.
`status` deve ser `"DONE"` — se aparecer `"ERROR"` ou `"INVALID"`, algo no
agente quebrou (o Kaggle mostra o traceback nesse caso).

Ou, de forma mais direta, use a skill `/bench` (roda várias partidas de uma
vez e resume o resultado) ou `python analysis/bench.py 15` diretamente.
Para conferir as 4 regras de negócio, use `/check-rules` ou
`python analysis/check_rules.py`.

### 6. Ver a partida visualmente

O `env.render(mode="ipython", ...)` só funciona dentro de um notebook
Jupyter. Do terminal puro, gere o replay como HTML autossuficiente e sirva
localmente:

```powershell
python -c "from kaggle_environments import make; env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True); env.run(['src/main.py', 'random']); open('replay.html', 'w', encoding='utf-8').write(env.render(mode='html'))"
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
python src/test_smoke.py
```

## Submissão

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
kaggle competitions submit kaggriculture -f src/main.py -m "descrição da mudança"
```

Se o agente precisar de outros arquivos junto no futuro, empacote tudo em um
`.tar.gz` com `main.py` na raiz do pacote e submeta o pacote em vez do
arquivo único (hoje não é necessário — o agente é um único arquivo, de
propósito).

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
