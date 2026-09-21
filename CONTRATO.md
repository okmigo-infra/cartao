# O contrato do cartão declarado

O crivo **reconstrói** o cartão no vocabulário do produto e **descarta o que não
entende sem dizer nada**. Não existe campo de cor, de fonte nem de pixel: o
serviço declara INTENÇÃO e quem escolhe a aparência é o cliente. Teto: **2000
nós** por cartão.

Este documento é a fonte de verdade do vocabulário. A implementação é
[`src/okmigo_cartao/crivo.py`](src/okmigo_cartao/crivo.py); divergência entre os
dois é bug de um deles.

## 1 · As três regras que fecham o desenho

1. **O que não é construído não existe.** O crivo nunca repassa a árvore que
   recebeu — monta outra, nó a nó. Um nó que não sobrevive some — ou cai no
   `fallback` do próprio schema. Só o **estrutural** recusa a tela inteira:
   cartão sem corpo, mais de 2000 nós, operação que o serviço não declarou.

   ⭐ **E o `fallback` vale para QUALQUER queda, não só para tipo desconhecido**
   (11/09). A queda mais comum aqui não é «não conheço esse tipo» — é **«o
   elemento veio vazio»**: a tabela que ficou só com o cabeçalho porque a lista
   não repetiu nada, a escolha sem opção válida, o `ActionSet` que perdeu todos
   os botões. Antes disso, um negócio sem movimento no dia abria a tela sem a
   tabela **e sem a frase que o autor tinha escrito para o vazio**.

   ⚠️ O `fallback` **não é atalho para dentro**: ele volta pelo mesmo crivo, e
   um proibido cai igual (com o `fallback` dele, se tiver). ⚠️ E ele não
   aparece quando o elemento sobrevive — senão a tela teria a tabela e o aviso
   de «nada aqui» ao mesmo tempo.
2. **Quem desenha é o produto.** Tamanho é palavra (`large`), não número;
   estilo é hierarquia (`emphasis`, `accent`) ou estado (`good`, `attention`,
   `warning`); altura é faixa; cor de gráfico é significado (`positivo`,
   `negativo`). `TextBlock.color` é lido e descartado.
3. **Ação nomeia capacidade, nunca endereço.** `Action.Submit` e
   `Action.Execute` carregam o nome de uma OPERAÇÃO do contrato que o serviço
   declarou ao instalar; o cliente
   transforma isso em chamada a uma rota do produto. `Action.OpenUrl` evapora.
   A única saída para um endereço de terceiro é `okmigoAutorizar`.

## 2 · O vocabulário

