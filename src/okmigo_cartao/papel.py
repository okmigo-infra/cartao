"""O PAPEL do app: o que ele é dono, com quem se fala e como a pessoa pede.

⭐ OMINFRA-1037 (épico OMINFRA-1036). O okmigo escolhe o app que atende um
pedido por um BROKER de roteamento que lê o que cada app instalado declara de
si. Medido em 08/10 (1.297 falas, catálogo real): o broker que lê só as
competências do agente acerta 769 e erra 86; lendo também as operações e as
relações entre apps, acerta 965 e erra 46 — e os erros que sobram são, quase
todos, CADASTRO que não diz o que o app faz («marque meus treinos» foi à Agenda
porque o Fitness não declarava que marca os dias).

As regras de roteamento que este bloco sustenta (decisões do Victor, 08/10):

- **O pedido vai ao DONO da coisa pedida** (``dono_de``), nunca a quem só a
  recebe ou mostra. Os apps se falam PELO okmigo, com uma fonte por número:
  ``recebe_de`` e ``entrega_para`` dizem isso, e o par tem de bater dos dois
  lados.
- **A Agenda é o padrão de todos** e recebe só o que não pertence a nenhum
  outro app instalado. Quem tem agendamento (marca horário, publica datas)
  ENTREGA para a Agenda e recebe o pedido.

⚠️ Nesta versão o cadastro fraco é AVISO (``avisos_do_cadastro``): o registro
passa e o aviso aparece. Na versão seguinte, recusa.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .agente import _NOME

MAX_DESCRICAO = 400
MAX_DONO_DE = 12
MAX_RELACOES = 12
MAX_NAO_E_MEU = 12
MAX_DEFINICOES = 24
MAX_EXEMPLOS_DE_ROTEAMENTO = 80
MAX_CEDIDAS = 40
#: O app que é o padrão de todos — quem marca horário entrega para ele.
AGENDA = "agenda"


class PapelInvalido(ValueError):
    """O bloco ``papel`` do manifesto não cumpre o contrato."""


def _texto(valor: Any, onde: str, maximo: int) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise PapelInvalido(f"{onde} precisa ser texto não vazio")
    valor = " ".join(valor.split())
    if len(valor) > maximo:
        raise PapelInvalido(f"{onde} passa de {maximo} caracteres ({len(valor)})")
    return valor


def _slug(valor: Any, onde: str) -> str:
    if not isinstance(valor, str) or not _NOME.fullmatch(valor.strip().replace("-", "_")):
        raise PapelInvalido(f"{onde} precisa ser o slug de um app, recebi {valor!r}")
    return valor.strip()


@dataclass(frozen=True, slots=True)
class Relacao:
    """Um fluxo PELO okmigo: com qual app, e o que viaja."""

    app: str
    o_que: str

    def __post_init__(self) -> None:
        _slug(self.app, "relação.app")
        _texto(self.o_que, "relação.o_que", 160)

    def compilar(self) -> dict[str, str]:
        return {"app": self.app.strip(), "o_que": " ".join(self.o_que.split())}


@dataclass(frozen=True, slots=True)
class ExemploDeRoteamento:
    """Uma fala real de quem usa e a operação da conversa que ela pede.

    ``operacao`` vazia = o pedido é deste app, mas não de uma operação só
    (uma pergunta geral sobre o domínio).
    """

    pedido: str
    operacao: str = ""

    def __post_init__(self) -> None:
        _texto(self.pedido, "exemplo.pedido", 240)
        if self.operacao and not _NOME.fullmatch(self.operacao):
            raise PapelInvalido(f"exemplo.operacao precisa ser um identificador, recebi {self.operacao!r}")

    def compilar(self) -> dict[str, str]:
        bloco = {"pedido": " ".join(self.pedido.split())}
        if self.operacao:
            bloco["operacao"] = self.operacao
        return bloco


@dataclass(frozen=True, slots=True)
class Papel:
    """O bloco ``papel`` do manifesto — lido pelo broker de roteamento.

    - ``descricao``: o que o app é, para quem não o conhece (1 a 3 frases);
    - ``dono_de``: as coisas de que ele é a FONTE («o treino», «a reserva de
      mesa», «o extrato do banco»);
    - ``recebe_de`` / ``entrega_para``: os fluxos com outros apps, pelo okmigo;
    - ``nao_e_meu``: o que parece dele e não é (e de quem é);
    - ``definicoes``: o vocabulário do app («previsto»: conta que ainda não
      aconteceu);
    - ``exemplos``: falas reais, cobrindo as operações da conversa;
    - ``cede_a_quem_marca_horario``: as operações que o app CEDE quando outro
      app instalado recebe pedidos de horário (0.29.0, OMINFRA-1064). É a
      Agenda dizendo «com o HoraOk instalado, o atendimento a clientes é dele»:
      o broker tira essas operações — e os exemplos delas — do que mostra.
    """

    descricao: str
    dono_de: tuple[str, ...]
    recebe_de: tuple[Relacao, ...] = ()
    entrega_para: tuple[Relacao, ...] = ()
    nao_e_meu: tuple[str, ...] = ()
    definicoes: Mapping[str, str] = field(default_factory=dict)
    exemplos: tuple[ExemploDeRoteamento, ...] = ()
    cede_a_quem_marca_horario: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _texto(self.descricao, "papel.descricao", MAX_DESCRICAO)
        if not 1 <= len(self.dono_de) <= MAX_DONO_DE:
            raise PapelInvalido(f"declare de 1 a {MAX_DONO_DE} coisas em dono_de")
        for d in self.dono_de:
            _texto(d, "dono_de", 100)
        for nome, rel in (("recebe_de", self.recebe_de), ("entrega_para", self.entrega_para)):
            if len(rel) > MAX_RELACOES:
                raise PapelInvalido(f"no máximo {MAX_RELACOES} relações em {nome}")
            if not all(isinstance(r, Relacao) for r in rel):
                raise PapelInvalido(f"{nome} é uma lista de Relacao")
        if len(self.nao_e_meu) > MAX_NAO_E_MEU:
            raise PapelInvalido(f"no máximo {MAX_NAO_E_MEU} itens em nao_e_meu")
        for n in self.nao_e_meu:
            _texto(n, "nao_e_meu", 160)
        if len(self.definicoes) > MAX_DEFINICOES:
            raise PapelInvalido(f"no máximo {MAX_DEFINICOES} definições")
        for termo, definicao in self.definicoes.items():
            _texto(termo, "definição (termo)", 40)
            _texto(definicao, f"definição de {termo!r}", 200)
        if len(self.exemplos) > MAX_EXEMPLOS_DE_ROTEAMENTO:
            raise PapelInvalido(f"no máximo {MAX_EXEMPLOS_DE_ROTEAMENTO} exemplos")
        if not all(isinstance(e, ExemploDeRoteamento) for e in self.exemplos):
            raise PapelInvalido("exemplos é uma lista de ExemploDeRoteamento")
        vistos = set()
        for e in self.exemplos:
            chave = " ".join(e.pedido.lower().split())
            if chave in vistos:
                raise PapelInvalido(f"exemplo repetido: {e.pedido!r}")
            vistos.add(chave)
        if len(self.cede_a_quem_marca_horario) > MAX_CEDIDAS:
            raise PapelInvalido(f"no máximo {MAX_CEDIDAS} operações em cede_a_quem_marca_horario")
        for op in self.cede_a_quem_marca_horario:
            if not isinstance(op, str) or not _NOME.fullmatch(op):
                raise PapelInvalido(f"cede_a_quem_marca_horario: {op!r} não é o nome de uma operação")
        if len(set(self.cede_a_quem_marca_horario)) != len(self.cede_a_quem_marca_horario):
            raise PapelInvalido("cede_a_quem_marca_horario tem operação repetida")

    def compilar(self) -> dict[str, Any]:
        bloco: dict[str, Any] = {
            "descricao": " ".join(self.descricao.split()),
            "dono_de": [" ".join(d.split()) for d in self.dono_de],
        }
        if self.recebe_de:
            bloco["recebe_de"] = [r.compilar() for r in self.recebe_de]
        if self.entrega_para:
            bloco["entrega_para"] = [r.compilar() for r in self.entrega_para]
        if self.nao_e_meu:
            bloco["nao_e_meu"] = [" ".join(n.split()) for n in self.nao_e_meu]
        if self.definicoes:
            bloco["definicoes"] = {k.strip(): " ".join(v.split()) for k, v in self.definicoes.items()}
        if self.exemplos:
            bloco["exemplos"] = [e.compilar() for e in self.exemplos]
        if self.cede_a_quem_marca_horario:
            bloco["cede_a_quem_marca_horario"] = list(self.cede_a_quem_marca_horario)
        return bloco

    @classmethod
    def de_json(cls, bruto: Any) -> Papel:
        """O bloco CRU, como chega do registro, pelas mesmas regras."""
        if not isinstance(bruto, Mapping):
            raise PapelInvalido("o bloco papel precisa ser um objeto")
        conhecidas = {"descricao", "dono_de", "recebe_de", "entrega_para", "nao_e_meu", "definicoes", "exemplos",
                      "cede_a_quem_marca_horario"}
        sobra = set(bruto) - conhecidas
        if sobra:
            raise PapelInvalido("campos desconhecidos no papel: " + ", ".join(sorted(sobra)))

        def lista(campo: str) -> list:
            v = bruto.get(campo) or []
            if not isinstance(v, list):
                raise PapelInvalido(f"{campo} precisa ser uma lista")
            return v

        def relacoes(campo: str) -> tuple[Relacao, ...]:
            itens = lista(campo)
            if not all(isinstance(r, Mapping) and set(r) <= {"app", "o_que"} for r in itens):
                raise PapelInvalido(f"{campo} é uma lista de {{app, o_que}}")
            return tuple(Relacao(r.get("app", ""), r.get("o_que", "")) for r in itens)

        exemplos = lista("exemplos")
        if not all(isinstance(e, Mapping) and set(e) <= {"pedido", "operacao"} for e in exemplos):
            raise PapelInvalido("exemplos é uma lista de {pedido, operacao}")
        definicoes = bruto.get("definicoes") or {}
        if not isinstance(definicoes, Mapping):
            raise PapelInvalido("definicoes precisa ser um objeto termo → definição")
        return cls(
            descricao=bruto.get("descricao", ""),
            dono_de=tuple(lista("dono_de")),
            recebe_de=relacoes("recebe_de"),
            entrega_para=relacoes("entrega_para"),
            nao_e_meu=tuple(lista("nao_e_meu")),
            definicoes=dict(definicoes),
            exemplos=tuple(ExemploDeRoteamento(e.get("pedido", ""), e.get("operacao", "") or "") for e in exemplos),
            cede_a_quem_marca_horario=tuple(lista("cede_a_quem_marca_horario")),
        )


def avisos_do_cadastro(manifesto: Mapping[str, Any]) -> list[str]:
    """O que falta no cadastro para o broker saber quando o pedido é deste app.

    ⚠️ Nesta versão: AVISOS, nunca exceção — o registro passa. Cada aviso é uma
    frase para quem mantém o app ler e consertar.
    """
    slug = str(manifesto.get("slug") or "")
    bruto = manifesto.get("papel")
    if bruto is None:
        return ["sem papel: o broker não sabe quando um pedido é deste app (OMINFRA-1037)"]
    try:
        papel = Papel.de_json(bruto)
    except PapelInvalido as erro:
        return [f"papel inválido: {erro}"]
    avisos: list[str] = []
    conversa = manifesto.get("conversa")
    if not isinstance(conversa, list):
        # ⛔ OMINFRA-1055: sem a lista `conversa` (tudo é conversa), a cobertura
        # era PULADA e o cadastro fraco passava calado. Vale a lista de
        # `operacoes` que a ponte entrega ao okmigo; sem nenhuma, avisa.
        ops = manifesto.get("operacoes")
        if isinstance(ops, list):
            conversa = [str(o.get("nome")) for o in ops if isinstance(o, Mapping) and o.get("nome")
                        and o.get("conversa", True) is not False]
        else:
            avisos.append("sem a lista conversa (nem operacoes): a cobertura dos exemplos não foi conferida")
    if isinstance(conversa, list):
        cobertas = {e.operacao for e in papel.exemplos if e.operacao}
        fora = sorted(cobertas - set(conversa))
        if fora:
            avisos.append("exemplo de operação fora da conversa: " + ", ".join(fora))
        cedidas_fora = sorted(set(papel.cede_a_quem_marca_horario) - set(conversa))
        if cedidas_fora:
            avisos.append("operação cedida fora da conversa: " + ", ".join(cedidas_fora))
        sem = [op for op in conversa if op not in cobertas]
        if sem:
            avisos.append(f"{len(sem)} operação(ões) da conversa sem exemplo: " + ", ".join(sem[:12])
                          + (" …" if len(sem) > 12 else ""))
    if slug != AGENDA and (manifesto.get("marca_horario") or manifesto.get("eventos")):
        if AGENDA not in {r.app for r in papel.entrega_para}:
            avisos.append("o app marca horário ou publica datas, e o papel não diz que entrega para a agenda")
    if slug and slug in {r.app for r in (*papel.recebe_de, *papel.entrega_para)}:
        avisos.append("o app se cita nas próprias relações")
    return avisos


def pares_que_nao_batem(manifestos: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Entre vários apps: se A diz que recebe de B, B tem de dizer que entrega
    para A (e vice-versa). Só confere pares em que os DOIS lados declaram papel."""
    papeis: dict[str, Papel] = {}
    for slug, m in manifestos.items():
        try:
            if m.get("papel") is not None:
                papeis[slug] = Papel.de_json(m["papel"])
        except PapelInvalido:
            continue
    faltas = []
    for a, p in papeis.items():
        for r in p.recebe_de:
            if r.app in papeis and a not in {x.app for x in papeis[r.app].entrega_para}:
                faltas.append(f"{a} diz que recebe de {r.app}, e {r.app} não diz que entrega para {a}")
        for r in p.entrega_para:
            if r.app in papeis and a not in {x.app for x in papeis[r.app].recebe_de}:
                faltas.append(f"{a} diz que entrega para {r.app}, e {r.app} não diz que recebe de {a}")
    return faltas
