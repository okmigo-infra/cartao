# A matriz do contrato

`python -m okmigo_cartao matriz` lê o manifesto **registrado** de um app (o
mesmo JSON que o `okmigo/registrar.sh` manda) e escreve a lista de tudo o que
esse manifesto obriga a provar — a matriz da §3.2 do `PADRAO-QA.md` do okmigo.
É a peça comum «gerador da matriz» da §12 de lá: cada app deixa de copiar a
sua.

⛔ **A lista do que testar sai do manifesto, não do caderno do app.** O caderno
se desatualiza; o manifesto é o que o okmigo usa. A matriz se gera a cada ciclo,
e linha sem caso que passou reprova o ciclo.

## Uso

```bash
# para ler (Markdown, uma tabela por app)
python -m okmigo_cartao matriz okmigo/manifesto.json

# para preencher: JSON, um ou mais manifestos (os apps de dois lados têm um por slug)
python -m okmigo_cartao matriz okmigo/manifesto-escritorio.json okmigo/manifesto-cliente.json \
    --formato json --saida matriz.json

# depois do ciclo: confere a matriz preenchida contra o manifesto de HOJE
python -m okmigo_cartao matriz okmigo/manifesto.json --conferir matriz.json
```

Puro: sem rede, só biblioteca padrão. O mesmo código está em
`okmigo_cartao.matriz` (`gerar`, `gerar_de_varios`, `conferir`, `contagem`).

## As linhas

Uma linha por:

| categoria | uma linha por | `id` |
|---|---|---|
| `superficie` | superfície × estado (§4.2: `vazio`, `tipico`, `cheio`, `texto_longo`, `erro`, `sem_permissao`, `carregando`) | `superficie:agenda:vazio` |
| `elemento` | **tipo** de elemento usado × superfície | `elemento:agenda:okmigoCalendario` |
| `acao` | ação distinta × superfície | `acao:agenda:enviar:cancelar_agendamento` |
| `rota` | rota de `rotas[]` | `rota:periodo_da_agenda` |
| `navegacao` | grupo da navegação agrupada | `navegacao:fitness` |
| `conversa` | operação da `conversa` | `conversa:criar_agendamento` |
| `operacao` | operação de `operacoes[]` que fica **fora** da `conversa` | `operacao:agenda_canonica_eventos` |
| `agente` | ferramenta do `agente`, mais uma para os `exemplos` e uma para o `orcamento` | `agente:ferramenta:interpretar_data`, `agente:exemplos`, `agente:orcamento` |
| `declaracao` | declaração presente (`eventos`, `avisa_antes`, … `versao`); `estados_restauraveis` e `recebe_documento`, uma por entrada | `declaracao:marca_horario`, `declaracao:estados_restauraveis:acoes` |

Colunas: `id`, `slug`, `categoria`, `alvo`, `o_que_provar` (a frase da tabela
§3.1), `web`, `android`, `ios`, `conversa`, `resultado`, `evidencia`. Num
canal, **«—»** é «não se aplica»; **vazio** é «se aplica e falta provar».
`resultado` e `evidencia` nascem vazios.

O `id` é estável: não depende da ordem das chaves, nem da ordem dos alvos de um
`ToggleVisibility`, nem de quantas vezes o mesmo gesto aparece na tela. É ele
que o `--conferir` usa para casar a matriz preenchida com o manifesto de hoje,
junto com o `slug`.

### O percurso do cartão

O cartão é percorrido **inteiro**: `body`, `items`, `columns`, `rows`, `cells`,
`actions`, `selectAction`, os `fallback`, a variante `okmigoDesktop` e os
moldes `_repetir_lista` — um elemento que só existe dentro de um molde é o que
mais some sem ninguém ver. `TableRow`, `TableCell` e `Column` vivem e morrem
com o pai e não contam como tipo, como no `relatorio()`. Tipo que o crivo não
conhece **gera linha mesmo assim**: é ali que o ciclo descobre que ele some.

As ações, pelo gesto:

| gesto | de onde sai |
|---|---|
| `enviar:<op>` | `Action.Submit` com `data.operacao` |
| `consultar:<op>` | `Action.Execute` com `data.operacao`; `okmigoDocumento.ler` |
| `navegar:<rota>` | `Action.Execute` com `data.okmigoNavegar`; `aoNavegarPeriodo` do calendário |
| `alternar:<alvos>` | `Action.ToggleVisibility` (`+id` mostra, `-id` esconde) |
| `autocompletar:<op>` | `okmigoBuscar` de uma escolha filtrada |
| `sobreposto:<id>` | caixa com `okmigoSobreposto: true` (o formulário sobreposto) |
| `tocar_o_dia:<id>` | `aoTocarODia` do calendário |
| `evento:<para>:enviar\|arrastar\|mostrar:<alvo>` | `acoesDoEvento` do calendário |
| `showcard:<título>`, `openurl:<título>` … | as ações que o crivo recusa: a linha existe para provar que a tela NÃO as oferece |

A transição `okmigoAposEnviar` faz parte do botão que grava e não ganha linha
própria. Ação sem alvo (um `Submit` sem `operacao`) o crivo descarta, e também
não ganha linha.

### Os canais

Os da coluna «canal» da §3.1; «emulador» é Android **e** iOS (§4.3).