| nó | o essencial | armadilhas |
|---|---|---|
| `TextBlock` | `size`/`weight`/`isSubtle`/`wrap`/`horizontalAlignment` — palavras, não números | `color` evapora: a seta de variação vai no TEXTO (`↗ 5%`); texto vazio some |
| `Container` | `style` (`emphasis` painel · `accent` a caixa preenchida com o acento, a «porta recomendada» · `good`/`attention`/`warning` o TOM do que ela carrega) · `minHeight` em faixa · `id`/`isVisible` · `selectAction` (`Action.ToggleVisibility` local ou `Action.Execute` de leitura; ⛔ nunca escrita) · `okmigoSobreposto: true` (sai do fluxo, aparece por cima) · `okmigoGrade` | `okmigoGrade: true` = grade comum (números curtos); `"larga"` = cada filho é um cartão inteiro, no máximo DOIS por linha; `"compacta"` = filhos pequenos, o máximo que couber (a única que dá duas colunas num telefone); `"etiquetas"` = palavras curtas correndo em linha, cada uma do tamanho do texto. Cliente que não conhece a palavra desenha grade comum ou empilha — nenhum quebra. Caixa que perdeu um campo OBRIGATÓRIO perde os botões. ⭐ **Telas que se sucedem** = caixas com `id` e `ToggleVisibility` COM SINAL (mostra uma, esconde a outra); não é navegação, é o que o contrato já tinha |
| `ColumnSet` | colunas `auto`/`stretch`, cada uma com `style`, `minHeight` e itens | número vira `stretch`; `auto` é só para tamanho CONHECIDO (logo, dinheiro formatado) — texto imprevisível estoura o telefone |
| `Table` | `columns[{width: N}]` em **proporção numérica** · `firstRowAsHeader` (⛔ singular) · `showGridLines` · `TableRow`/`TableCell`, e a célula é uma caixa · `TableRow.selectAction` aceita só `Action.Execute` de leitura, tornando a linha consultável | `"auto"`/`"stretch"` viram 1; teto 16 colunas × 200 linhas; **cabeçalho sem linha de dado descarta a tabela INTEIRA**; num telefone o cliente pode virar fichas; a ação da linha recebe somente os campos daquela linha e operação fora do contrato recusa a tela |
| `FactSet` | `facts[{title, value}]` | fato sem título some; sem fatos, o bloco some |
| `Image` | ⛔ só de domínio do produto (`/img/…` vira absoluta; https, sem credencial, porta 443) · `height` em palavra · `altText` | URL de terceiro é recusada (o aparelho de quem abre bateria no servidor dele); sem URL válida vira MARCADOR (`sem_imagem`), não buraco — ou o `fallback` declarado; `size`/`style` somem |
| `Input.Text` · `Input.Number` | `id` (⛔ obrigatório: é a chave de ESTADO no cliente, única no cartão) · `campo` (o nome que viaja ao serviço; pode repetir entre caixas) · `label`, `placeholder`, `value` (pré-preenche: é o formulário de correção), `isRequired`, `isMultiline`, `maxLength` (só aperta), `min`/`max` · `okmigoSomenteLeitura` | ⛔ número em `Input.Text`: «62.900» chega como 62,9 do outro lado, sem erro — use `Input.Number`; campo em branco NÃO é enviado |
| `Input.ChoiceSet` | `choices[{title, value}]` (⛔ os dois obrigatórios: `value` viaja, `title` se lê) · `isMultiSelect` para múltipla escolha · `okmigoControle: "alternancia"` para booleano · `okmigoAoAlterar` para visibilidade local explícita · `okmigoNota` (linha de apoio) e `okmigoIcone` (um glifo, ≤ 12 caracteres) por opção · três formas: sem `style` = lista suspensa; `style: "expanded"` = **fichas tocáveis**; `style: "filtered"` = typeahead LIVRE; com `okmigoEstrito: true` = busca estrita · `okmigoBuscar: "operacao"` pede sugestões remotas declaradas | corta em 60 opções; múltiplos valores continuam limitados às opções; alteração condicional só aceita alvos com booleano explícito e não alcança rede; lista estrita vazia derruba o campo e os botões da caixa |
| `ActionSet` | `Action.ToggleVisibility` · `Action.Submit` para escrita · `Action.Execute` para leitura (⛔ operação fora do contrato recusa a tela INTEIRA) · ênfase semântica · `okmigoIcone: "delete"` · `okmigoConfirmacao` com título, mensagem e rótulos · `okmigoRodape` · `okmigoAposEnviar` · `okmigoMenu` para menu contextual · `okmigoSegmentado` para abas/filtros · `okmigoExpansivel` para acordeão | `OpenUrl` evapora; menu é limitado a 10 itens; cada operação ganha os campos da própria caixa; confirmação não contém código nem endereço; dicas de apresentação não ampliam a fronteira |
| `okmigoGrafico` | `forma: barras\|linha` · `series[{rotulo, cor}]` com cor SEMÂNTICA (`positivo/negativo/neutro/atencao/principal/suave`) · `pontos[{rotulo, valores[]}]` · teto 4 séries × 24 pontos | valores casam com séries por ÍNDICE; ponto faltando é buraco honesto, nunca série deslocada; aceita `1234.5` e `"1.234,50"`; NaN/infinito somem; gráfico sem ponto some; ⛔ não existe pizza (posição e comprimento se julgam melhor que ângulo e área) |
| `okmigoCalendario` | `vista: mes\|semana\|dia` · `de` · `eventos[{inicio, fim, titulo, detalhe, id, tipo}]` (teto 500; vale 1 nó) · `aoTocarODia {mostrar, preencher}` · `acoesDoEvento[{para, titulo, gesto, enviar+campos \| mostrar+preencher}]` (teto 6) | o serviço nomeia o CAMPO, nunca o VALOR (`preencher: {"dia": "data"}`); evento sem `id` desenha mas não aceita ação; `nova_*` só existem no gesto `arrastar`; um toque abre formulário, nunca escreve |
| `okmigoArquivo` | `id`, `campo`, `label`, `aceita` (`pdf/imagem/xml/planilha/texto`), `maxBytes` (só aperta o teto do produto), `isRequired` | palavra desconhecida em `aceita` some; sem nenhuma, aceita tudo |
| `okmigoDocumento` | `titulo`/`nome`, `tipo` (MIME), `tamanho`, `ler: {operacao, pedido}` — a operação tem de ser LEITURA declarada (⛔ fora dela recusa a tela) | `formato` sai derivado do MIME (`pdf`, `imagem` só raster, `outro`); `pedido` só com escalares |
| `okmigoCopiar` | `{rotulo, valor}` → área de transferência | sem valor, some |
| `okmigoAutorizar` | ⛔ a ÚNICA saída para endereço de terceiro: `url` (https, sem credencial embutida, sem porta/IP, **nunca domínio do produto**, ≤ 2048), `rotulo`, `motivo` (obrigatório: é o que a pessoa lê antes de sair) | UM por cartão; o segundo some; o host volta separado (`onde`) e o cliente é obrigado a escrevê-lo; endereço acima do teto é recusado, nunca cortado; a URL vem do DADO (o token vence), nunca do molde |
| `okmigoCronometro` | `{rotulo, segundos}` — contagem REGRESSIVA de um valor declarado; 1 s … 3600 s | ⛔ não começa sozinho; sem hora do servidor; fora da faixa ou sem rótulo, some |
| `okmigoProgresso` | `{feito, de, rotulo?, tom?}`; `de` de 1 a 10 000 | recebe os DOIS números, **nunca uma porcentagem**; `de` inválido some; `feito` fora da faixa é PRENSADO; é tipo NOVO — declare o «4 de 6» num `TextBlock` ao lado para o cliente velho não perder a informação |
| `okmigoEtiqueta` | `{texto, tom, status?}`; tons fechados `neutro`, `positivo`, `atencao`, `negativo`, `informativo` | status usa também símbolo/texto; cor nunca é a única pista; sem texto cai no fallback |
| `okmigoGaleria` | `{rotulo, imagens[]}` com até 12 `Image` | cada imagem passa pelas mesmas regras de domínio e HTTPS; rolagem e tamanho são do renderer |
| `okmigoLinhaDoTempo` | `{rotulo, etapas[{titulo, detalhe?, estado}]}`; até 24 etapas | estados fechados `concluida`, `atual`, `futura`, `erro`; sem etapa válida cai no fallback |
| `okmigoBarraDeValor` | `{rotulo, valor, de, texto?, tom?}`; `de` de 1 a 10 000 | comparação acessível com número sempre visível; valor é prensado entre zero e total |
| `okmigoMinigrafico` | `{valores[], alternativa, rotulo?, tom?}`; 2 a 48 números | a TENDÊNCIA sem eixo, sem legenda e sem rótulo de ponto. ⛔ `alternativa` é OBRIGATÓRIA e não tem padrão: é o único componente cujo conteúdo não dá para derivar em texto, e sem ela o dado existe só para quem enxerga. Aceita `1234.5` e `"1.234,50"`; menos de dois números válidos e o bloco some |
| `okmigoRanking` | `{titulo, criterio, itens[{rotulo, valor, apoio?, variacao?, tom?, id?, tendencia?, aoTocar?}], base?, universo?, nota?, verTodos?}`; teto 50 itens | ⛔ sem `criterio` o bloco CAI inteiro — lista ordenada que não diz por que está nessa ordem é recomendação disfarçada de tabela. A **posição é do crivo**, na ordem recebida: item que traz o próprio número consegue mentir sobre a ordem. `aoTocar` e `verTodos` são `Action.Execute` e só; item sem rótulo E valor some sem furar a numeração |
| `okmigoCabecalhoDeDetalhe` | `{titulo, valor?, subtitulo?, variacao?, tom?, base?, etiquetas[]?, destacar?, destacado?, menu?}` | o topo de uma ficha. `destacar` (favoritar) é a única ESCRITA de um componente de leitura e passa pela mesma conferência de `escrituras` de qualquer botão — operação não declarada recusa a tela inteira. Teto de 4 etiquetas |
| `okmigoEstadoDoDado` | `{situacao, titulo, explicacao?, base?, acao?}`; `situacao` em `carregando/vazio/parcial/desatualizado/erro/offline/sem_permissao/nao_aplicavel` | ⛔ `vazio` e `desatualizado` NÃO são o mesmo estado: o primeiro diz que não há nada, o segundo que o coletor parou — e o gesto que cada um pede é outro. Situação desconhecida vira `parcial`, nunca `erro`: inventar gravidade que o serviço não declarou assusta quem lê |
| `okmigoComparador` | `{titulo, itens[{rotulo, apoio?, id?}], criterios[{rotulo, valores[], explicacao?, melhor?}], base?, nota?}`; 2 a 4 itens × 24 critérios | `valores` casa com `itens` por ÍNDICE e é PRENSADO no tamanho deles — valor faltando vira `""` e o cliente desenha «—»; encurtar deslocaria a coluna. `melhor` marca o extremo de UM critério (e é descartado se apontar para valor vazio); ⛔ não existe nota final: somar critérios de naturezas diferentes num score é produzir recomendação |
| `okmigoAgenda` | `{titulo, itens[{data, titulo, apoio?, valor?, estado?, id?, aoTocar?}], base?, vazio?, agruparPorData?}`; teto 120 itens; `estado` em `confirmado/anunciado/previsto/realizado/sem_data/cancelado` | a LISTA do que vem por data — o irmão do `okmigoCalendario`, que é a grade do mês. ⭐ agenda VAZIA **sobrevive** (ao contrário da tabela só com cabeçalho): «nenhum provento anunciado» é a resposta, não a falta dela. Item sem `data` vira `sem_data` em vez de sumir; `previsto` nunca se desenha como `confirmado` |
| `okmigoCartaoBancario` · `okmigoDistribuicao` · `okmigoListaFinanceira` | blocos do tema financeiro (`okmigoTema: "financeiro-violeta"`, `okmigoNavegacao: "inferior"` no topo do cartão); `tom` em lista fechada | itens sem título/valor somem; sem itens, o bloco some; `semantica` fora de `positivo/negativo/neutro` cai em `neutro` |

