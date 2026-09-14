# Catálogo do SDK Python

O SDK é uma forma tipada de escrever o mesmo cartão declarado que o OkMigo já
aceita. Ele não envia Python ao produto: `compilar()` produz JSON, e esse JSON
passa pelo crivo fechado antes de qualquer cliente desenhá-lo.

```text
componentes Python → JSON declarado → crivo → renderer Web ou nativo
```

O catálogo usa duas camadas:

- **primitivas tipadas** representam capacidades universais já aceitas pelo
  crivo, como texto, campo, ação, imagem, calendário e progresso;
- **composições** combinam essas primitivas em métricas, fichas, formulários e
  estados vazios. Elas não criam poderes novos no JSON.

Essa separação permite acrescentar receitas de interface com baixo custo. Um
novo tipo nativo só é necessário quando a composição perde uma interação ou
uma semântica importante — e, nesse caso, precisa existir no Web, no app e no
fallback de clientes antigos.

## Importação

O catálogo completo é exportado pelo pacote:

```python
from okmigo_cartao import CampoTexto, Formulario, Tela
```

Os componentes originais continuam disponíveis em `okmigo_cartao.sdk`. Para
código novo, importar do pacote principal deixa primitivas e composições no
mesmo lugar.

## Estrutura e conteúdo

| intenção | componentes |
|---|---|
| texto e hierarquia | `Texto`, `PapelDoTexto`, `Fato`, `Fatos` |
| agrupamento responsivo | `Painel`, `Secao`, `Area`, `Faixa`, `Tabela` |
| listas vindas dos dados | `Repetir`, `Condicao` |
| estados e degradação | `ComAlternativa`, `EstadoVazio` |
| resumos | `Metrica`, `GradeDeMetricas`, `Ficha` |

`Secao` é o agrupamento completo: pode ter identidade, estado visível, tom
semântico, grade, altura, comportamento ao toque e apresentação sobreposta.
Use `Painel` para o caso simples e `Secao` quando uma dessas intenções existir.

## Entrada e ações

| intenção | componentes |
|---|---|
| texto | `CampoTexto` |
| número sem perda de formato | `CampoNumero` |
| lista, cards ou busca estrita | `Escolha`, `FormaDaEscolha`, `Opcao` |
| autocomplete remoto livre | `Busca` |
| upload | `Arquivo`, `FormatoDeArquivo` |
| formulário completo | `Formulario` |
| leitura e escrita | `Acao`, `Acoes` |
| mostrar e esconder | `Alternar`, `AlvoDeVisibilidade` |
| salvar e avançar uma etapa | `EnviarEAvancar` |

```python
from okmigo_cartao import (
    Acao,
    CampoNumero,
    CampoTexto,
    EnfaseDaAcao,
    Escolha,
    FormaDaEscolha,
    Formulario,
    Opcao,
    Tela,
)

tela = Tela(
    "Perfil",
    (
        Formulario(
            "Dados básicos",
            campos=(
                CampoTexto("nome_perfil", "nome", "Nome", obrigatorio=True),
                CampoNumero("peso_perfil", "peso", "Peso (kg)", minimo=20),
                Escolha(
                    "objetivo_perfil",
                    "objetivo",
                    "Objetivo",
                    (
                        Opcao("Ganhar força", "forca", "Treinos progressivos", "💪"),
                        Opcao("Ter disposição", "disposicao", "Rotina sustentável", "⚡"),
                    ),
                    FormaDaEscolha.CARTOES,
                    obrigatoria=True,
                ),
            ),
            acoes=(
                Acao.escrever(
                    "Salvar",
                    "salvar_perfil",
                    enfase=EnfaseDaAcao.PRIMARIA,
                ),
            ),
        ),
    ),
)

tela.conferir(escrituras={"salvar_perfil"})
```

