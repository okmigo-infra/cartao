# okmigo-cartao — o crivo do cartão declarado

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
em cinco superfícies:

```bash
python -m okmigo_cartao preview exemplos/sdk_catalogo.py:APLICATIVO
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
requisição externa. O quadro de 390 px reproduz o Web responsivo; a conferência
final do cliente nativo continua sendo feita no emulador Flutter.

O catálogo tipado cobre estrutura responsiva, cartões clicáveis, menus de
ações, confirmação, abas, expansíveis, diálogos, tabelas flexíveis, campos
semânticos, múltipla escolha, alternância, quantidade, galeria, linha do tempo,
paginação, estados, calendário, gráficos e blocos financeiros. Padrões de
produto como ficha, grade de métricas e estado vazio são composições dessas
primitivas e não aumentam a superfície do contrato.
Consulte [`docs/CATALOGO-SDK.md`](docs/CATALOGO-SDK.md) para a lista completa,
exemplos e a regra para evoluir o vocabulário.

Para passear pelo catálogo em cinco superfícies navegáveis:

```bash
python -m okmigo_cartao preview exemplos/sdk_catalogo.py:APLICATIVO
```

### Trazendo um aplicativo existente

Uma migração grande não precisa reescrever centenas de componentes no mesmo
commit. `AplicativoDoContrato` transforma o manifesto que o produto já testa
num objeto do SDK, acrescenta a navegação/tema compartilhados e permite abrir
o aplicativo inteiro no preview Python:

```python
from okmigo_cartao import AplicativoDoContrato, Tema

APLICATIVO = AplicativoDoContrato(
    manifesto_existente(),
    tema_padrao=Tema.OPERACAO,
)
MANIFESTO = APLICATIVO.compilar()
```

O adaptador valida a forma do aplicativo, nomes únicos e a presença de um
cartão por superfície. Ele é a ponte de migração; telas novas devem usar os
componentes tipados (`Tela`, `Texto`, `Painel`, `Tabela` etc.). Nos dois casos,
o JSON que cruza a fronteira continua passando pelo mesmo crivo fechado do
OkMigo.

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

## Licença

[Apache-2.0](LICENSE). Contribuições entram sob a mesma licença (§5 dela) — é o que
permite aceitar um PR de fora sem acordo à parte.