Chaves de TOPO: `type: "AdaptiveCard"`, `version`, `body`, `okmigoTema`,
`okmigoNavegacao`. Qualquer outra é ignorada.

`okmigoTema` declara a **natureza da experiência**, nunca uma paleta ou CSS.
A lista fechada é `financeiro-violeta` (finanças pessoais), `jornada-ativa`
(processos guiados em etapas), `mercado-editorial` (leitura e comparação de
dados) e `operacao-direta` (fila e ação rápida). O cliente escolhe cores,
tipografia, densidade, raios e espaçamento; um tema desconhecido é ignorado e
o cartão continua legível com a identidade padrão do produto.

## 3 · Escrita: o que um toque pode e não pode

- **Formulário não é lista.** Quem preencheu e apertou Salvar já confirmou: o
  `Action.Submit` grava. `Action.Execute` consulta e substitui o cartão pela
  resposta reconstruída. Um toque numa `TableRow` pode executar essa leitura;
  em outras caixas, só alterna visibilidade — quem escreve é o botão do
  formulário revelado.
- **O `Submit` manda os campos da própria caixa** (`campos`, escopado pelos
  `id`). Dois formulários independentes convivem na mesma tela; um por dia
  num calendário é o caso que fez a regra existir.
- **Depois de gravar, o cliente busca o cartão de novo** — o que o serviço
  devolve é a verdade, não o que a pessoa digitou — e **preserva o que estava
  aberto** (os `id` que existem nos dois cartões), senão gravar numa aba
  devolveria a pessoa à primeira. Os CAMPOS são re-semeados.