Cada `id` identifica o estado local do campo; `campo` é o nome enviado ao
serviço. A ação recebe somente os campos da caixa onde está. Operações que o
serviço não declarou recusam a tela inteira, evitando botões que parecem
funcionar e não fazem nada.

## Mídia, documentos e utilidades

| intenção | componentes |
|---|---|
| imagem do domínio do produto | `Imagem`, `AlturaDaImagem` |
| arquivo guardado pelo serviço | `Documento` |
| copiar um valor | `Copiar` |
| contagem regressiva | `Cronometro` |
| andamento | `Progresso` |
| autorização em terceiro | `Autorizar` |

`Imagem` exige descrição acessível. `Documento` nomeia uma operação de leitura
e envia apenas um pedido escalar. `Autorizar` continua sendo a única saída para
um endereço de terceiro; ações comuns nunca carregam URL.

## Agenda

`Calendario` cobre mês, semana e dia, abertura de formulário ao tocar numa
data, abertura de detalhe ao tocar num evento e remarcação explícita por
arrasto:

```python
from okmigo_cartao import (
    AcaoDoEvento,
    AoTocarODia,
    Calendario,
    Evento,
    GestoDoEvento,
    TipoDeEvento,
    VistaDoCalendario,
)

agenda = Calendario(
    eventos=(
        Evento(
            "{inicio}",
            "{titulo}",
            id="{id}",
            tipo=TipoDeEvento.ATENDIMENTO,
        ),
    ),
    vista=VistaDoCalendario.SEMANA,
    ao_tocar_o_dia=AoTocarODia("novo_atendimento", "data"),
    acoes_do_evento=(
        AcaoDoEvento(
            TipoDeEvento.ATENDIMENTO,
            {"atendimento_id": "id", "inicio": "novo_inicio"},
            gesto=GestoDoEvento.ARRASTAR,
            enviar="remarcar_atendimento",
        ),
    ),
)
```

O serviço nomeia campos e operações; a data tocada e o destino do arrasto são
preenchidos pelo cliente.

## Financeiro

Os componentes financeiros existentes no renderer também têm autoria tipada:

- `CartoesFinanceiros` e `CartaoFinanceiro`;
- `ListaFinanceira` e `LancamentoFinanceiro`;
- `Distribuicao` e `ItemDeDistribuicao`;
- `TomFinanceiro` e `SemanticaFinanceira`.

Eles declaram significado, não cor. O cliente escolhe os tons reais para modo
claro, escuro, contraste e plataforma.

## Dados repetidos

`Repetir` representa a expansão segura de listas do manifesto. Não é um laço
executado no cliente e não aceita expressão:

```python
from okmigo_cartao import Condicao, Ficha, Repetir

abertos = Repetir(
    Ficha("{titulo}", "{detalhe}"),
    quando=Condicao("status", ("aberto",)),
)
```

Use `de="itens"` para repetir uma sublista do item atual. O preview expande o
molde com `--dados` antes de passá-lo pelo crivo.

## Como escolher entre composição e tipo nativo

Antes de acrescentar uma capacidade, siga esta ordem:

1. Monte-a com as primitivas existentes.
2. Transforme a combinação recorrente numa composição Python.
3. Acrescente apenas uma dica semântica a um tipo existente se a composição
   não preservar o comportamento.
4. Crie um tipo nativo novo somente quando a interação for universal e não
   houver fallback honesto.

Um tipo nativo novo precisa, no mesmo trabalho, de crivo, renderer Web,
renderer nativo, acessibilidade, claro/escuro, limites, documentação e testes
de degradação. Receitas Python precisam apenas compilar para o contrato já
conferido.

## Validação mínima

```bash
python -m okmigo_cartao preview seu_modulo.py:APLICATIVO \
  --dados dados.aplicativo.json
```

Valide sempre o aplicativo inteiro, em desktop e celular, nos modos claro e
escuro. Para listas, use pelo menos dois itens, texto longo, zero e estado
vazio; validar apenas o molde cru não exercita `Repetir`.
