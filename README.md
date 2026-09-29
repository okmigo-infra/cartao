# okmigo-cartao — o crivo do cartão declarado

## Retrato (28/09/2026)

| | |
|---|---|
| **Publicada** | **v0.22.1**, SHA `828e4cb`, tag de 29/09. |
| **Na `main`** | <!-- conferir: versao_pacote -->0.22.1<!-- /conferir -->: além da régua de compatibilidade, da depreciação com janela e da correção da casca da 0.22.0, declara rotas internas fora da navegação e a injeção confiável do ator local. |
| **Quem consome** | **12 repositórios** do ecossistema pinam `828e4cb` na `main`; cada produção avança pelo próprio fluxo de promoção. Medido em 29/09 depois da rodada de atualização dos consumidores. |
| **Ambientes** | Nenhum: é um pacote. Publicar é **tag**, e quem roda o crivo é o produto e a suíte de cada consumidor. |
| **Compatibilidade** | A 0.22.1 mantém a compatibilidade de expansão comprovada na 0.22.0: as <!-- conferir: superficies_do_corpus -->101<!-- /conferir --> superfícies do corpus e as dos `exemplos/` produzem o mesmo resultado nos cinco cenários da régua. Nos cartões reais, a prova lê cada consumidor antes da publicação. |
| **Riscos** | 1. **O pino é mudo.** Quando o crivo anda, nada nos consumidores acusa; quem avisa é um processo do lado de lá, de 3 em 3 horas. 2. **O teto de 2.000 nós recusa a tela INTEIRA.** Medido em 28/09 nos cartões reais, com os dados de exemplo do próprio aplicativo: há tela que é recusada a partir de 13 linhas. 3. **O quadro de 390 px do preview, numa janela larga, não aplica as regras `@media` do renderer**: o mestre–detalhe aparece lado a lado e cortado, o que nenhum celular vê. Para a conferência fiel, abra o preview numa janela estreita. 4. **A régua só conhece o que o corpus contém.** Tela que nasceu depois da última geração não está nele. |
| **Próximos passos** | Regenerar o corpus a cada aplicativo novo e rodar `--consumidores` antes de cada próxima tag. |

A política de versão, a matriz do que exige cada número e a depreciação estão
em [`docs/COMPATIBILIDADE.md`](docs/COMPATIBILIDADE.md).

Este repositório existe para quem escreve um **app para o okmigo** testar a tela
**antes** de registrá-la — e para propor um elemento novo do vocabulário sem
precisar de acesso ao produto.

