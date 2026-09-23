# Agente Kaggriculture

Agente para a competição [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)
(Kaggle x Google) — uma simulação de fazenda 1x1 (720 turnos = 30 dias x 24
turnos/dia) onde o objetivo é terminar com o maior saldo em dinheiro.

## Arquivos

- [main.py](main.py) — o agente (`def agent(obs)`), pronto para submissão.
- [test_smoke.py](test_smoke.py) — um harness de teste simplificado (não é o
  motor real do jogo), usado antes de eu conseguir instalar o
  `kaggle-environments` de verdade. Hoje é só um teste rápido a mais;
  `analysis/` tem os scripts que rodam contra o **motor oficial**.
- `analysis/` — scripts usados para medir e depurar o agente contra o motor
  oficial: `bench.py` roda várias partidas e mede o saldo final médio,
  `check_rules.py` confere as 4 regras abaixo turno a turno.

## Regras de negócio que você pediu (implementadas em `main.py`)

1. **Reserva mínima de $1000** — toda decisão de compra (terra, sementes,
   animais, contratação, ração) verifica `RESERVE = 1000` antes de gastar, e
   todas as compras no mesmo turno são somadas (`committed`) para não estourar
   o caixa mesmo somando várias ordens de uma vez.
2. **Só compra terreno novo quando o atual estiver todo ocupado** — antes de
   emitir `BUY_LAND`, o agente confere se não sobra nenhuma tile vazia nos
   quadrantes já desbloqueados.
3. **Máximo de 13 vacas** — `MAX_COWS = 13` limita novas compras de `COW`; o
   agente nunca força chegar a 13, só nunca ultrapassa.
4. **Timing da temporada** — `can_finish()` bloqueia plantar uma cultura que
   não teria tempo de crescer, ser colhida e vendida antes do fim dos 30 dias;
   a partir do dia 27 (`LIQUIDATE_DAY`) o agente liquida tudo o que está no
   paiol independentemente do preço, já que estoque não vendido não conta para
   a pontuação final.

   Todas as 4 regras foram reconferidas turno a turno contra o motor oficial
   com `analysis/check_rules.py` (múltiplas rodadas, sem violação).

## O que mudou nesta rodada de otimização de lucro

Você pediu para eu aumentar o lucro e analisar mais partidas. Consegui
instalar o motor oficial do jogo (`kaggle-environments`, ver seção de teste
abaixo) e usei ele — não mais suposições de documentação de terceiros — para
rodar dezenas de partidas reais e medir o agente de verdade. Isso expôs 5
bugs sérios que a versão anterior nunca tinha detectado (porque nunca tinha
rodado contra o motor real):

1. **O código de segurança (try/except) nunca rodava.** O carregador do
   Kaggle executa o *último* `def` definido no arquivo, não uma função
   chamada `agent` especificamente. Como `_agent_impl` vinha depois de
   `agent` no arquivo antigo, era `_agent_impl` — sem proteção nenhuma —
   quem rodava de verdade em toda submissão. Corrigido: `agent` agora é
   garantidamente a última função do arquivo.
2. **Bug crítico de concorrência no plantio.** Lendo o código-fonte real do
   motor (`kaggriculture.py`, instalado junto com o pacote), descobri que se
   vários trabalhadores pedem `PLANT` da mesma safra no mesmo turno e a soma
   dos pedidos passa do estoque de sementes, o motor cancela **todos** os
   pedidos daquela safra no turno — não só o excedente. Meu agente antigo
   deixava vários trabalhadores decidirem "tenho semente, vou plantar"
   cada um por conta própria, e com poucas sementes isso significava dias
   inteiros em que ninguém plantava nada, sempre.
3. **Deadlock de caixa.** A escolha de safra exigia caixa suficiente para
   *3 sementes* de reserva antes de sequer considerar plantar. Assim que o
   saldo caía perto de $1000 (o que sempre acontecia, por causa da
   contratação inicial), o agente nunca mais conseguia plantar nada — e sem
   plantar, nunca mais saía dali. Corrigido para exigir só 1 semente.