| o que | `web` | `android` | `ios` | `conversa` |
|---|---|---|---|---|
| superfície, elemento, ação, rota, navegação, `busca` | ✓ | ✓ | ✓ | — |
| `historico_de_navegacao`, `estados_restauraveis` | — | ✓ | ✓ | — |
| `avisa_antes`, `relata_mudancas` (push num aparelho, §6.3) | — | ✓ | ✓ | — |
| `conversa`, `agente`, `marca_horario`, `recebe_documento`, `grupo` | — | — | — | ✓ |
| `eventos` (conversa + tela da Agenda) | ✓ | ✓ | ✓ | ✓ |
| `convite`, `so_por_convite`, `aceita_contato` | ✓ | — | — | ✓ |
| `para_tipo`, `publico`, `vitrine_url`, `propoe_na_vitrine`, `em_breve` | ✓ | — | — | — |
| `quer_a_marca`, `nome_visivel`, `descricao_humana`, `marca` | ✓ | ✓ | ✓ | ✓ |
| `credencial_sondagem`, `tenant_sondagem`, `versao`, operação fora da conversa | — | — | — | — |

A última linha se prova no **contrato** (o teste do app, a trilha, o `/health`):
nenhum canal se aplica, e o que a matriz cobra é o `resultado`.

## A chave que o gerador não conhece

⛔ **Reprova** (código 2), sem escrever matriz nenhuma:

    ✗ okmigo/manifesto.json: agenda: chave de topo desconhecida `x` — acrescente a chave
      à tabela §3.1 do PADRAO-QA e ao gerador (okmigo_cartao/matriz.py, DECLARACOES)

A lista é fechada de propósito: uma declaração nova que o gerador ignorasse em
silêncio sumiria da matriz, e o ciclo aprovaria um app sem nunca ter provado o
que ela promete. O gesto é acrescentar a linha na §3.1 **e** em `DECLARACOES`,
no mesmo PR em que a chave nasce.

As conhecidas em 05/10/2026: as dos onze apps (`aceita_contato agente
avisa_antes conversa convite credencial_sondagem descricao descricao_humana
endpoint estados_restauraveis eventos forma historico_de_navegacao
marca_horario navegacao nome_visivel para_tipo publico quer_a_marca
recebe_documento relata_mudancas rotas slug so_por_convite superficies
tenant_sondagem tipo versao`, mais o `vitrine_url` do sohautos), `propoe_na_vitrine`
e `marca` (documentadas no okmigo), as que o SDK deste pacote emite e o okmigo
lê (`busca`, `em_breve`, `grupo`), e `operacoes`, que o okmigo e o próprio
`okmigo_cartao` leem.

⚠️ **Seis delas não estão na tabela §3.1 em 05/10/2026** — `vitrine_url`,
`propoe_na_vitrine`, `marca`, `busca`, `em_breve` e `grupo`. A frase delas aqui
saiu do registro do okmigo; a linha da §3.1 tem de ser acrescentada lá.

`slug`, `endpoint`, `forma`, `descricao` e `tipo` são conhecidas e não geram
linha: o que elas prometem já se prova pela `versao` e pela sondagem.

## `--conferir`

Regera a matriz do manifesto de **hoje** e a compara com a preenchida (o JSON
de `--formato json`, com as células escritas). Reprova (código 1) e lista cada
pendência quando:

- uma linha do manifesto de hoje **não tem par** na preenchida (o manifesto
  ganhou superfície, ação, operação… depois do ciclo);
- um canal que se aplica está vazio — ou com «—»: a régua é a matriz regerada,
  não a do arquivo;
- um canal ou o `resultado` começa com «falhou»;
- o `resultado` está vazio ou não começa com «passou» nem «falhou».

Linha da preenchida que o manifesto de hoje não tem mais vira aviso, não
reprovação. `evidencia` não é conferida — mas é ela que diz onde está a captura
ou o turno da trilha, e o registro do ciclo (§10) a pede.

## Os manifestos dos testes

`tests/dados/manifestos/` tem os 14 manifestos registrados dos onze apps,
copiados da `main` de cada repo em 05/10/2026 (calendar `2b34d2c`, estoufit
`683fc39`, dinfinance `f7586a8`, radaria `848fa6c`, horaok `0216aae`,
comcontabil `5e67390`, dogiromoney `b93b19b`, marketplace `ea215bb`, sohautos
`c34f66c`). ⚠️ Este repositório é público: o `endpoint` de todos virou
`http://SEU-HOST:8000/mcp/` e a `credencial_sondagem` do horaok virou
`credencial-ficticia`. O prediomeu e o cardapmesa geram o manifesto pelo SDK e
não o versionam; não estão aqui.

A contagem em 05/10/2026:

| app (slug) | linhas |
|---|---|
| agenda (calendar) | 82 |
| estoufit (personal) | 89 |
| estoufit-aluno | 206 |
| estoufit-nutri | 60 |
| dinfinance | 138 |
| radaria | 346 |
| horaok | 145 |
| comcontabil (escritório) | 378 |
| comcontabil-cliente | 201 |
| dogiromoney | 356 |
| dogiromoney-pagador | 24 |
| marketplace | 110 |
| marketplace-loja | 130 |
| sohautos | 60 |
