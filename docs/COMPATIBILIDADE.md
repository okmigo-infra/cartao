# Compatibilidade, SemVer e depreciação

Quem consome este pacote o pina por **SHA** e só recebe a versão nova quando
alguém troca o pino. Até lá, nada avisa. Então a pergunta «a versão nova
estraga alguma tela?» tem de ser respondida **aqui, antes da tag**, e o
número da versão tem de dizer a resposta.

## A matriz

O que muda numa versão, e o número que isso exige. Em `0.x` o slot de
quebra é o **menor** (`0.21 → 0.22`); de `1.0` em diante, o **maior**.

| o que mudou | como se detecta | `0.x` | `≥ 1.0` |
|---|---|---|---|
| só `README.md`, `docs/`, `scripts/`, `tests/`, `.github/` | — | nenhuma versão | nenhuma |
| `src/` mudou e nenhuma tela do corpus mudou | `versao_subiu.py` | correção (`0.21.0 → 0.21.1`) | correção |
| a saída do crivo mudou **sem perder nada** (chave nova, valor normalizado) | `compatibilidade.py`: `forma` | correção | correção |
| um cartão que era recusado passou a entrar | `compatibilidade.py`: `novo_aceito` | correção | correção |
| nome novo no `__all__`, tipo ou dica nova no vocabulário | `contrato_so_cresce.py` (relata) | menor | menor |
| o SDK compila o **mesmo** aplicativo num JSON diferente | `compatibilidade.py`: `regenerar` | menor | menor |
| um cartão que passava agora é **recusado** | `compatibilidade.py`: `quebra` | menor | **maior** |
| a tela perdeu um nó, um tipo ou um texto acessível | `compatibilidade.py`: `quebra` | menor | **maior** |
| um aplicativo Python que compilava agora levanta exceção | `compatibilidade.py`: `quebra` | menor | **maior** |
| um nome saiu do `__all__` | `contrato_so_cresce.py` | menor **e janela** | maior **e janela** |

⚠️ `regenerar` pede versão menor mesmo sem quebrar nada, porque o CI de cada
consumidor confere que o manifesto é o que o gerador produz: a PR de pino
chegaria VERMELHA lá, e quem mergeia precisa ler isso no número.

## As quatro travas da esteira

Todas rodam na PR e de novo na tag (`publicar.yml`), porque a tag pode cair
num commit que nunca passou por PR.

1. **`scripts/versao_subiu.py`**: mexeu em `src/`, a versão sobe, e nunca volta.
2. **`scripts/contrato_so_cresce.py`**: um nome só sai do `__all__` no slot de
   quebra **e** depois de cumprir a janela de depreciação (abaixo).
3. **`scripts/compatibilidade.py`**: roda a **última tag** e a **árvore**, cada
   uma num processo com o próprio `src/` no `PYTHONPATH`, sobre os mesmos
   cartões e os mesmos dados, e compara superfície a superfície. Reprova se a
   pior diferença pede um salto maior do que a versão deu.
4. **`tests/test_renderiza_no_navegador.py`** (job `navegador`): o bundle Web
   oficial desenha cada superfície de `exemplos/` nos extremos, sem erro no
   console e sem texto passando da borda do celular.

### Os cinco cenários

Validar o molde cru não prova a expansão: um `_repetir_lista` só vira tabela
depois de receber linhas. Então cada superfície é conferida com dados, e os
dados saem da **forma do próprio molde** (`{campo}`, `_repetir_lista`, `_de`,
`_quando`), sem que ninguém escreva fixture:

| cenário | dados |
|---|---|
| `cru` | nenhum (o molde como está) |
| `vazio` | resumo preenchido, toda lista vazia |
| `tipico` | três linhas, três itens por sublista |
| `muitas_linhas` | 250 linhas e 60 itens por sublista, acima dos tetos de 200 linhas de tabela e 50 itens de `_de` |
| `textos_longos` | três linhas com textos de 1.200 caracteres e números nos extremos (0, −987.654.321,25, 10¹², 0,01) |

⚠️ Os dois extremos ficam separados de propósito: 250 linhas com 1.200
caracteres em cada campo, num molde grande, expandem para gigabytes antes de
o crivo contar o primeiro nó. Medido: um molde de 47 KB chegou a 3,5 GB.

### O que se compara

Para cada cenário: aceita ou recusada, o hash da tela reconstruída, o número
de nós, a contagem por tipo e os textos acessíveis (`alt` de imagem,
`rotulo` de campo, `titulo` de botão). Um nó, um tipo ou um texto acessível
a menos é `quebra`, mesmo com a tela aceita, porque o modo de falha desta
plataforma é a tela sair **sem o pedaço**, sem erro nenhum.

