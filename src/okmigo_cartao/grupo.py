"""Ações e conteúdo com escopo de GRUPO — o contrato tipado (OMINFRA-806).

Um serviço age dentro de um grupo do okmigo sem nunca ver o grupo:

1. o manifesto DECLARA o que pede — ``CapacidadesDeGrupo`` no campo ``grupo``
   do ``Aplicativo``;
2. quem modera o grupo ATIVA o serviço e escolhe quais capacidades valem (e se
   a mensagem que ninguém pediu passa por aprovação);
3. a ação vai na RESPOSTA de uma chamada que o okmigo fez — o Submit de uma
   tela em que a pessoa escolheu o grupo pelo campo ``okmigo_grupos``. O
   okmigo confere, executa e anota; ao serviço volta só estado e motivo.

⛔ Não existe porta para o serviço escrever no grupo por conta própria, e o
grupo chega como REFERÊNCIA OPACA (``grupo``): nada de id, membro, tabela ou
texto de outra pessoa. Por isso nenhum serviço precisa conhecer a roda.

Exemplo — uma tela com o seletor de grupo e a resposta que age no grupo::

    from okmigo_cartao.grupo import (
        CapacidadesDeGrupo, EnviarMensagem, ResponderInteracao, SugerirPublicacao,
        Enquete, acoes_no_grupo, CAMPO_DE_GRUPO,
    )

    grupo = CapacidadesDeGrupo(("responder_interacao", "sugerir_publicacao"))
    # Aplicativo(..., grupo=grupo)

    def ao_enviar(valores: dict) -> dict:
        ref = valores[CAMPO_DE_GRUPO]           # o ref opaco que o okmigo preencheu
        return {
            "texto": "Enquete sugerida ao grupo.",   # o que a TELA mostra
            **acoes_no_grupo(
                ResponderInteracao(ref, "Seu alerta de HGLG11 ficou ativo."),
                SugerirPublicacao(ref, "Qual FII analisamos na próxima?",
                                  titulo="Próxima análise",
                                  enquete=Enquete(("HGLG11", "KNRI11"))),
            ),
        }

A resposta do okmigo à tela traz ``acoes_no_grupo`` com o resultado de cada
uma: ``executada``, ``pendente`` (esperando quem modera) ou ``recusada`` com o
``motivo`` (``MOTIVOS``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .sdk import ContratoDoSdkInvalido

Json = dict[str, Any]

#: o campo da escolha que o PRODUTO preenche com os grupos da pessoa
CAMPO_DE_GRUPO = "okmigo_grupos"

#: capacidade → o que faz; a matriz completa está em ``docs/GRUPOS.md``
CAPACIDADES: dict[str, str] = {
    "responder_interacao": "responde, no grupo, a quem acabou de usar o serviço (sem fila: foi pedido)",
    "enviar_mensagem": "manda uma mensagem ao grupo (na fila de quem modera, se o grupo exigir)",
    "sugerir_publicacao": "sugere uma publicação — nasce RASCUNHO; publicar é de quem publica",
}
#: ⛔ reservada: a Agenda é a fonte única de horário — o evento nasce lá
RESERVADAS = ("criar_evento",)

#: os motivos de recusa que o okmigo devolve — códigos estáveis
MOTIVOS = (
    "acao_desconhecida", "grupo_desconhecido", "servico_nao_ativado", "sem_capacidade",
    "agenda_e_a_fonte", "conteudo_invalido", "precisa_de_quem_pediu", "quem_pediu_nao_fala",
    "uma_resposta_por_interacao", "demais_acoes",
)
MAX_ACOES = 5
MAX_TEXTO = 2000


def _ref(grupo: str) -> None:
    if not isinstance(grupo, str) or not grupo.strip() or len(grupo) > 200:
        raise ContratoDoSdkInvalido("grupo é a referência opaca que o okmigo mandou no Submit")


def _texto(texto: str, teto: int, nome: str) -> None:
    if not isinstance(texto, str) or not texto.strip():
        raise ContratoDoSdkInvalido(f"{nome} não pode ser vazio")
    if len(texto) > teto:
        raise ContratoDoSdkInvalido(f"{nome} passa de {teto} caracteres")


@dataclass(frozen=True, slots=True)
class CapacidadesDeGrupo:
    """O que o serviço PEDE dentro de um grupo. Declarar não ativa: cada grupo
    escolhe. ⛔ A reservada e a desconhecida são recusadas aqui — o okmigo as
    descartaria calado no registro."""

    capacidades: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.capacidades:
            raise ContratoDoSdkInvalido("declare ao menos uma capacidade de grupo")
        for c in self.capacidades:
            if c in RESERVADAS:
                raise ContratoDoSdkInvalido(f"{c} é reservada: a Agenda é a fonte única de horário")
            if c not in CAPACIDADES:
                raise ContratoDoSdkInvalido(f"capacidade de grupo desconhecida: {c}")
        if len(set(self.capacidades)) != len(self.capacidades):
            raise ContratoDoSdkInvalido("capacidade de grupo repetida")

    def compilar(self) -> Json:
        return {"capacidades": list(self.capacidades)}


# ═══ OS DETALHES DA PUBLICAÇÃO (a forma fechada do okmigo) ════════════════

def _https(url: str) -> None:
    partes = urlsplit(url or "")
    if partes.scheme != "https" or not partes.netloc:
        raise ContratoDoSdkInvalido("o link precisa começar com https://")


@dataclass(frozen=True, slots=True)
class Acao:
    """O botão de uma publicação (``material`` exige um)."""
    url: str
    rotulo: str = "abrir"

    def __post_init__(self) -> None:
        _https(self.url)
        _texto(self.rotulo, 40, "o rótulo da ação")

    def compilar(self) -> Json:
        return {"rotulo": self.rotulo, "url": self.url}


@dataclass(frozen=True, slots=True)
class Atividade:
    """Uma atividade do grupo (encontro, mutirão). ⚠️ É publicação, não
    evento de Agenda: a hora aparece no feed; o compromisso é da Agenda."""
    quando: str
    onde: str | None = None

    def __post_init__(self) -> None:
        _texto(self.quando, 40, "quando (ISO 8601)")
        if self.onde is not None:
            _texto(self.onde, 80, "onde")

    def compilar(self) -> Json:
        return {"quando": self.quando, **({"onde": self.onde} if self.onde else {})}


@dataclass(frozen=True, slots=True)
class Enquete:
    opcoes: tuple[str, ...]
    resultado: str = "sempre"
    fecha_em: str | None = None

    def __post_init__(self) -> None:
        if len(self.opcoes) < 2 or len(set(self.opcoes)) != len(self.opcoes):
            raise ContratoDoSdkInvalido("a enquete precisa de pelo menos duas opções diferentes")
        if len(self.opcoes) > 6:
            raise ContratoDoSdkInvalido("a enquete tem no máximo seis opções")
        for o in self.opcoes:
            _texto(o, 80, "a opção da enquete")
        if self.resultado not in ("sempre", "apos_votar", "ao_fechar"):
            raise ContratoDoSdkInvalido("resultado é sempre, apos_votar ou ao_fechar")

    def compilar(self) -> Json:
        return {"opcoes": list(self.opcoes), "resultado": self.resultado,
                **({"fecha_em": self.fecha_em} if self.fecha_em else {})}


# ═══ AS AÇÕES ══════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ResponderInteracao:
    """A resposta, no grupo, a quem acabou de usar o serviço. Uma por Submit."""
    grupo: str
    texto: str

    def __post_init__(self) -> None:
        _ref(self.grupo)
        _texto(self.texto, MAX_TEXTO, "o texto")

    def compilar(self) -> Json:
        return {"tipo": "responder_interacao", "grupo": self.grupo, "texto": self.texto}


@dataclass(frozen=True, slots=True)
class EnviarMensagem:
    """Uma mensagem ao grupo. Se o grupo exige aprovação, volta ``pendente``."""
    grupo: str
    texto: str

    def __post_init__(self) -> None:
        _ref(self.grupo)
        _texto(self.texto, MAX_TEXTO, "o texto")

    def compilar(self) -> Json:
        return {"tipo": "enviar_mensagem", "grupo": self.grupo, "texto": self.texto}


@dataclass(frozen=True, slots=True)
class SugerirPublicacao:
    """Uma publicação sugerida — nasce RASCUNHO, com o serviço como autor.

    O tipo sai do que se passa: ``atividade``, ``enquete``, ``material`` (a
    ``acao`` com link), ``aviso`` (``importante``), ``convite`` ou ``post``."""
    grupo: str
    corpo: str
    titulo: str | None = None
    tipo: str = "post"
    atividade: Atividade | None = None
    enquete: Enquete | None = None
    acao: Acao | None = None
    importante: bool = False
    audiencia: str = "membros"

    def __post_init__(self) -> None:
        _ref(self.grupo)
        _texto(self.corpo, 4000, "o corpo")
        if self.titulo is not None:
            _texto(self.titulo, 140, "o título")
        if self.audiencia not in ("membros", "publico"):
            raise ContratoDoSdkInvalido("audiência é membros ou publico")
        tipo = self._tipo()
        if tipo not in ("post", "atividade", "aviso", "convite", "enquete", "material"):
            raise ContratoDoSdkInvalido(f"tipo de publicação desconhecido: {tipo}")
        if tipo == "material" and self.acao is None:
            raise ContratoDoSdkInvalido("o material precisa da ação com o link (https://)")
        if sum(x is not None for x in (self.atividade, self.enquete)) > 1:
            raise ContratoDoSdkInvalido("uma publicação é atividade OU enquete")

    def _tipo(self) -> str:
        if self.atividade is not None:
            return "atividade"
        if self.enquete is not None:
            return "enquete"
        return self.tipo

    def compilar(self) -> Json:
        detalhes: Json = {}
        if self.atividade is not None:
            detalhes |= self.atividade.compilar()
        if self.enquete is not None:
            detalhes |= self.enquete.compilar()
        if self.acao is not None:
            detalhes["acao"] = self.acao.compilar()
        if self._tipo() == "aviso":
            detalhes["importante"] = self.importante
        return {"tipo": "sugerir_publicacao", "grupo": self.grupo, "corpo": self.corpo,
                "tipo_de_publicacao": self._tipo(), "audiencia": self.audiencia,
                **({"titulo": self.titulo} if self.titulo else {}), "detalhes": detalhes}


AcaoNoGrupo = ResponderInteracao | EnviarMensagem | SugerirPublicacao


def acoes_no_grupo(*acoes: AcaoNoGrupo) -> Json:
    """O pedaço da RESPOSTA do Submit que age no grupo. ⛔ No máximo
    ``MAX_ACOES``, e uma ``ResponderInteracao`` por Submit."""
    if not acoes:
        raise ContratoDoSdkInvalido("nenhuma ação")
    if len(acoes) > MAX_ACOES:
        raise ContratoDoSdkInvalido(f"no máximo {MAX_ACOES} ações por resposta")
    if sum(isinstance(a, ResponderInteracao) for a in acoes) > 1:
        raise ContratoDoSdkInvalido("uma interação tem uma resposta")
    return {"acoes_no_grupo": [a.compilar() for a in acoes]}
