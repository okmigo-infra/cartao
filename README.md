# okmigo-cartao — o crivo do cartão declarado

Este repositório existe para quem escreve um **app para o okmigo** testar a tela
**antes** de registrá-la — e para propor um elemento novo do vocabulário sem
precisar de acesso ao produto.

No okmigo, um serviço não desenha a própria tela: ele **declara** um cartão
(um subconjunto do [Adaptive Cards](https://adaptivecards.io/), com algumas
chaves próprias prefixadas `okmigo`), e o produto **reconstrói** esse cartão no
vocabulário dele, descartando em silêncio o que não conhece. Esse reconstrutor
é o **crivo**, e é ele que está aqui — o mesmo código que roda no produto.

⚠️ **O que não está aqui, de propósito:** os renderizadores do produto (web e
app), a ponte que busca os dados, o registro, o produto em si. O que se entrega
é o **contrato** e o **crivo**; a aparência é do produto.

## Comece por aqui

```bash
pip install -e '.[dev]'
python -m okmigo_cartao exemplos/academia.json --dados exemplos/academia.dados.json \
    --escrituras guardar_perfil,iniciar_treino,encerrar_treino --html saida/academia.html
```

A linha de comando responde as três perguntas que importam:

1. **Passou?** — ou por que a tela inteira foi recusada.
2. **O que o crivo comeu?** — o modo de falha desta plataforma quase nunca é
   erro: é a tela sair **sem o pedaço**, com tudo em 200. O relatório nomeia
   cada tipo que entrou e não saiu, e cada chave lida e descartada.
3. **Como fica, pelado?** — `--html` escreve a **casca**: o cartão reconstruído
   em HTML **sem uma linha de CSS**. Se o documento pelado não faz sentido,
   nenhum renderizador conserta. O feio é intencional.

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

A definir pelo dono do repositório antes da publicação.
