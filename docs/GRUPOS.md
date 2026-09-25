# Ações no grupo — o contrato tipado

Um serviço pode agir **dentro de um grupo do okmigo**: responder a quem acabou
de usá-lo, mandar uma mensagem, sugerir uma publicação (atividade, enquete,
material, aviso, convite). Ele faz isso **sem nunca ver o grupo**: nenhuma
tabela, membro, id ou texto de outra pessoa atravessa. O módulo é
`okmigo_cartao.grupo`.

## Como funciona

1. **O manifesto declara** o que o serviço pede, no campo `grupo` do
   `Aplicativo`. Declarar não ativa nada.
2. **Quem modera o grupo ativa** o serviço e escolhe quais capacidades valem.
   Também decide se a mensagem que ninguém pediu espera aprovação (o padrão é
   esperar).
3. **A ação vai na resposta** de uma chamada que o okmigo fez: o Submit de uma
   tela em que a pessoa escolheu o grupo pelo campo `okmigo_grupos`. O okmigo
   confere, executa e anota. Ao serviço volta só estado e motivo.

⛔ Não existe endpoint para o serviço escrever no grupo por conta própria.

## A matriz

| capacidade | o que faz | aprovação | quem aciona | recusa típica |
|---|---|---|---|---|
| `responder_interacao` | responde, no grupo, a quem acabou de usar o serviço | não — foi pedido | a pessoa do Submit, que precisa poder falar no grupo | `quem_pediu_nao_fala`, `uma_resposta_por_interacao` |
| `enviar_mensagem` | manda uma mensagem ao grupo | **se o grupo exigir** (padrão): volta `pendente` | o serviço | `sem_capacidade` |
| `sugerir_publicacao` | sugere uma publicação, com o serviço como autor | **sempre**: nasce rascunho; publicar é de quem publica | o serviço | `conteudo_invalido` |
| `criar_evento` | ⛔ reservada — a Agenda é a fonte única de horário | — | — | `agenda_e_a_fonte` |

Do lado do grupo, `gerir_servicos` (ativar, escolher as capacidades, aprovar
a fila, ler a trilha) é do **dono e do moderador**. Todos do grupo **veem**
quais serviços agem ali e o que podem.

Toda tentativa fica na trilha, **inclusive a recusada**, com o motivo.
Quem modera lê a trilha do grupo. Uma referência que não resolve fica só na
trilha da plataforma: mostrá-la em algum grupo contaria que ele existe.

### Os motivos de recusa (códigos estáveis)

| motivo | quando |
|---|---|
| `acao_desconhecida` | o `tipo` não é do contrato |
| `grupo_desconhecido` | a referência não é de um grupo da pessoa (ou não existe) — a mesma resposta nos dois casos |
| `servico_nao_ativado` | o grupo não ativou o serviço |
| `sem_capacidade` | o grupo não deu esta capacidade |
| `agenda_e_a_fonte` | pediu `criar_evento` |
| `conteudo_invalido` | texto vazio, enquete com uma opção, material sem `https://`… |
| `precisa_de_quem_pediu` | `responder_interacao` fora de um Submit |
| `quem_pediu_nao_fala` | a pessoa foi calada, ou o grupo está no regime «só quem modera» |
| `uma_resposta_por_interacao` | duas respostas no mesmo Submit |
| `demais_acoes` | mais de cinco ações numa resposta |

## Exemplo completo

```python
from okmigo_cartao import Aplicativo, Escolha, Fonte, Superficie, Tela, Texto
from okmigo_cartao.grupo import (
    CAMPO_DE_GRUPO, CapacidadesDeGrupo, Enquete, EnviarMensagem,
    ResponderInteracao, SugerirPublicacao, acoes_no_grupo,
)

# 1. o manifesto: o que o serviço PEDE nos grupos
app = Aplicativo(
    slug="radar", endpoint="https://radar.example/mcp", para_tipo="amigo",
    descricao="Radar de ativos", descricao_humana=None, nome_visivel="Radar",
    versao="1", conversa=(),
    superficies=(...,),  # a tela tem uma escolha com campo=CAMPO_DE_GRUPO
    grupo=CapacidadesDeGrupo(("responder_interacao", "sugerir_publicacao")),
)

# 2. a operação que o Submit chama: o grupo chega como REFERÊNCIA OPACA
def compartilhar_alerta(valores: dict) -> dict:
    ref = valores[CAMPO_DE_GRUPO]
    return {
        "texto": "Pronto — o grupo foi avisado.",        # o que a TELA mostra
        **acoes_no_grupo(
            ResponderInteracao(ref, "Alerta de HGLG11 ativo para o grupo."),
            SugerirPublicacao(
                ref, "Qual FII analisamos na próxima reunião?",
                titulo="Próxima análise",
                enquete=Enquete(("HGLG11", "KNRI11", "XPML11")),
            ),
        ),
    }
```

A resposta do okmigo à tela traz o resultado de cada ação:

```json
{"ok": true, "resultado": {"texto": "Pronto — o grupo foi avisado."},
 "acoes_no_grupo": [
   {"tipo": "responder_interacao", "estado": "executada"},
   {"tipo": "sugerir_publicacao", "estado": "executada", "rascunho": true}
 ]}
```

Sem a capacidade ativada no grupo, a mesma resposta volta assim:

```json
{"tipo": "sugerir_publicacao", "estado": "recusada", "motivo": "sem_capacidade",
 "frase": "o grupo não deu esta capacidade ao serviço"}
```

### Os tipos de publicação

| construtor | o que vira |
|---|---|
| `SugerirPublicacao(ref, corpo)` | `post` |
| `…, atividade=Atividade("2026-10-03T09:00:00-03:00", "praça")` | `atividade` — ⚠️ é publicação no feed; o compromisso é da Agenda |
| `…, enquete=Enquete(("A", "B"), resultado="apos_votar")` | `enquete` (2 a 6 opções; resultado `sempre`, `apos_votar` ou `ao_fechar`) |
| `…, tipo="material", acao=Acao("https://…", "baixar")` | `material` (o link é obrigatório) |
| `…, tipo="aviso", importante=True` | `aviso` |
| `…, tipo="convite"` | `convite` |

A `audiencia` é `membros` (padrão) ou `publico`. Quem publica para o público
continua passando pelo fluxo de revisão do grupo.

## Na tela

A fala de um serviço aparece igual na web e no app: **«✦ Radar · serviço · a
pedido de Ana»**, com «a pedido de você» para quem pediu. O painel «Serviços
do grupo», no menu do grupo, mostra a todos quais serviços agem ali. Para
quem modera, ele também tem a ativação, a fila e a trilha.

## Validar antes de registrar

`acoes_no_grupo(...)` e os construtores recusam, com `ContratoDoSdkInvalido`,
o que o okmigo recusaria: capacidade reservada ou desconhecida, texto vazio ou
longo demais, enquete sem duas opções diferentes, link sem `https://`, mais de
cinco ações, duas respostas no mesmo Submit. O `preview` (`python -m
okmigo_cartao`) confere a tela com o seletor `okmigo_grupos` como sempre.