- **`okmigoAposEnviar`** é a transição depois de gravar: mostra a próxima
  etapa, esconde a anterior, e leva a pessoa ao alto. Só com estados
  booleanos explícitos.
- **Recusa do serviço é falha visível**: a frase dele aparece junto do
  formulário («placa duplicada» é acionável; «erro ao salvar» não).

## 4 · O crivo come em silêncio — e como se valida de verdade

O modo de falha desta plataforma quase nunca é erro: é a tela sair sem o
pedaço, com tudo em 200. As regras que salvam:

1. **Validar o molde cru não prova nada.** `_repetir_lista` só existe depois
   de expandido com dados; o crivo pula o nó de repetição, e a regra dele
   descarta a tabela que ficou só com cabeçalho. **Expanda com 2+ linhas
   concretas antes de validar** (`--dados`), e a asserção procura o NÓ
   (`tipo == "tabela"`), não o «aceito».
2. **Cartão sintético não prova cartão real.** Só o cartão com os nomes exatos
   que o serviço espera pega colisão de `campo`/`id`.
3. **Qualquer coisa com tela: abra a tela — nos DOIS clientes.** O crivo
   aceitar não quer dizer que os dois desenham.
4. **Tipo novo no vocabulário:** pergunte antes «o que o cliente que não
   conhece isto vai desenhar?». Se a resposta é «nada», não está pronto.
   Cliente velho é a REGRA num app de loja; o desconhecido se anuncia, nunca
   cai num catch-all mudo.