No okmigo, um serviço não desenha a própria tela: ele **declara** um cartão
(um subconjunto do [Adaptive Cards](https://adaptivecards.io/), com algumas
chaves próprias prefixadas `okmigo`), e o produto **reconstrói** esse cartão no
vocabulário dele, descartando em silêncio o que não conhece. Esse reconstrutor
é o **crivo**, e é ele que está aqui — o mesmo código que roda no produto.

⚠️ **O que não está aqui, de propósito:** o código-fonte do produto, o cliente
nativo, a ponte que busca os dados e o registro. O pacote inclui somente um
**bundle compilado do renderer Web oficial** para o preview local. O serviço
continua recebendo apenas o contrato e o crivo; aparência e componentes não
podem ser fornecidos pelo app.

## Escrever a tela com o SDK Python

O SDK Python oferece uma forma tipada de autoria. Ele não substitui nem
afrouxa o contrato: componentes como `Tela`, `Busca`, `Tabela` e `Acao`
compilam para o mesmo cartão restrito que o crivo já reconstrói. Não há HTML,
JavaScript ou URL de ação, e uma linha tocável só pode executar leitura.

```python
from okmigo_cartao import Busca, Navegacao, Tela, Tema

tela = Tela(
    titulo="Meus ativos",
    tema=Tema.MERCADO,
    navegacao=Navegacao.INFERIOR,
    componentes=(
        Busca(
            id="ticker_busca",
            campo="ticker",
            rotulo="Ativo da B3",
            placeholder="Digite PETR4",
            sugestoes_por="buscar_ativos",
        ),
    ),
)

cartao = tela.compilar()  # JSON do contrato atual
tela.conferir(leituras={"buscar_ativos"})  # o mesmo crivo de produção
```

O aplicativo neutro em
[`exemplos/sdk_catalogo.py`](exemplos/sdk_catalogo.py) reúne formulários,
métricas, agenda, documentos, componentes financeiros e o catálogo universal
em <!-- conferir: superficies_do_catalogo -->seis<!-- /conferir --> superfícies:

```bash
python -m okmigo_cartao preview exemplos/sdk_catalogo.py:APLICATIVO
```

As telas dele são estáticas. Quando a tela depende da lista que o serviço
devolve (tabela que repete por linha, sublista, filtro, rota com parâmetro),
o exemplo é [`exemplos/sdk_dados.py`](exemplos/sdk_dados.py), com dados em
[`exemplos/sdk_dados.dados.json`](exemplos/sdk_dados.dados.json):

```bash
python -m okmigo_cartao preview exemplos/sdk_dados.py:APLICATIVO \
  --dados exemplos/sdk_dados.dados.json
```

Para testar o **aplicativo inteiro direto do Python**, exponha um `Aplicativo`
e passe um mapa de dados por superfície. A navegação inferior troca de verdade
entre todos os cartões que o produto declarará ao OkMigo:

```bash
python -m okmigo_cartao preview seu_app/okmigo/manifesto.py:APLICATIVO \
  --dados seu_app/okmigo/exemplos/preview.dados.json
```

Também é possível passar o `manifesto.json` compilado; ele é útil para o
registro e para conferir que a saída do SDK não mudou, mas não é necessário
para desenvolver ou visualizar o app.

O comando abre `http://localhost:4173` com desktop e celular de 390 px lado a
lado, navegação entre superfícies e alternância claro/escuro. A página é
reconstruída a cada recarga, então basta salvar o manifesto/dados e atualizar o
navegador. Em container, publique ou encaminhe a porta `4173`. Para gerar um
arquivo sem subir servidor, acrescente `--saida preview.html`.

O preview usa o mesmo componente React e os mesmos estilos do OkMigo Web. O
bundle compilado viaja dentro do wheel Python: quem desenvolve um app não
precisa clonar nem executar o produto. Navegação, responsividade, claro/escuro e
respostas declaradas em `_preview.respostas` funcionam localmente, inclusive
ida ao detalhe e volta à lista. Escritas são simuladas e nenhuma ação faz
requisição externa. A conferência final do cliente nativo continua sendo feita
no emulador Flutter.

⚠️ O quadro de 390 px reproduz o Web responsivo **só numa janela estreita**.
O renderer adapta por `@media (max-width: …)`, que olha a janela e não o
quadro: numa janela larga, o mestre–detalhe aparece lado a lado e cortado
dentro do quadro de celular. Para conferir o celular, estreite a janela (ou
use o modo de dispositivo do navegador) e escolha «Celular».

O catálogo tipado cobre estrutura responsiva, cartões clicáveis, menus de
ações, confirmação, abas, expansíveis, diálogos, tabelas flexíveis, campos
semânticos, múltipla escolha, alternância, quantidade, galeria, linha do tempo,
paginação, estados, calendário, gráficos, blocos financeiros, cabeçalho
universal, mestre–detalhe, fluxos retomáveis, rotas tipadas, busca global e
navegação agrupada com indicadores.

Quando a mudança de largura exige mais do que reorganizar colunas, use
`TelaResponsiva(celular=..., desktop=...)`. As duas composições compartilham a
mesma `Superficie`, fonte, permissões, tema e navegação. A versão de celular é
o fallback compatível; clientes novos escolhem a versão de desktop quando há
espaço. Isso permite uma lista direta no telefone e um painel denso com menu
lateral e abas no desktop, sem duplicar serviço nem regra de negócio. Padrões
de produto como ficha, grade de métricas e estado vazio são composições dessas
primitivas e não aumentam a superfície do contrato.
Consulte [`docs/CATALOGO-SDK.md`](docs/CATALOGO-SDK.md) para a lista completa,
exemplos e a regra para evoluir o vocabulário.

Para agir **dentro de um grupo** do okmigo (responder a quem usou o serviço,
mandar mensagem, sugerir atividade, enquete ou material) sem nunca ver o
grupo, use `okmigo_cartao.grupo` — o contrato, a matriz de permissões e um
exemplo completo estão em [`docs/GRUPOS.md`](docs/GRUPOS.md).

O aplicativo é mais do que a soma dos cartões. `Rota` + `Acao.navegar`
permitem abrir detalhes sem URL livre; `BuscaDoAplicativo` conecta uma busca
transversal a essas rotas; `EstadoRestauravel` declara exatamente quais partes
da UI podem sobreviver à troca de tela; e `HistoricoDeNavegacao` limita
recentes e favoritos. Todas essas declarações saem no JSON do manifesto e são
reconferidas pelo host — o Python nunca é executado no OkMigo.

Para passear pelo catálogo em <!-- conferir: superficies_do_catalogo -->seis<!-- /conferir --> superfícies navegáveis:

```bash
python -m okmigo_cartao preview exemplos/sdk_catalogo.py:APLICATIVO
```

### Trazendo um aplicativo existente

Há duas etapas possíveis. `AplicativoDoContrato` é uma ponte temporária: ele
transforma o manifesto que o produto já testa num objeto compilável e permite
abrir o aplicativo inteiro no preview Python:

```python
from okmigo_cartao import AplicativoDoContrato, Tema

APLICATIVO = AplicativoDoContrato(
    manifesto_existente(),
    tema_padrao=Tema.OPERACAO,
)
MANIFESTO = APLICATIVO.compilar()
```

O estado final é não depender de dicionários crus. Para uma conversão mecânica
inicial, o repositório inclui um transpilador que transforma um ou mais
manifestos existentes em código Python com `Aplicativo`, `Superficie`, `Tela`
e os componentes públicos do catálogo:

```bash
python scripts/transpilar_manifesto.py \
  ../seu-app/okmigo/manifesto.json \
  --saida ../seu-app/okmigo/aplicativo_sdk_seu_app.py
```

Depois da conversão, esse arquivo Python vira a fonte que o time evolui; o
`gerar_manifesto.py` do produto só reexporta o `APLICATIVO` e materializa o
JSON para registro. O transpilador não fica no caminho de execução e não deve
ser rodado novamente sobre o JSON gerado, pois sobrescreveria edições feitas
no código tipado. Nos dois estágios, o JSON que cruza a fronteira passa pelo
mesmo crivo fechado do OkMigo.

## Comece por aqui

```bash
pip install -e '.[dev]'
python -m okmigo_cartao preview exemplos/sdk_catalogo.py:APLICATIVO
```

A linha de comando responde as três perguntas que importam:

1. **Passou?** — ou por que a tela inteira foi recusada.
2. **O que o crivo comeu?** — o modo de falha desta plataforma quase nunca é
   erro: é a tela sair **sem o pedaço**, com tudo em 200. O relatório nomeia
   cada tipo que entrou e não saiu, e cada chave lida e descartada.
3. **Como fica, pelado?** — `--html` escreve a **casca**: o cartão reconstruído
   em HTML **sem uma linha de CSS**. Se o documento pelado não faz sentido,
   nenhum renderizador conserta. O feio é intencional.

### Testando o SEU manifesto

Passe o manifesto inteiro e diga a superfície:

```bash
python -m okmigo_cartao okmigo/manifesto.json --superficie extrato \
    --dados dados-do-extrato.json --escrituras marcar_pago,estornar --dominio seudominio.com
```

- `--dados` é `{"resumo": {...}, "linhas": [...]}` — o mesmo par que a `fonte`
  da superfície declara (o objeto de resumo e a lista). Use dados que pareçam
  os do seu serviço: nomes de campo iguais, uma linha com valor zero, uma com
  texto longo.
- `--escrituras`/`--leituras` são as operações que o **seu servidor MCP**
  expõe (as de escrita e as de leitura). É contra elas que o produto confere
  cada botão: um `Action.Submit` que nomeie operação fora da lista **recusa a
  tela inteira** — e é melhor descobrir isso aqui do que depois de registrar.
  Se o seu manifesto declarar `operacoes[{nome, efeitos}]`, a ferramenta as lê
  sozinha; sem isso, sem as bandeiras, os botões **não são conferidos**, e ela
  avisa.

⛔ **Validar o molde cru não prova nada.** Um molde com `_repetir_lista` só vira
tabela, grade ou fichas depois de expandido com dados — e o crivo descarta a
tabela que ficou só com cabeçalho, a lista que ficou sem opção. `--dados`
expande o molde do mesmo jeito que a ponte do produto expande (`{campo}`,
`_repetir_lista`, `_quando`, `_de`). Rode com dados que pareçam os seus, ou o
«passou» é falso.

## Como código

```python
from okmigo_cartao import validar, Config, casca, relatorio

tela, erro = validar(cartao, escrituras={"salvar"}, leituras={"baixar"},
                     config=Config(dominios=("seudominio.com",)))
```

`tela` é o cartão reconstruído (nunca o original) ou `None`; `erro` é o motivo
da recusa da tela inteira. `escrituras`/`leituras` são as operações que o
serviço declarou — um `Action.Submit` (ou `okmigoDocumento.ler`) fora delas
recusa o cartão inteiro. `Config` diz o que o crivo precisa saber do ambiente:
os domínios do produto (imagens só passam se forem deles; autorizações em
terceiro só passam se **não** forem), a base que torna `/img/...` absoluto, e o
teto de anexo.

O contrato do vocabulário — cada tipo, o que ele aceita, o que evapora e por
quê — está em [`CONTRATO.md`](CONTRATO.md).

## Propor um elemento novo

Um PR de elemento novo entra quando traz **as quatro coisas juntas**:

1. **O caso** — a tela real que não cabe no vocabulário de hoje, e por que as
   dicas existentes (`okmigoGrade`, `selectAction`, `ToggleVisibility`…) não
   resolvem. Elemento nasce de observação, não de ideia.
2. **O crivo** — a reconstrução em `crivo.py`, com os tetos do produto (não do
   autor) e as listas fechadas; **e os testes**, com o caso negativo ao lado de
   cada positivo. Teste que passa no cenário quebrado não é teste.
3. **O contrato** — a linha do tipo em `CONTRATO.md`: o essencial e as armadilhas.
4. **Um fixture** em `exemplos/`, sintético, que o exercite.

E a pergunta que decide se está pronto: **«o que o cliente que não conhece isto
vai desenhar?»** Uma **dica em tipo que já existe** (um campo novo num
`Container`, num `Input`, num `ActionSet`) degrada sozinha — o cliente velho
ignora o campo. Um **tipo novo** some no cliente velho, e por isso custa mais:
precisa dizer o que o autor deve declarar ao lado para a informação não se
perder. Se a resposta é «nada», não está pronto.

Duas regras que não se negociam, e estão escritas no próprio crivo:

- **Nada de cor, fonte ou pixel.** O serviço declara intenção (tamanho como
  palavra, estilo como hierarquia, altura como faixa, cor como significado);
  quem escolhe a aparência é o produto.
- **Ação nomeia capacidade, nunca endereço.** Um botão não carrega URL. A única
  saída para um endereço de terceiro é `okmigoAutorizar`, cercada de travas —
  e nenhuma proposta afrouxa uma delas.

## O que a esteira cobra

Toda PR aqui passa por estas travas. Elas existem porque **este pacote é
dependência pinada por SHA em doze repositórios**, e um SHA não tem nome: a única
coisa que diz o que está instalado num pod é o `version` que o pacote declara.

| passo | o que ele impede |
|---|---|
| suíte em **3.11 e 3.12** | 3.11 é o piso que o `pyproject` promete a quem está de fora; 3.12 é o que roda em produção nos doze. Testar só um esconde metade |
| `ruff check .` | erro, não estilo: sintaxe, nome indefinido, import morto, armadilha do bugbear. Com `target-version = "py311"`, também a sintaxe que só o 3.12 entende |
| **instala pelo tarball do git** | é como o consumidor instala. O `pip install -e .` resolve `src/` pelo disco e por isso nunca vê um `assets/*.js` ficando fora do `package-data` |
| `scripts/versao_subiu.py` | mexeu em `src/` ⇒ a `version` sobe. E ela não regride |
| `scripts/contrato_so_cresce.py` | nome não sai do `__all__` sem a versão dizer (em `0.x`, o slot de quebra é o MENOR) e sem ter cumprido a janela de depreciação |
| `scripts/compatibilidade.py` | a árvore aceita e expande os cartões do corpus e dos `exemplos/` **igual** à última tag, em cinco cenários de dados; se não, a versão tem de dizer no número o que dói |
| job `navegador` | os `exemplos/` renderizam no bundle Web oficial, nos extremos, sem erro no console e sem texto passando da borda do celular |

⛔ **O `__all__` não encolhe de graça.** Quem consome está pinado num SHA antigo e
um dia recebe a PR que troca o pino. Se um nome sumiu no meio do caminho, o app
não quebra no teste de tela: quebra no `import`, e a esteira inteira dele para.

## Publicar

Publicar é **tag**, e a tag tem de ser igual ao `version` do `pyproject.toml` —
`publicar.yml` recusa se discordarem. Ele roda a suíte de novo na tag (a tag pode
ser marcada em qualquer commit, inclusive num que nunca passou por PR), prova que
o tarball instala com os assets, e escreve o Release com a linha do pino pronta
para colar:

```toml
  "okmigo-cartao @ https://github.com/okmigo-infra/cartao/archive/<sha>.tar.gz",  # vX.Y.Z
```

⛔ **O pino é SHA, nunca tag nem `main`.** Tag se move; SHA não. A tag serve para
o humano saber o que é aquele SHA — não para resolver o download.

⭐ **Antes de marcar**, quem tem os consumidores clonados ao lado roda a mesma
comparação contra os cartões reais deles, e não só contra o corpus:

```bash
python3 scripts/compatibilidade.py --consumidores ..
```

⚠️ A esteira **para** na publicação, de propósito: avisar os consumidores exigiria
uma credencial com escrita nos repositórios deles, e este repositório é público.
Quem avisa é um processo do lado de lá, que compara as versões e abre a PR.

## Licença

[Apache-2.0](LICENSE). Contribuições entram sob a mesma licença (§5 dela) — é o que
permite aceitar um PR de fora sem acordo à parte.