## O corpus

`tests/compat/corpus/forma-NN.json` é a **forma** dos cartões que os
aplicativos do ecossistema declaram hoje. Não é o cartão: o anonimizador
(`scripts/compatibilidade.py --anonimizar`) troca todo texto, nome de campo,
operação, rota, parâmetro e endereço por pseudônimo, e guarda só o que o
crivo lê:

- a estrutura, os tipos e as chaves do vocabulário (toda string que já é
  constante no `src/` deste pacote, portanto pública);
- os moldes, com `{campo}` trocado por um pseudônimo que carrega a
  natureza do campo (`num3`, `url7`, `data2`, `txt12`), para os dados
  sintéticos saírem do mesmo tipo;
- o comprimento dos textos, porque os tetos (40, 60, 120, 200 e 400
  caracteres) fazem parte da forma;
- as referências cruzadas: a mesma string vira sempre o mesmo pseudônimo, de
  modo que a operação do botão, o `id` alvo de um `ToggleVisibility`, a rota
  do `okmigoNavegar` e o `_de` da sublista continuam apontando para o mesmo
  lugar.

Duas provas guardam o corpus:

- **fidelidade**, ao gerar: cada forma passa pelo crivo lado a lado com o
  cartão real, nos cinco cenários, e só é escrita se der a mesma aceitação,
  o mesmo número de nós e os mesmos tipos. Uma forma infiel fica de fora e
  o motivo aparece. Na geração de 28/09/2026 foram 19 formas de 19, com 101
  superfícies;
- **nada interno**, em `tests/test_compatibilidade.py`: toda string do corpus
  tem de ser vocabulário do pacote, número, sinal ou pseudônimo. O teste tem
  o caso negativo ao lado.

### Regenerar

Quem tem os repositórios consumidores clonados lado a lado:

```bash
python3 scripts/compatibilidade.py --consumidores .. --anonimizar tests/compat/corpus
```

Ele lê a `origin/main` de cada vizinho por `git archive`, sem tocar a árvore
de trabalho deles, e só escreve aqui o que passou pela anonimização e pela
fidelidade. Regenere quando um aplicativo novo nascer ou uma tela mudar de
forma. O corpus só cobre o que ele contém.

### Com os cartões reais, localmente

Antes de marcar a tag, a mesma comparação roda contra os cartões **reais**,
incluindo os geradores `aplicativo_sdk_*.py` de cada consumidor (o que pega
`regenerar`) e os `examples/*.dados.json` que eles mantêm para o preview:

```bash
python3 scripts/compatibilidade.py --consumidores ..          # contra a última tag
python3 scripts/compatibilidade.py --consumidores .. --teto   # e quantas linhas cada tela aguenta
```

O relatório só dá contagens e nomes de superfície. Nada dos cartões é escrito.

## Depreciação: aviso, janela e mensagem

Um nome público não sai de uma vez. Ele passa por três estados, e as regras
estão em [`src/okmigo_cartao/depreciacao.py`](../src/okmigo_cartao/depreciacao.py):

1. **Depreciado.** O nome sai do módulo, mas continua no `__all__` e continua
   funcionando: o `__getattr__` do pacote o entrega e emite um
   `DeprecationWarning` que aponta a linha de quem usou, com a versão em que o
   aviso começou, a primeira versão que pode removê-lo, o que usar no lugar e
   o motivo:

   ```python
   Depreciacao(nome="TelaAntiga", desde="0.23.0", sai_em="0.25.0",
               alvo="okmigo_cartao.sdk:Tela", use="Tela", motivo="Renomeada.")
   ```

2. **Janela.** Em `0.x`, pelo menos **duas** versões menores entre `desde` e
   `sai_em`. De `1.0` em diante, só na versão maior seguinte. Com a cadência
   de hoje, isso dá ao consumidor pelo menos uma PR de pino com o aviso visível
   antes da PR que quebraria.
3. **Removido.** O nome sai do `__all__` e de `DEPRECIACOES` no mesmo commit,
   na versão `sai_em` ou depois, e no slot de quebra.
   `contrato_so_cresce.py` recusa a remoção que não estava declarada na base
   ou que chega antes do `sai_em`.

⚠️ O vocabulário do **crivo** (tipos e chaves do cartão) não tem aviso em tempo
de execução, porque o crivo roda no produto e o autor do aplicativo não vê o
`warnings` de lá. Tirar uma chave do vocabulário é `quebra` na comparação, e a
janela é dada pela documentação: a linha do tipo no [`CONTRATO.md`](../CONTRATO.md)
ganha «depreciado desde X, sai em Y» pelo mesmo período.