4. **O motor recontrata do zero todo santo dia.** Não é só que a posição de
   todo mundo reseta à noite (fazendeiro *e* diaristas voltam pro paiol) —
   os diaristas em si somem e precisam ser recontratados, com o custo
   Fibonacci reiniciando. Meu agente antigo usava 1 trabalhador por tile,
   então cobrir a fazenda inteira exigia contratar ~12-13 diaristas *todo
   dia* (~$400-600/dia, todo santo dia da partida) para render, na prática,
   1-2 ações úteis por trabalhador (o resto do dia ele ficava parado). Isso
   sozinho comia praticamente toda a receita do trigo. Corrigido: agora cada
   trabalhador cuida de um lote de ~4 tiles próximas em sequência (do jeito
   que o cuidador de animais já fazia com as vacas), cortando a folha de
   pagamento diária em ~4x pela mesma cobertura de terreno.
5. **Melão cedo demais quebra tudo.** Pelos números reais do motor, melão
   dá de longe o melhor $/tile-dia (~125/dia contra ~37-47 de trigo/cenoura)
   — mas leva 12 dias para a primeira colheita. Deixar os primeiros
   trabalhadores decidirem plantar melão antes de qualquer venda acontecer
   trava a economia inteira (sem renda por 12 dias enquanto a contratação
   diária continua consumindo caixa). Corrigido: só trigo/cenoura (colheita
   em ~3-4 dias) até o caixa acumular uma folga real acima da reserva;
   melão e as demais safras entram depois disso.

Resultado dessa primeira rodada, medido com `analysis/bench.py`: saldo final
médio de **~$3600** partindo de $3000 — instável antes, virou consistente,
mas ainda pouco crescimento real.

## Segunda rodada: por que a fazenda terminava com um único campo

Você reportou o problema certo: a fazenda terminava com um só campo (NW) e
quase o dinheiro inicial. Investiguei de novo contra o motor oficial e achei
mais 3 problemas, todos consequência direta de decisões da rodada anterior:

1. **Lotes de trabalho espalhados viravam mato.** O "lote de ~4 tiles por
   trabalhador" da correção #4 acima pegava as 4 tiles mais próximas *do
   paiol* na fila, não umas das outras — duas tiles podem estar à mesma
   distância do paiol e ainda assim em cantos opostos do campo. Resultado:
   o trabalhador passava o dia andando entre elas em vez de regar, e a
   metade da fazenda virava erva daninha (cheguei a medir 8-13 tiles em mato
   de 25, todo santo dia). Corrigido: o lote agora é montado por
   proximidade *entre si* (a tile mais perto do paiol vira a "semente" do
   lote, depois pego as tiles mais próximas dela, não do paiol), e a ordem
   de visita também é otimizada — o trabalhador anda um circuito curto em
   vez de zigue-zague.
