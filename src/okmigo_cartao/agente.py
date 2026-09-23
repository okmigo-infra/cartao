"""O agente de domínio: o bloco do manifesto e as respostas tipadas (contrato 1).

A decisão está na ADR 001 do okmigo (OMINFRA-762). Em uma frase: cada serviço
pode declarar um agente que entende o SEU domínio, e o MCP continua sendo a
fronteira determinística para dado e ação. **O agente fica em cima do MCP,
nunca no lugar dele.**

⭐ Dois modos, e um contrato só:

- ``declarado``: o serviço escreve instruções, vocabulário e a lista de
  ferramentas, e quem executa é o runtime do okmigo. A mensagem da pessoa não
  sai do okmigo; só os parâmetros das ferramentas atravessam, como sempre;
- ``remoto``: o serviço executa o agente atrás de UMA operação MCP
  (``operacao``). Fica previsto aqui, e só abre quando um serviço provar que
  precisa.

⛔ Sem o bloco, nada muda: o serviço segue só MCP, com a ``conversa`` de hoje.

As respostas têm quatro formas, e só quatro (``validar_resposta``):
``respondido``, ``precisa_esclarecer``, ``acao_proposta`` e ``indisponivel``.
Quem valida é o CONSUMIDOR, nos dois modos. O agente declarado também é
modelo, e modelo devolve o que quiser.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

#: As MAJORs que este pacote entende. MAJOR nova é contrato novo, e o
#: consumidor que não a conhece cai para só MCP em vez de adivinhar.
CONTRATOS = frozenset({"1"})
MODOS = frozenset({"declarado", "remoto"})

#: ⛔ O teto das instruções é o que impede a REGRA de negócio de migrar para o
#: prompt (ADR 001 §2.2): vocabulário e uso de ferramenta cabem aqui; tabela
#: de regra, não. A medir no piloto (§6.3).
MAX_INSTRUCOES = 4000
MAX_COMPETENCIAS = 6
MAX_FERRAMENTAS = 12
MAX_EXEMPLOS = 12

#: O orçamento é teto por pedido, conferido pelo runtime e não pelo modelo.
#: Os padrões são os da ADR 001 §6.3; os máximos existem para um manifesto não
#: poder pedir o turno inteiro.
MAX_CHAMADAS = 4
MAX_TOKENS = 20_000
MAX_SEGUNDOS = 30

FORMAS = ("respondido", "precisa_esclarecer", "acao_proposta", "indisponivel")

#: A lista FECHADA de códigos de `indisponivel`. Código que o consumidor não
#: conhece não tem frase de reserva, e é por isso que a lista é fechada.
CODIGOS_INDISPONIVEL = frozenset(
    {"dado_ausente", "fonte_indisponivel", "limite", "fora_do_dominio", "falha_interna"}
)

_NOME = re.compile(r"[a-z][a-z0-9_]{0,63}")


class AgenteInvalido(ValueError):
    """O bloco `agente` do manifesto não cumpre o contrato."""


class RespostaDeAgenteInvalida(ValueError):
    """A resposta do agente não é nenhuma das quatro formas do contrato."""


def _texto(valor: Any, papel: str, maximo: int) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise AgenteInvalido(f"{papel} precisa ser texto não vazio")
    valor = valor.strip()
    if len(valor) > maximo:
        raise AgenteInvalido(f"{papel} passa de {maximo} caracteres ({len(valor)})")
    return valor


def _identificador(valor: Any, papel: str) -> str:
    if not isinstance(valor, str) or not _NOME.fullmatch(valor.strip()):
        raise AgenteInvalido(f"{papel} precisa ser um identificador, recebi {valor!r}")
    return valor.strip()


@dataclass(frozen=True, slots=True)
class Orcamento:
    """O teto de UM pedido ao agente: chamadas de ferramenta, tokens e tempo."""

    chamadas: int = 3
    tokens: int = 12_000
    segundos: int = 20

    def __post_init__(self) -> None:
        for nome, valor, maximo in (
            ("chamadas", self.chamadas, MAX_CHAMADAS),
            ("tokens", self.tokens, MAX_TOKENS),
            ("segundos", self.segundos, MAX_SEGUNDOS),
        ):
            if not isinstance(valor, int) or isinstance(valor, bool) or not 1 <= valor <= maximo:
                raise AgenteInvalido(f"orçamento.{nome} vai de 1 a {maximo}, recebi {valor!r}")

    def compilar(self) -> dict[str, int]:
        return {"chamadas": self.chamadas, "tokens": self.tokens, "segundos": self.segundos}


@dataclass(frozen=True, slots=True)
class Exemplo:
    """Um pedido e a FORMA que se espera dele — é o laboratório do 767."""

    pedido: str
    espera: str

    def __post_init__(self) -> None:
        _texto(self.pedido, "exemplo.pedido", 300)
        if self.espera not in FORMAS:
            raise AgenteInvalido(f"exemplo.espera precisa ser uma de {FORMAS}, recebi {self.espera!r}")

    def compilar(self) -> dict[str, str]:
        return {"pedido": self.pedido.strip(), "espera": self.espera}


@dataclass(frozen=True, slots=True)
class AgenteDeDominio:
    """O bloco `agente` do manifesto.

    ``competencias`` é o que o AMIGO lê para decidir se delega: frases curtas
    do que o agente resolve. ``ferramentas`` são as operações MCP que o agente
    pode chamar — todas de LEITURA e todas na ``conversa``. Escrita só existe
    como ``acao_proposta``, executada pelo portão de confirmação do
    consumidor, nunca pelo agente.
    """

    competencias: tuple[str, ...]
    ferramentas: tuple[str, ...] = ()
    instrucoes: str = ""
    exemplos: tuple[Exemplo, ...] = ()
    orcamento: Orcamento = field(default_factory=Orcamento)
    modo: str = "declarado"
    contrato: str = "1"
    #: Só do modo ``remoto``: a operação MCP que recebe a entrada do contrato.
    operacao: str | None = None

    def __post_init__(self) -> None:
        if self.contrato not in CONTRATOS:
            raise AgenteInvalido(
                f"contrato {self.contrato!r} desconhecido; este pacote entende {sorted(CONTRATOS)}"
            )
        if self.modo not in MODOS:
            raise AgenteInvalido(f"modo precisa ser um de {sorted(MODOS)}, recebi {self.modo!r}")
        if not 1 <= len(self.competencias) <= MAX_COMPETENCIAS:
            raise AgenteInvalido(f"declare de 1 a {MAX_COMPETENCIAS} competências")
        for c in self.competencias:
            _texto(c, "competência", 80)
        if len(set(self.ferramentas)) != len(self.ferramentas):
            raise AgenteInvalido("ferramentas repetidas")
        if len(self.ferramentas) > MAX_FERRAMENTAS:
            raise AgenteInvalido(f"no máximo {MAX_FERRAMENTAS} ferramentas por agente")
        for f in self.ferramentas:
            _identificador(f, "ferramenta")
        if len(self.exemplos) > MAX_EXEMPLOS:
            raise AgenteInvalido(f"no máximo {MAX_EXEMPLOS} exemplos")

        if self.modo == "declarado":
            # ⛔ O agente declarado sem ferramenta só pode responder de cabeça,
            # e texto sobre o domínio sem dado do domínio é invenção (ADR §1.2).
            if not self.ferramentas:
                raise AgenteInvalido("o agente declarado precisa de ferramentas")
            _texto(self.instrucoes, "instruções", MAX_INSTRUCOES)
            if self.operacao is not None:
                raise AgenteInvalido("operacao é só do modo remoto")
        else:
            if self.operacao is None:
                raise AgenteInvalido("o modo remoto precisa declarar a operacao que recebe o pedido")
            _identificador(self.operacao, "operacao")
            if self.instrucoes:
                _texto(self.instrucoes, "instruções", MAX_INSTRUCOES)

    def conferir_conversa(self, conversa: tuple[str, ...] | None) -> None:
        """⛔ Ferramenta fora da ``conversa`` é operação escondida da conversa.

        Com ``conversa`` ausente, tudo é conversa, e a conferência de escrita
        fica com o consumidor, que é quem conhece os efeitos de cada operação.
        """
        if conversa is None:
            return
        fora = [f for f in self.ferramentas if f not in conversa]
        if self.operacao is not None and self.operacao not in conversa:
            fora.append(self.operacao)
        if fora:
            raise AgenteInvalido(
                "o agente usa operação fora da conversa: " + ", ".join(sorted(fora))
            )

    def compilar(self) -> dict[str, Any]:
        bloco: dict[str, Any] = {
            "contrato": self.contrato,
            "modo": self.modo,
            "competencias": [c.strip() for c in self.competencias],
            "ferramentas": list(self.ferramentas),
            "orcamento": self.orcamento.compilar(),
        }
        if self.instrucoes:
            bloco["instrucoes"] = self.instrucoes.strip()
        if self.exemplos:
            bloco["exemplos"] = [e.compilar() for e in self.exemplos]
        if self.operacao is not None:
            bloco["operacao"] = self.operacao
        return bloco

    @classmethod
    def de_json(cls, bruto: Any) -> AgenteDeDominio:
        """O bloco CRU, como chega do registro, validado pelas mesmas regras.

        ⭐ É o que o consumidor chama ao registrar: quem escreveu o manifesto à
        mão, sem o SDK, passa pelo mesmo crivo de quem usou as classes.
        """
        if not isinstance(bruto, Mapping):
            raise AgenteInvalido("o bloco agente precisa ser um objeto")
        conhecidas = {"contrato", "modo", "competencias", "ferramentas", "instrucoes",
                      "exemplos", "orcamento", "operacao"}
        sobra = set(bruto) - conhecidas
        if sobra:
            # ⛔ Campo desconhecido não é ignorado: ignorar é o crivo comendo em
            # silêncio, e quem escreveu acha que declarou algo que não existe.
            raise AgenteInvalido("campos desconhecidos no agente: " + ", ".join(sorted(sobra)))
        orc = bruto.get("orcamento") or {}
        if not isinstance(orc, Mapping) or set(orc) - {"chamadas", "tokens", "segundos"}:
            raise AgenteInvalido("orçamento aceita só chamadas, tokens e segundos")
        exemplos = bruto.get("exemplos") or []
        if not isinstance(exemplos, list) or not all(isinstance(e, Mapping) for e in exemplos):
            raise AgenteInvalido("exemplos precisa ser uma lista de objetos")
        for campo in ("competencias", "ferramentas"):
            if not isinstance(bruto.get(campo, []), list):
                raise AgenteInvalido(f"{campo} precisa ser uma lista")
        return cls(
            contrato=str(bruto.get("contrato", "1")),
            modo=str(bruto.get("modo", "declarado")),
            competencias=tuple(bruto.get("competencias") or ()),
            ferramentas=tuple(bruto.get("ferramentas") or ()),
            instrucoes=bruto.get("instrucoes") or "",
            exemplos=tuple(Exemplo(e.get("pedido", ""), e.get("espera", "")) for e in exemplos),
            orcamento=Orcamento(**dict(orc)),
            operacao=bruto.get("operacao"),
        )


# ── as respostas ───────────────────────────────────────────────────────────


def _exigir(resposta: Mapping[str, Any], campo: str, tipo: type, *, vazio: bool = False) -> Any:
    valor = resposta.get(campo)
    if not isinstance(valor, tipo) or (isinstance(valor, bool) and tipo is not bool):
        raise RespostaDeAgenteInvalida(f"{resposta.get('forma')}.{campo} ausente ou de tipo errado")
    if not vazio and isinstance(valor, (str, list)) and not (valor.strip() if isinstance(valor, str) else valor):
        raise RespostaDeAgenteInvalida(f"{resposta.get('forma')}.{campo} vazio")
    return valor


def validar_resposta(bruto: Any) -> dict[str, Any]:
    """A resposta do agente, conferida contra as quatro formas. Devolve cópia.

    ⛔ Forma desconhecida, campo faltando ou tipo errado LEVANTAM — e quem
    chama cai para só MCP. Não existe «quase respondido»: meia resposta
    tipada é o caminho por onde volta a invenção.
    """
    if not isinstance(bruto, Mapping):
        raise RespostaDeAgenteInvalida("a resposta precisa ser um objeto")
    r = dict(bruto)
    forma = r.get("forma")
    if forma not in FORMAS:
        raise RespostaDeAgenteInvalida(f"forma precisa ser uma de {FORMAS}, recebi {forma!r}")

    if forma == "respondido":
        _exigir(r, "texto", str)
        # ⭐ Sem data-base não há resposta de domínio: o número sem data é o
        # número que a pessoa lê como de hoje (a lacuna do `quando`, ADR §1.4).
        _exigir(r, "data_base", str)
        fatos = _exigir(r, "fatos", list, vazio=True)
        for fato in fatos:
            if not isinstance(fato, Mapping) or not isinstance(fato.get("rotulo"), str) \
                    or not isinstance(fato.get("valor"), (str, int, float)) or isinstance(fato.get("valor"), bool):
                raise RespostaDeAgenteInvalida("cada fato precisa de rotulo (texto) e valor")
        fontes = _exigir(r, "fontes", list)
        if not all(isinstance(f, str) and f.strip() for f in fontes):
            raise RespostaDeAgenteInvalida("fontes precisa ser uma lista de textos")
    elif forma == "precisa_esclarecer":
        _exigir(r, "pergunta", str)
        opcoes = _exigir(r, "opcoes", list, vazio=True)
        if not all(isinstance(o, str) and o.strip() for o in opcoes):
            raise RespostaDeAgenteInvalida("opcoes precisa ser uma lista de textos")
        # ⚠️ A continuação é opaca e ASSINADA pelo consumidor, não pelo
        # agente: aqui só se confere que ela existe quando há o que continuar.
        if "continuacao" in r and not isinstance(r["continuacao"], str):
            raise RespostaDeAgenteInvalida("continuacao precisa ser texto")
    elif forma == "acao_proposta":
        _identificador_resposta(_exigir(r, "operacao", str))
        _exigir(r, "parametros", dict, vazio=True)
        _exigir(r, "resumo", str)
        # ⛔ Não há `executado`, `confirmado` nem nada que diga que aconteceu:
        # quem executa é o portão do consumidor, no turno seguinte.
        for proibido in ("executado", "confirmado", "confirmado_pela_pessoa"):
            if proibido in r:
                raise RespostaDeAgenteInvalida(f"acao_proposta não carrega {proibido}")
    else:
        codigo = _exigir(r, "codigo", str)
        if codigo not in CODIGOS_INDISPONIVEL:
            raise RespostaDeAgenteInvalida(
                f"codigo {codigo!r} fora da lista fechada {sorted(CODIGOS_INDISPONIVEL)}"
            )
        _exigir(r, "mensagem_segura", str)
        if not isinstance(r.get("recuperavel"), bool):
            raise RespostaDeAgenteInvalida("indisponivel.recuperavel precisa ser booleano")
    return r


def _identificador_resposta(valor: str) -> None:
    if not _NOME.fullmatch(valor.strip()):
        raise RespostaDeAgenteInvalida(f"acao_proposta.operacao inválida: {valor!r}")