5. **As três degradações:** campo desconhecido **some**; capacidade
   desconhecida no **servidor recusa a superfície inteira** (botão que não faz
   nada faz a pessoa culpar o produto); no **cliente, não faz nada**.

## 5 · O molde e a expansão

Um cartão registrado é um **molde**: texto com `{campo}` e nós de repetição.
A expansão (`expandir()` aqui; a ponte, no produto) tem quatro regras e só
quatro — sem condicional, sem laço, sem expressão:

- `{campo}` em texto vira o valor (`{a.b}` desce um nível). Campo ausente vira
  vazio; espaços e os separadores `·`, `—`, `|` que só ligavam pedaços colapsam.
- Todo número substituído sai **formatado para leitura** (`62900.5` →
  `62.900,50`) — por isso o crivo aceita `"1.234,50"` como número. Um `id`
  NÃO passa por molde: numérico, viraria `1.234` e deixaria de casar.
- `{"_repetir_lista": <modelo>}` dentro de uma lista vira N cópias do modelo,
  uma por item da lista da superfície, dissolvidas na lista de cima.
- `_quando: {campo, em: [...]}` escolhe QUAIS itens; `_de: "nome"` repete
  sobre uma lista **de dentro do item da vez** (a sublista de um cartão), com
  teto de 50 — dentro de um item repetido a lista da superfície chega vazia,
  senão seria N×N.