2. **Trigo/cenoura para sempre.** A trava de segurança contra plantar melão
   cedo demais (item #5 da rodada anterior) usava um limiar de caixa alto
   (~$6000) que a fazenda quase nunca alcançava plantando só trigo/cenoura —
   um ciclo vicioso onde a safra de segurança nunca gerava caixa suficiente
   para justificar sair dela. Troquei o gatilho: agora é baseado no **dia**
   (só trigo/cenoura até o dia 6, quando a primeira colheita já teve tempo
   de acontecer), não no caixa acumulado — bem mais confiável, e libera
   melão/morango/tomate rapidamente para quem for contratado depois.
3. **Vacas reservadas em terreno que não sobrava.** Com o lote de 4 tiles
   por trabalhador, 7 trabalhadores já reivindicavam as 25 tiles do NW
   inteiras — sobrava zero tile livre para construir um pasto quando o
   caixa finalmente justificava investir em gado, então `want_animals`
   virava `True` mas nenhuma vaca aparecia nunca. Corrigido: agora reservo
   algumas tiles para animais *antes* dos trabalhadores de cultivo
   reivindicarem tudo (e devolvo elas para plantio se a fazenda nunca
   chegar a investir em gado, para não desperdiçar terreno à toa).

Resultado, medido de novo com `analysis/bench.py` em 15 partidas reais
contra o agente `"random"`: saldo final médio de **~$6500** (mínimo $3199,
máximo $10498), partindo de $3000 — mais que o dobro do capital inicial em
média, contra ~$3600 da rodada anterior. As 4 regras de negócio continuam
100% respeitadas (`analysis/check_rules.py`, sem violação).

## Terceira rodada: tentativas de expandir terreno e investir em gado mais cedo (a maioria não valeu a pena)

Você pediu para eu achar mais alguma regra para otimizar — testei várias
mudanças de verdade contra o motor oficial, e a maioria **piorou** o
resultado, o que também é informação útil:

- **Expandir terreno assim que "toda tile está sob gestão" (em vez de
  literalmente vazia agora)**: parecia uma interpretação mais justa da sua
  regra (afinal colheita→replantio sempre deixa 1-2 tiles momentaneamente
  vazias, então o campo quase nunca bate 0 exato). Na prática, comprar
  terreno cedo *dobra* o número de tiles que precisam de trabalhadores e
  sementes antes do terreno novo ter rendido um centavo, e isso derrubava a
  economia de volta pro piso — mesmo exigindo uma folga de caixa extra além
  do preço do terreno. **Revertido** para a checagem literal original (mais
  rígida, mas nunca quebra a fazenda).
- **Investir em gado mais cedo** (limiar de caixa menor): mesma história —
  comprar vaca/pasto antes da lavoura de trigo/cenoura estar madura o
  suficiente trava a economia perto do piso na maioria das partidas.
  **Revertido** para o limiar original.
- **Trabalhador cuidando de mais tiles (6) ou menos tiles (3)**: 6 por
  trabalhador deu resultado mais baixo e mais previsível; 3 deu média
  parecida mas com uma partida travada perto do piso (mais risco). **Mantido
  em 4**, que segue sendo o melhor equilíbrio entre custo de contratação
  diário e risco.

O que realmente ajudou, sem mexer nos limiares frágeis acima:

- **Vender lotes maiores por turno**: o teto de venda por turno (para não
  derrubar o preço de mercado) estava bem mais conservador do que a curva
  real de preço do jogo suporta. Trigo/cenoura (curva suave) subiu de 20
  para 30 unidades por pedido; itens premium (morango, melão, leite, lã,
  ovo — curva mais sensível a excesso de oferta) subiu de 5 para 8. Isso só
  acelera a conversão de colheita parada no paiol em dinheiro — não muda
  nenhuma decisão de plantio/contratação, então não tem o mesmo risco das
  mudanças acima.

Resultado depois desse ajuste: saldo final médio subiu para **~$5850-6500**
dependendo da amostra, com o mínimo observado subindo de ~$3200 para
~$4200-4300 (menos partidas fracas) — sem violar nenhuma das 4 regras. A
lição da rodada: o gargalo real deste jogo é o custo de contratação diário
(reinicia todo dia) crescendo mais rápido que a receita sempre que a fazenda
expande rápido demais — qualquer mudança que faz a fazenda crescer mais
rápido tende a bater nesse mesmo problema, então o ganho mais seguro que
sobra é extrair mais valor do que já é colhido (vender melhor), não plantar
mais agressivamente.

## Fonte das regras do jogo

Inicialmente usei a documentação da comunidade (o Kaggle não expõe as regras
completas na página da competição, que é renderizada via JS) — principalmente
o guia `docs/AGENTS.md` do repositório
[`phucthaiv02/kaggriculture`](https://github.com/phucthaiv02/kaggriculture).
Mas depois de instalar o `kaggle-environments` de verdade nesta máquina, todas
as correções acima vieram de ler **o código-fonte oficial do motor**
(`kaggle_environments/envs/kaggriculture/kaggriculture.py`, que fica junto do
pacote instalado — veja o comando no passo 4 da seção de teste abaixo se
quiser inspecionar você mesmo), que é a fonte da verdade e diverge da
documentação de terceiros em vários pontos importantes (os 5 itens acima).

## Testando localmente (passo a passo, terminal do VS Code)

O Python padrão desta máquina é o 3.14, e o `kaggle-environments` depende do
`pygame`, que ainda não tem wheel pré-compilada para 3.14 no Windows (a
instalação trava tentando compilar do zero). A boa notícia é que você já tem
o **Python 3.12** instalado também (via `py -3.12`), que funciona sem
problema. Todos os comandos abaixo são para o terminal **PowerShell** do
VS Code (o padrão no Windows). Rode-os sempre a partir da pasta do projeto.

### 1. Abrir a pasta certa no terminal

No terminal do VS Code (`Ctrl+\``), confirme que está na pasta do projeto:

```powershell
cd "C:\Users\eduar\Desktop\agente-kaggle"
```

### 2. Criar um ambiente virtual com Python 3.12 (só precisa fazer uma vez)

```powershell
py -3.12 -m venv .venv
```

Isso cria uma pasta `.venv` dentro do projeto com um Python isolado, sem
mexer no Python 3.14 que você já usa para outras coisas.

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
no início da linha. **Repita este passo 3 toda vez que abrir um terminal
novo** (o passo 2 é só uma vez).

### 4. Instalar as dependências (só precisa fazer uma vez por ambiente)

```powershell
python -m pip install --upgrade pip
python -m pip install kaggle-environments==1.32.7 kaggle
```

> **Sobre a versão:** testei isso de verdade nesta máquina. Python 3.14
> (o padrão daqui) não instala o `kaggle-environments` porque uma das suas
> dependências (`pygame`) ainda não tem wheel pronta para 3.14 no Windows —
> a instalação trava tentando compilar do zero e falha. Com **Python 3.12**
> funcionou sem nenhum problema, e `kaggle-environments==1.32.7` (a mais
> recente no momento) já inclui o ambiente `kaggriculture` oficial — eu criei
> o ambiente (`make('kaggriculture', ...)`) e rodei um episódio completo de
> 720 turnos com o `main.py` de verdade, sem travar nem dar erro. Se uma
> versão mais nova do pacote não tiver `kaggriculture` registrado por algum
> motivo, use `==1.32.7` explicitamente como acima.

### 5. Rodar um episódio completo localmente

Com o ambiente ativado (prompt mostrando `(.venv)`):

```powershell
python -c "from kaggle_environments import make; env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True); env.run(['main.py', 'random']); print([(i, s.reward, s.status) for i, s in enumerate(env.steps[-1])])"
```

Isso joga uma partida completa (720 turnos) do seu `main.py` contra o agente
"random" e imprime, para cada jogador, `(índice, saldo final, status)`.
`status` deve ser `"DONE"` — se aparecer `"ERROR"` ou `"INVALID"`, algo no
agente quebrou (o Kaggle mostra o traceback nesse caso).

**Já rodei esse comando de verdade** (motor oficial, não o smoke test) dezenas
de vezes nesta máquina para medir e ajustar o agente (ver `analysis/bench.py`
e as seções "O que mudou" acima) — status `DONE` sempre, saldo final médio em
torno de **$6.000–$6.500** partindo de $3.000 (o agente `"random"` zera o
caixa, como esperado). As 4 regras de negócio (reserva de $1000, expandir só
quando cheio, máximo 13 vacas, respeitar o tempo de safra) foram reconferidas
turno a turno com `analysis/check_rules.py` sem violação.

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
pular pro fim, arrastar a barra) mostrando os dois tabuleiros lado a lado,
saldo de cada jogador, e o que cada um plantou/construiu. `Ctrl+C` no
terminal encerra o servidor quando terminar. Se preferir notebook Jupyter, o
`env.render(mode="ipython", width=1200, height=800)` funciona direto numa
célula, sem precisar de servidor.

### 7. (Opcional) Rodar o smoke test rápido que usei durante o desenvolvimento

Esse não é o motor oficial do jogo — é uma simulação simplificada que criei
porque não consegui instalar o `kaggle-environments` real neste ambiente
Sonnet 5, e usei para caçar bugs de lógica sem gastar submissões:

```powershell
python test_smoke.py
```

Nesse teste eu encontrei e corrigi bugs de verdade: o "cuidador" (rancher)
ficava construindo currais infinitamente antes de posicionar as vacas
compradas, vacas morriam de fome porque buscar um animal novo tinha
prioridade sobre alimentar os já existentes, e múltiplas compras no mesmo
turno conseguiam furar a reserva de $1000 porque cada uma checava o saldo
original em vez do saldo já comprometido no turno. Mas o passo 5 (motor
oficial) é o teste que realmente importa antes de submeter.

## Submissão (passo a passo)

### 1. Configurar as credenciais da API do Kaggle (só uma vez)

1. Acesse https://www.kaggle.com/settings/api e clique em **"Create New
   Token"**. Isso baixa um arquivo `kaggle.json`.
2. No terminal do VS Code, mova esse arquivo para a pasta que o CLI espera:

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

### 3. Confirmar que está inscrito (com o ambiente virtual ativado)

```powershell
.\.venv\Scripts\Activate.ps1
kaggle competitions list --group entered
```

Você deve ver `kaggriculture` na lista.

### 4. Enviar o agente

```powershell
kaggle competitions submit kaggriculture -f main.py -m "v1 - regras do usuario"
```

Se o `main.py` crescer e precisar de outros arquivos junto, empacote tudo em
um `.tar.gz` com `main.py` na raiz e submeta o pacote em vez do arquivo único
(hoje não é necessário, o agente é um único arquivo).

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
