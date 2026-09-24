# Diário de desenvolvimento

Este arquivo registra, rodada a rodada, o que foi investigado, tentado,
medido e revertido ou mantido durante o desenvolvimento do agente. O
[README](../README.md) traz só o resumo; aqui vai o detalhe completo, na
ordem em que aconteceu — incluindo os becos sem saída, porque eles também
são parte de como o agente chegou ao estado atual.

Toda alegação de "medi X" abaixo foi de fato medida contra o **motor oficial**
do jogo (`kaggle-environments`, instalado localmente — ver
[README § Testando localmente](../README.md#testando-localmente)), usando
`analysis/bench.py` (várias partidas reais, saldo final médio/mínimo/máximo)
e `analysis/check_rules.py` (confere as 4 regras de negócio turno a turno).

## Rodada 1 — dos primeiros bugs até um agente estável

O agente original nunca tinha rodado contra o motor de verdade (só contra um
harness simplificado feito à mão, porque o `kaggle-environments` não instalava
neste ambiente inicialmente). Depois de conseguir instalar o motor oficial
(ver a nota sobre Python 3.12 vs 3.14 no README), rodar partidas reais expôs
5 bugs sérios:

1. **O código de segurança (try/except) nunca rodava.** O carregador do
   Kaggle executa o *último* `def` definido no arquivo, não uma função
   chamada `agent` especificamente. Como `_agent_impl` vinha depois de
   `agent` no arquivo antigo, era `_agent_impl` — sem proteção nenhuma —
   quem rodava de verdade em toda submissão. Corrigido: `agent` agora é
   garantidamente a última função do arquivo (ver o comentário na própria
   função em `main.py`).
2. **Bug crítico de concorrência no plantio.** Lendo o código-fonte real do
   motor (`kaggle_environments/envs/kaggriculture/kaggriculture.py`,
   instalado junto com o pacote), descobri que se vários trabalhadores pedem
   `PLANT` da mesma safra no mesmo turno e a soma dos pedidos passa do
   estoque de sementes, o motor cancela **todos** os pedidos daquela safra no
   turno — não só o excedente. O agente antigo deixava vários trabalhadores
   decidirem "tenho semente, vou plantar" cada um por conta própria, e com
   poucas sementes isso significava dias inteiros em que ninguém plantava
   nada, sempre. Corrigido com `_throttle_plant_race` em `main.py`.
3. **Deadlock de caixa.** A escolha de safra exigia caixa suficiente para
   *3 sementes* de reserva antes de sequer considerar plantar. Assim que o
   saldo caía perto de $1000 (o que sempre acontecia, por causa da
   contratação inicial), o agente nunca mais conseguia plantar nada — e sem
   plantar, nunca mais saía dali. Corrigido para exigir só 1 semente.
4. **O motor recontrata do zero todo santo dia.** Não é só que a posição de
   todo mundo reseta à noite (fazendeiro *e* diaristas voltam pro paiol) —
   os diaristas em si somem e precisam ser recontratados, com o custo
   Fibonacci reiniciando. O agente antigo usava 1 trabalhador por tile, então
   cobrir a fazenda inteira exigia contratar ~12-13 diaristas *todo dia*
   (~$400-600/dia, todo santo dia da partida) para render, na prática, 1-2
   ações úteis por trabalhador (o resto do dia ele ficava parado). Isso
   sozinho comia praticamente toda a receita do trigo. Corrigido: cada
   trabalhador passou a cuidar de um lote de ~4 tiles em sequência (do jeito
   que o cuidador de animais já fazia com as vacas), cortando a folha de
   pagamento diária em ~4x pela mesma cobertura de terreno.
5. **Melão cedo demais quebra tudo.** Pelos números reais do motor, melão dá
   de longe o melhor $/tile-dia (~125/dia contra ~37-47 de trigo/cenoura) —
   mas leva 12 dias para a primeira colheita. Deixar os primeiros
   trabalhadores decidirem plantar melão antes de qualquer venda acontecer
   trava a economia inteira (sem renda por 12 dias enquanto a contratação
   diária continua consumindo caixa). Corrigido: só trigo/cenoura (colheita
   em ~3-4 dias) até o caixa acumular uma folga real acima da reserva; melão
   e as demais safras entram depois disso.

**Resultado:** saldo final médio de **~$3600** partindo de $3000 — instável
antes, virou consistente, mas ainda pouco crescimento real.

## Rodada 2 — por que a fazenda terminava com um único campo

O usuário reportou o problema certo: a fazenda terminava com um só campo (NW)
e quase o dinheiro inicial. Investigando de novo contra o motor oficial,
apareceram mais 3 problemas, todos consequência direta de decisões da
rodada 1:

1. **Lotes de trabalho espalhados viravam mato.** O "lote de ~4 tiles por
   trabalhador" da correção #4 acima pegava as 4 tiles mais próximas *do
   paiol* na fila, não umas das outras — duas tiles podem estar à mesma
   distância do paiol e ainda assim em cantos opostos do campo. Resultado: o
   trabalhador passava o dia andando entre elas em vez de regar, e a metade
   da fazenda virava erva daninha (chegou a medir 8-13 tiles em mato de 25,
   todo santo dia). Corrigido: o lote agora é montado por proximidade
   *entre si* (a tile mais perto do paiol vira a "semente" do lote, depois
   pega as tiles mais próximas dela, não do paiol — ver `_pop_tile_cluster`),
   e a ordem de visita também é otimizada (`_order_by_proximity`) — o
   trabalhador anda um circuito curto em vez de zigue-zague.
2. **Trigo/cenoura para sempre.** A trava de segurança contra plantar melão
   cedo demais (item #5 da rodada 1) usava um limiar de caixa alto (~$6000)
   que a fazenda quase nunca alcançava plantando só trigo/cenoura — um ciclo
   vicioso onde a safra de segurança nunca gerava caixa suficiente para
   justificar sair dela. Trocado o gatilho para ser baseado no **dia**
   (`FAST_CASH_MIN_DAY`, trigo/cenoura até o dia 6), não no caixa acumulado —
   bem mais confiável, e libera melão/morango/tomate rapidamente para quem
   for contratado depois.
3. **Vacas reservadas em terreno que não sobrava.** Com o lote de 4 tiles por
   trabalhador, 7 trabalhadores já reivindicavam as 25 tiles do NW inteiras —
   sobrava zero tile livre para construir um pasto quando o caixa finalmente
   justificava investir em gado, então `want_animals` virava `True` mas
   nenhuma vaca aparecia nunca. Corrigido: `ANIMAL_RESERVE_PER_QUADRANT`
   reserva algumas tiles para animais *antes* dos trabalhadores de cultivo
   reivindicarem tudo (e devolve elas para plantio se a fazenda nunca chegar
   a investir em gado, para não desperdiçar terreno à toa).

**Resultado:** saldo final médio de **~$6500** (mínimo $3199, máximo
$10498) em 15 partidas reais contra o agente `"random"` — mais que o dobro do
capital inicial em média, contra ~$3600 da rodada 1.

## Rodada 3 — tentativas de vender melhor (e de expandir mais agressivo, que não valeu a pena)

O usuário pediu mais uma passada de otimização. Testando várias mudanças
contra o motor oficial, a maioria **piorou** o resultado — o que também é
informação útil:

- **Expandir terreno assim que "toda tile está sob gestão"** (em vez de
  literalmente vazia agora): parecia uma leitura mais justa da regra (afinal
  colheita→replantio sempre deixa 1-2 tiles momentaneamente vazias, então o
  campo quase nunca bate 0 exato). Na prática, comprar terreno cedo *dobra* o
  número de tiles que precisam de trabalhadores e sementes antes do terreno
  novo ter rendido um centavo, e isso derrubava a economia de volta pro piso
  — mesmo exigindo uma folga de caixa extra além do preço do terreno.
  **Revertido** para a checagem literal original.
- **Investir em gado mais cedo** (limiar de caixa menor): mesma história —
  comprar vaca/pasto antes da lavoura de trigo/cenoura estar madura o
  suficiente trava a economia perto do piso na maioria das partidas.
  **Revertido**.
- **Trabalhador cuidando de mais tiles (6) ou menos (3)**: 6 por trabalhador
  deu resultado mais baixo e mais previsível; 3 deu média parecida, mas com
  uma partida travada perto do piso (mais risco). **Mantido em 4**.

O que realmente ajudou:

- **Vender lotes maiores por turno**: o teto de venda por turno (para não
  derrubar o preço de mercado) estava bem mais conservador do que a curva
  real de preço do jogo suporta. Trigo/cenoura (curva suave) subiu de 20 para
  30 unidades por pedido; itens premium (morango, melão, leite, lã, ovo —
  curva mais sensível a excesso de oferta) subiu de 5 para 8.

**Resultado:** saldo final médio subiu para **~$5850-6500** dependendo da
amostra, com o mínimo observado subindo de ~$3200 para ~$4200-4300 (menos
partidas fracas).

**Lição da rodada:** o gargalo real deste jogo é o custo de contratação
diário (reinicia todo dia) crescendo mais rápido que a receita sempre que a
fazenda expande rápido demais — qualquer mudança que faz a fazenda crescer
mais rápido tende a bater nesse mesmo problema, então o ganho mais seguro é
extrair mais valor do que já é colhido (vender melhor), não plantar mais
agressivamente.

## Rodada 4 — tentando imitar um oponente real (e por que não deu certo)

Depois de uma derrota real na competição, o replay foi baixado e analisado
via `kaggle competitions replay` (episódio `112626139`). O oponente venceu
por 20x ($102.001 contra $4.950) com um padrão claramente mais agressivo:
terra, animais e safras premium desde o dia 0, tolerando caixa quase zero
por um bom tempo (chegou a $52-85 entre os dias 9-16) antes de explodir
exponencialmente ($5.8k no dia 17 → $100k+ no dia 29). Uma captura de tela
adicional do histórico de partidas (dois times do topo do ranking, `M&M&P&Q`
vs `Boey`) mostrou o mesmo padrão: pastos funcionando já no dia 3.

Tentativas de reproduzir isso literalmente:

- `RESERVE` reduzido de 1000 para 400, depois para 100.
- Compra de terreno liberada assim que as tiles estivessem "atribuídas" (não
  necessariamente vazias).
- Contratação e compra de sementes liberadas para ignorar `RESERVE`
  inteiramente (só não deixar o saldo ficar negativo).
- Limiar de investimento em gado reduzido de "$3000 de folga + 3 diaristas"
  para "$500 de folga + 1 diarista".
- `FAST_CASH_MIN_DAY` reduzido de 6 para 2.

**Cada uma dessas mudanças, medida contra `analysis/bench.py`, piorou o
resultado** — algumas drasticamente (a combinação completa chegou a travar
com saldo final de exatos $400, igual em 10/10 partidas, um sinal claro de
bug estrutural, não só de agressividade). A causa raiz de fundo, encontrada
nesse processo: quando o saldo converge para exatamente o valor da reserva
(qualquer que seja o valor), **nenhuma compra consegue mais acontecer**,
porque qualquer gasto, por menor que seja, deixaria o saldo abaixo do piso —
um beco sem saída matemático. Combinado com um bug real nos lotes de
trabalho (um trabalhador sem sementes ficava parado numa tile vazia esperando
comprar mais, abandonando as *outras* tiles do lote, mesmo com colheita
pronta esperando), a fazenda simplesmente congelava.

O bug dos lotes de trabalho (`_tile_action` sempre avança para a próxima
tile do lote, independente do motivo) foi **mantido** — é uma correção real,
independente do valor de `RESERVE`. Todo o resto foi **revertido** para os
valores validados na rodada 2/3 (`RESERVE = 1000`, limiares de gado e safra
originais), porque a conclusão prática é: a mecânica de trabalhadores deste
agente não é eficiente o bastante ainda para sobreviver ao nível de risco que
aquele oponente sobrevive — e violar a própria regra de reserva do usuário
(chegou a medir saldo mínimo de $708, abaixo do piso) não valia a pena pelo
ganho.

**Resultado final:** de volta a saldo final médio de **~$5000-5100** em 15
partidas reais, mínimo observado nunca abaixo de exatos $1000 (a regra da
reserva é honrada com precisão), máximo de $12.584 numa das partidas.

## Próximos passos possíveis

- Fazer o oponente-alvo funcionar de verdade exigiria repensar a mecânica de
  trabalhadores em si (não só afrouxar limiares) — por exemplo, um modelo que
  extraia mais valor por trabalhador/dia, para que o mesmo nível de risco que
  funciona para o oponente também funcione aqui.
- Usar fertilizante colhido dos animais diretamente nas plantações (hoje ele
  só é vendido) — o ganho por essa via foi estimado como pequeno pelos
  números do motor, mas nunca chegou a ser implementado/medido de verdade.
- Diversificar animais (ganso, ovelha) além de vaca — a regra do usuário só
  menciona vacas, então isso exigiria autorização explícita antes de mudar.
