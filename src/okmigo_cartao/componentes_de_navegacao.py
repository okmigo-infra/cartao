"""Vocabulário público para telas navegáveis e fluxos adaptativos.

Os componentes deste módulo declaram estrutura e intenção. Eles não aceitam
CSS, HTML, JavaScript, URL livre, breakpoint ou ícone arbitrário.
"""

from __future__ import annotations

from dataclasses import dataclass

from .componentes_avancados import MenuDeAcoes
from .sdk import (
    Acao,
    Componente,
    ContratoDoSdkInvalido,
    PapelDoTexto,
    Texto,
    TipoDeAcao,
    _compilar,
    _nome,
)

Json = dict[str, object]


def _texto(valor: str, papel: str) -> str:
    if not valor.strip():
        raise ContratoDoSdkInvalido(f"{papel} nao pode ser vazio")
    return valor


@dataclass(frozen=True, slots=True)
class CabecalhoDaTela:
    """Topo universal de superfície ou detalhe, na mesma ordem semântica."""

    titulo: str
    subtitulo: str = ""
    voltar: Acao | None = None
    acao_principal: Acao | None = None
    favoritar: Acao | None = None
    desfavoritar: Acao | None = None
    favorito: bool = False
    menu: MenuDeAcoes | None = None
    variante: str = "tela"

    def __post_init__(self) -> None:
        _texto(self.titulo, "titulo do cabecalho")
        if self.variante not in {"tela", "detalhe"}:
            raise ContratoDoSdkInvalido("variante do cabecalho precisa ser tela ou detalhe")
        if self.voltar is not None and self.voltar.tipo != TipoDeAcao.NAVEGACAO:
            raise ContratoDoSdkInvalido("voltar precisa ser navegacao interna tipada")
        if self.acao_principal is not None and self.acao_principal.tipo == TipoDeAcao.ESCRITA:
            raise ContratoDoSdkInvalido("acao principal nao pode ser escrita disfarçada")
        if (self.favoritar is None) != (self.desfavoritar is None):
            raise ContratoDoSdkInvalido(
                "favorito precisa declarar as acoes de marcar e desmarcar"
            )
        for acao in (self.favoritar, self.desfavoritar):
            if acao is not None and acao.tipo != TipoDeAcao.ESCRITA:
                raise ContratoDoSdkInvalido("favorito precisa gravar uma preferencia")

    def compilar(self) -> Json:
        no: Json = {
            "type": "okmigoCabecalhoDaTela",
            "titulo": self.titulo,
            "subtitulo": self.subtitulo,
            "variante": self.variante,
            "favorito": self.favorito,
            "fallback": Texto(self.titulo, PapelDoTexto.TITULO).compilar(),
        }
        opcionais = {
            "voltar": self.voltar,
            "acaoPrincipal": self.acao_principal,
            "favoritar": self.favoritar,
            "desfavoritar": self.desfavoritar,
            "menu": self.menu,
        }
        no.update({chave: valor.compilar() for chave, valor in opcionais.items() if valor})
        return no


@dataclass(frozen=True, slots=True)
class MestreDetalhe:
    """Lista e detalhe que se adaptam sem mudar o contrato do produto."""

    id: str
    lista: tuple[Componente, ...]
    detalhe: tuple[Componente, ...]
    vazio: str = "Selecione um item para ver os detalhes."
    selecionado: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id do mestre detalhe")
        if not self.lista or not self.detalhe:
            raise ContratoDoSdkInvalido("mestre detalhe precisa de lista e detalhe")
        _texto(self.vazio, "estado vazio do mestre detalhe")

    def compilar(self) -> Json:
        return {
            "type": "okmigoMestreDetalhe",
            "id": self.id,
            "lista": _compilar(self.lista),
            "detalhe": _compilar(self.detalhe),
            "vazio": self.vazio,
            "selecionado": self.selecionado,
            "fallback": {
                "type": "Container",
                "items": [*_compilar(self.lista), *_compilar(self.detalhe)],
            },
        }


@dataclass(frozen=True, slots=True)
class EtapaDoFluxo:
    nome: str
    titulo: str
    componentes: tuple[Componente, ...]
    opcional: bool = False
    voltar: Acao | None = None
    avancar: Acao | None = None

    def __post_init__(self) -> None:
        _nome(self.nome, "nome da etapa")
        _texto(self.titulo, "titulo da etapa")
        if not self.componentes:
            raise ContratoDoSdkInvalido("etapa do fluxo precisa de componentes")
        for papel, acao in (("voltar", self.voltar), ("avancar", self.avancar)):
            if acao is not None and acao.tipo != TipoDeAcao.ESCRITA:
                raise ContratoDoSdkInvalido(
                    f"{papel} do fluxo precisa confirmar a etapa no serviço"
                )

    def compilar(self) -> Json:
        no: Json = {
            "nome": self.nome,
            "titulo": self.titulo,
            "opcional": self.opcional,
            "componentes": _compilar(self.componentes),
        }
        if self.voltar is not None:
            no["voltar"] = self.voltar.compilar()
        if self.avancar is not None:
            no["avancar"] = self.avancar.compilar()
        return no


@dataclass(frozen=True, slots=True)
class Fluxo:
    """Jornada retomável com progresso e etapas declaradas."""

    id: str
    etapas: tuple[EtapaDoFluxo, ...]
    atual: str
    token_de_retomada: str = ""
    persistir: str | None = None
    cancelar: Acao | None = None

    def __post_init__(self) -> None:
        _nome(self.id, "id do fluxo")
        if not 2 <= len(self.etapas) <= 12:
            raise ContratoDoSdkInvalido("fluxo precisa ter de 2 a 12 etapas")
        nomes = [etapa.nome for etapa in self.etapas]
        if len(nomes) != len(set(nomes)):
            raise ContratoDoSdkInvalido("fluxo repete etapas")
        if self.atual not in nomes:
            raise ContratoDoSdkInvalido("etapa atual nao pertence ao fluxo")
        if self.persistir is not None:
            _nome(self.persistir, "operacao de persistencia do fluxo")
        if self.cancelar is not None and self.cancelar.tipo != TipoDeAcao.ESCRITA:
            raise ContratoDoSdkInvalido("cancelamento do fluxo precisa ser escrita confirmada")

    def compilar(self) -> Json:
        no: Json = {
            "type": "okmigoFluxo",
            "id": self.id,
            "atual": self.atual,
            "tokenDeRetomada": self.token_de_retomada,
            "etapas": _compilar(self.etapas),
            "fallback": {
                "type": "Container",
                "items": _compilar(next(e for e in self.etapas if e.nome == self.atual).componentes),
            },
        }
        if self.persistir is not None:
            no["persistir"] = self.persistir
        if self.cancelar is not None:
            no["cancelar"] = self.cancelar.compilar()
        return no
