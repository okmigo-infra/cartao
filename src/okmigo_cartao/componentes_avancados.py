"""Componentes universais que completam o vocabulário público do SDK.

Cada componente declara intenção. Aparência, plataforma e comportamento de
acessibilidade continuam pertencendo aos renderizadores do OkMigo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .componentes import (
    AlvoDeVisibilidade,
    Imagem,
)
from .sdk import (
    Acao,
    Componente,
    ContratoDoSdkInvalido,
    Opcao,
    PapelDoTexto,
    Texto,
    TipoDeAcao,
    _compilar,
    _nome,
)

Json = dict[str, object]


def _obrigatorio(valor: str, papel: str) -> str:
    if not valor.strip():
        raise ContratoDoSdkInvalido(f"{papel} nao pode ser vazio")
    return valor


class TomDaEtiqueta(StrEnum):
    NEUTRO = "neutro"
    POSITIVO = "positivo"
    ATENCAO = "atencao"
    NEGATIVO = "negativo"
    INFORMATIVO = "informativo"


@dataclass(frozen=True, slots=True)
class Etiqueta:
    texto: str
    tom: TomDaEtiqueta = TomDaEtiqueta.NEUTRO

    def __post_init__(self) -> None:
        _obrigatorio(self.texto, "texto da etiqueta")

    def compilar(self) -> Json:
        return {
            "type": "okmigoEtiqueta",
            "texto": self.texto,
            "tom": self.tom.value,
            "fallback": Texto(self.texto, PapelDoTexto.AUXILIAR).compilar(),
        }


@dataclass(frozen=True, slots=True)
class Status:
    texto: str
    tom: TomDaEtiqueta

    def __post_init__(self) -> None:
        _obrigatorio(self.texto, "texto do status")

    def compilar(self) -> Json:
        return {
            "type": "okmigoEtiqueta",
            "texto": self.texto,
            "tom": self.tom.value,
            "status": True,
            "fallback": Texto(self.texto, PapelDoTexto.AUXILIAR).compilar(),
        }


@dataclass(frozen=True, slots=True)
class MenuDeAcoes:
    itens: tuple[Componente, ...]
    rotulo: str = "Mais opções"

    def __post_init__(self) -> None:
        if not 1 <= len(self.itens) <= 10:
            raise ContratoDoSdkInvalido("menu de acoes precisa de 1 a 10 itens")
        _obrigatorio(self.rotulo, "rotulo acessivel do menu")
        if any(not item.compilar().get("type", "").startswith("Action.") for item in self.itens):
            raise ContratoDoSdkInvalido("menu aceita somente acoes")

    def compilar(self) -> Json:
        return {
            "type": "ActionSet",
            "actions": _compilar(self.itens),
            "okmigoMenu": True,
            "okmigoRotulo": self.rotulo,
        }


@dataclass(frozen=True, slots=True)
class CartaoClicavel:
    itens: tuple[Componente, ...]
    ao_tocar: Acao
    destaque: bool = False
    campos: tuple[Componente, ...] = ()
    menu: MenuDeAcoes | None = None

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("cartao clicavel precisa de conteudo")
        if self.ao_tocar.tipo != TipoDeAcao.LEITURA:
            raise ContratoDoSdkInvalido("tocar no cartao pode apenas consultar")

    def compilar(self) -> Json:
        itens = (*self.campos, *self.itens)
        if self.menu is not None:
            itens += (self.menu,)
        return {
            "type": "Container",
            "style": "accent" if self.destaque else "emphasis",
            "items": _compilar(itens),
            "selectAction": self.ao_tocar.compilar(),
        }


@dataclass(frozen=True, slots=True)
class Aba:
    id: str
    titulo: str
    conteudo: tuple[Componente, ...]

    def __post_init__(self) -> None:
        _nome(self.id, "id da aba")
        _obrigatorio(self.titulo, "titulo da aba")
        if not self.conteudo:
            raise ContratoDoSdkInvalido("aba precisa de conteudo")


@dataclass(frozen=True, slots=True)
class Abas:
    itens: tuple[Aba, ...]
    ativa: int = 0

    def __post_init__(self) -> None:
        if not 2 <= len(self.itens) <= 5:
            raise ContratoDoSdkInvalido("abas precisam de 2 a 5 opcoes")
        if not 0 <= self.ativa < len(self.itens):
            raise ContratoDoSdkInvalido("aba ativa fora da lista")
        if len({aba.id for aba in self.itens}) != len(self.itens):
            raise ContratoDoSdkInvalido("ids de abas precisam ser unicos")

    def compilar(self) -> Json:
        botoes = []
        paineis = []
        for indice, aba in enumerate(self.itens):
            botoes.append(
                {
                    "type": "Action.ToggleVisibility",
                    "title": aba.titulo,
                    "targetElements": [
                        {"elementId": alvo.id, "isVisible": alvo.id == aba.id}
                        for alvo in self.itens
                    ],
                }
            )
            paineis.append(
                {
                    "type": "Container",
                    "id": aba.id,
                    "isVisible": indice == self.ativa,
                    "items": _compilar(aba.conteudo),
                }
            )
        return {
            "type": "Container",
            "items": [
                {
                    "type": "ActionSet",
                    "actions": botoes,
                    "okmigoSegmentado": True,
                },
                *paineis,
            ],
        }


@dataclass(frozen=True, slots=True)
class FiltroSegmentado(Abas):
    """Abas locais usadas para filtrar conteúdo já presente no cartão."""


@dataclass(frozen=True, slots=True)
class Expansivel:
    id: str
    titulo: str
    conteudo: tuple[Componente, ...]
    aberto: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id do expansivel")
        _obrigatorio(self.titulo, "titulo do expansivel")
        if not self.conteudo:
            raise ContratoDoSdkInvalido("expansivel precisa de conteudo")

    def compilar(self) -> Json:
        return {
            "type": "Container",
            "items": [
                {
                    "type": "ActionSet",
                    "actions": [
                        {
                            "type": "Action.ToggleVisibility",
                            "title": self.titulo,
                            "targetElements": [self.id],
                        }
                    ],
                    "okmigoExpansivel": True,
                },
                {
                    "type": "Container",
                    "id": self.id,
                    "isVisible": self.aberto,
                    "items": _compilar(self.conteudo),
                },
            ],
        }


@dataclass(frozen=True, slots=True)
class Dialogo:
    id: str
    titulo: str
    conteudo: tuple[Componente, ...]
    visivel: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id do dialogo")
        _obrigatorio(self.titulo, "titulo do dialogo")
        if not self.conteudo:
            raise ContratoDoSdkInvalido("dialogo precisa de conteudo")

    def compilar(self) -> Json:
        return {
            "type": "Container",
            "id": self.id,
            "isVisible": self.visivel,
            "okmigoSobreposto": True,
            "items": [
                Texto(self.titulo, PapelDoTexto.SECAO).compilar(),
                *_compilar(self.conteudo),
            ],
        }


@dataclass(frozen=True, slots=True)
class CelulaDeTabela:
    itens: tuple[Componente, ...] = ()

    def compilar(self) -> Json:
        return {"type": "TableCell", "items": _compilar(self.itens)}


@dataclass(frozen=True, slots=True)
class LinhaDeTabela:
    celulas: tuple[CelulaDeTabela, ...]
    ao_tocar: Acao | None = None

    def __post_init__(self) -> None:
        if not self.celulas:
            raise ContratoDoSdkInvalido("linha precisa de celulas")
        if self.ao_tocar is not None and self.ao_tocar.tipo != TipoDeAcao.LEITURA:
            raise ContratoDoSdkInvalido("tocar numa linha pode apenas consultar")

    def compilar(self) -> Json:
        no: Json = {"type": "TableRow", "cells": _compilar(self.celulas)}
        if self.ao_tocar is not None:
            no["selectAction"] = self.ao_tocar.compilar()
        return no


@dataclass(frozen=True, slots=True)
class TabelaFlexivel:
    larguras: tuple[int, ...]
    linhas: tuple[Componente, ...]
    cabecalho: bool | None = True
    grade: bool | None = False
    vazio: str | None = "Nada para mostrar agora."
    alternativa: Componente | None = None

    def __post_init__(self) -> None:
        if not self.larguras or len(self.larguras) > 16:
            raise ContratoDoSdkInvalido("tabela precisa de 1 a 16 colunas")
        if any(largura < 1 for largura in self.larguras):
            raise ContratoDoSdkInvalido("larguras da tabela precisam ser positivas")
        if not 1 <= len(self.linhas) <= 200:
            raise ContratoDoSdkInvalido("tabela precisa de 1 a 200 linhas")

    def compilar(self) -> Json:
        tabela: Json = {
            "type": "Table",
            "columns": [{"width": largura} for largura in self.larguras],
            "rows": _compilar(self.linhas),
        }
        if self.cabecalho is not None:
            tabela["firstRowAsHeader"] = self.cabecalho
        if self.grade is not None:
            tabela["showGridLines"] = self.grade
        if self.alternativa is not None:
            tabela["fallback"] = self.alternativa.compilar()
        elif self.vazio is not None:
            tabela["fallback"] = Texto(self.vazio, PapelDoTexto.AUXILIAR).compilar()
        return tabela


class FormaDaEscolhaMultipla(StrEnum):
    LISTA = "compact"
    CARTOES = "expanded"


@dataclass(frozen=True, slots=True)
class EscolhaMultipla:
    id: str
    campo: str
    rotulo: str
    opcoes: tuple[Opcao, ...]
    valores: tuple[str, ...] = ()
    forma: FormaDaEscolhaMultipla = FormaDaEscolhaMultipla.LISTA
    obrigatoria: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id da escolha multipla")
        _nome(self.campo, "campo da escolha multipla")
        _obrigatorio(self.rotulo, "rotulo da escolha multipla")
        if not 1 <= len(self.opcoes) <= 60:
            raise ContratoDoSdkInvalido("escolha multipla precisa de 1 a 60 opcoes")
        validos = {opcao.valor for opcao in self.opcoes}
        if len(validos) != len(self.opcoes) or any(valor not in validos for valor in self.valores):
            raise ContratoDoSdkInvalido("opcoes e valores da escolha precisam ser unicos e validos")

    def compilar(self) -> Json:
        return {
            "type": "Input.ChoiceSet",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "choices": _compilar(self.opcoes),
            "value": ",".join(self.valores),
            "style": self.forma.value,
            "isRequired": self.obrigatoria,
            "isMultiSelect": True,
        }


@dataclass(frozen=True, slots=True)
class RegraAoAlterar:
    valor: str
    alvos: tuple[AlvoDeVisibilidade, ...]

    def __post_init__(self) -> None:
        _obrigatorio(self.valor, "valor da regra")
        if not self.alvos or any(alvo.mostrar is None for alvo in self.alvos):
            raise ContratoDoSdkInvalido("regra ao alterar exige alvos com estado")

    def compilar(self) -> Json:
        return {
            "valor": self.valor,
            "alvos": [alvo.compilar() for alvo in self.alvos],
        }


@dataclass(frozen=True, slots=True)
class EscolhaCondicional:
    id: str
    campo: str
    rotulo: str
    opcoes: tuple[Opcao, ...]
    regras: tuple[RegraAoAlterar, ...]
    valor: str = ""
    obrigatoria: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id da escolha condicional")
        _nome(self.campo, "campo da escolha condicional")
        _obrigatorio(self.rotulo, "rotulo da escolha condicional")
        if not self.opcoes or not self.regras or len(self.opcoes) > 60 or len(self.regras) > 60:
            raise ContratoDoSdkInvalido("escolha condicional precisa de opcoes e regras")
        validos = {opcao.valor for opcao in self.opcoes}
        if any(regra.valor not in validos for regra in self.regras):
            raise ContratoDoSdkInvalido("regra condicional precisa apontar para uma opcao")

    def compilar(self) -> Json:
        return {
            "type": "Input.ChoiceSet",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "choices": _compilar(self.opcoes),
            "value": self.valor,
            "isRequired": self.obrigatoria,
            "okmigoAoAlterar": _compilar(self.regras),
        }


class FormatoDoCampo(StrEnum):
    DATA = "data"
    HORA = "hora"
    MES = "mes"
    MOEDA = "moeda"
    DOCUMENTO = "documento"
    TELEFONE = "telefone"
    URL = "url"
    ETIQUETAS = "etiquetas"
    UNIDADE = "unidade"


@dataclass(frozen=True, slots=True)
class CampoFormatado:
    id: str
    campo: str
    rotulo: str
    formato: FormatoDoCampo
    placeholder: str = ""
    valor: str | int | float = ""
    obrigatorio: bool = False
    unidade: str = ""
    moeda: str = "BRL"

    def __post_init__(self) -> None:
        _nome(self.id, "id do campo formatado")
        _nome(self.campo, "campo formatado")
        _obrigatorio(self.rotulo, "rotulo do campo formatado")
        if self.formato == FormatoDoCampo.UNIDADE:
            _obrigatorio(self.unidade, "unidade do campo")
        if self.formato == FormatoDoCampo.MOEDA and len(self.moeda) != 3:
            raise ContratoDoSdkInvalido("moeda precisa usar codigo ISO de tres letras")

    def compilar(self) -> Json:
        numerico = self.formato in {FormatoDoCampo.MOEDA, FormatoDoCampo.UNIDADE}
        no: Json = {
            "type": "Input.Number" if numerico else "Input.Text",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "placeholder": self.placeholder,
            "value": self.valor,
            "isRequired": self.obrigatorio,
            "okmigoFormato": self.formato.value,
        }
        if self.unidade:
            no["okmigoUnidade"] = self.unidade
        if self.formato == FormatoDoCampo.MOEDA:
            no["okmigoMoeda"] = self.moeda.upper()
        return no


@dataclass(frozen=True, slots=True)
class CampoData(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.DATA, init=False)


@dataclass(frozen=True, slots=True)
class CampoHora(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.HORA, init=False)


@dataclass(frozen=True, slots=True)
class CampoMes(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.MES, init=False)


@dataclass(frozen=True, slots=True)
class CampoMoeda(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.MOEDA, init=False)


@dataclass(frozen=True, slots=True)
class CampoDocumento(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.DOCUMENTO, init=False)


@dataclass(frozen=True, slots=True)
class CampoTelefone(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.TELEFONE, init=False)


@dataclass(frozen=True, slots=True)
class CampoUrl(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.URL, init=False)


@dataclass(frozen=True, slots=True)
class CampoEtiquetas(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.ETIQUETAS, init=False)


@dataclass(frozen=True, slots=True)
class CampoComUnidade(CampoFormatado):
    formato: FormatoDoCampo = field(default=FormatoDoCampo.UNIDADE, init=False)


@dataclass(frozen=True, slots=True)
class SeletorDeQuantidade:
    id: str
    campo: str
    rotulo: str
    valor: int | float = 1
    minimo: int | float = 0
    maximo: int | float = 999
    passo: int | float = 1
    unidade: str = ""

    def __post_init__(self) -> None:
        _nome(self.id, "id do seletor")
        _nome(self.campo, "campo do seletor")
        _obrigatorio(self.rotulo, "rotulo do seletor")
        if self.minimo > self.maximo or self.passo <= 0:
            raise ContratoDoSdkInvalido("limites ou passo do seletor invalidos")

    def compilar(self) -> Json:
        return {
            "type": "Input.Number",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "value": self.valor,
            "min": self.minimo,
            "max": self.maximo,
            "okmigoControle": "quantidade",
            "okmigoPasso": self.passo,
            "okmigoUnidade": self.unidade,
        }


@dataclass(frozen=True, slots=True)
class Alternancia:
    id: str
    campo: str
    rotulo: str
    ligada: bool = False
    texto_ligada: str = "Ligado"
    texto_desligada: str = "Desligado"

    def __post_init__(self) -> None:
        _nome(self.id, "id da alternancia")
        _nome(self.campo, "campo da alternancia")
        _obrigatorio(self.rotulo, "rotulo da alternancia")
        _obrigatorio(self.texto_ligada, "texto da alternancia ligada")
        _obrigatorio(self.texto_desligada, "texto da alternancia desligada")

    def compilar(self) -> Json:
        return {
            "type": "Input.ChoiceSet",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "value": "true" if self.ligada else "false",
            "choices": [
                {"title": self.texto_ligada, "value": "true"},
                {"title": self.texto_desligada, "value": "false"},
            ],
            "okmigoControle": "alternancia",
        }


@dataclass(frozen=True, slots=True)
class GaleriaDeImagens:
    imagens: tuple[Imagem, ...]
    rotulo: str = "Galeria de imagens"

    def __post_init__(self) -> None:
        if not 1 <= len(self.imagens) <= 12:
            raise ContratoDoSdkInvalido("galeria precisa de 1 a 12 imagens")
        _obrigatorio(self.rotulo, "rotulo da galeria")

    def compilar(self) -> Json:
        return {
            "type": "okmigoGaleria",
            "rotulo": self.rotulo,
            "imagens": _compilar(self.imagens),
            "fallback": self.imagens[0].compilar(),
        }


class EstadoDaEtapa(StrEnum):
    CONCLUIDA = "concluida"
    ATUAL = "atual"
    FUTURA = "futura"
    ERRO = "erro"


@dataclass(frozen=True, slots=True)
class EtapaDaLinhaDoTempo:
    titulo: str
    detalhe: str = ""
    estado: EstadoDaEtapa = EstadoDaEtapa.FUTURA

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo da etapa")

    def compilar(self) -> Json:
        return {
            "titulo": self.titulo,
            "detalhe": self.detalhe,
            "estado": self.estado.value,
        }


@dataclass(frozen=True, slots=True)
class LinhaDoTempo:
    etapas: tuple[EtapaDaLinhaDoTempo, ...]
    rotulo: str = "Andamento"

    def __post_init__(self) -> None:
        if not 1 <= len(self.etapas) <= 24:
            raise ContratoDoSdkInvalido("linha do tempo precisa de 1 a 24 etapas")
        _obrigatorio(self.rotulo, "rotulo da linha do tempo")

    def compilar(self) -> Json:
        return {
            "type": "okmigoLinhaDoTempo",
            "rotulo": self.rotulo,
            "etapas": _compilar(self.etapas),
            "fallback": Texto(
                " · ".join(etapa.titulo for etapa in self.etapas),
                PapelDoTexto.AUXILIAR,
            ).compilar(),
        }


@dataclass(frozen=True, slots=True)
class BarraDeValor:
    rotulo: str
    valor: int | float | str
    de: int | float | str
    texto: str = ""
    tom: TomDaEtiqueta = TomDaEtiqueta.NEUTRO

    def __post_init__(self) -> None:
        _obrigatorio(self.rotulo, "rotulo da barra")

    def compilar(self) -> Json:
        return {
            "type": "okmigoBarraDeValor",
            "rotulo": self.rotulo,
            "valor": self.valor,
            "de": self.de,
            "texto": self.texto,
            "tom": self.tom.value,
            "fallback": Texto(
                self.texto or f"{self.rotulo}: {self.valor} de {self.de}"
            ).compilar(),
        }


@dataclass(frozen=True, slots=True)
class Paginacao:
    cursor: str
    campo: str = "cursor"
    anterior: Acao | None = None
    proxima: Acao | None = None

    def __post_init__(self) -> None:
        _nome(self.campo, "campo do cursor")
        if self.anterior is None and self.proxima is None:
            raise ContratoDoSdkInvalido("paginacao precisa de uma direcao")
        for acao in (self.anterior, self.proxima):
            if acao is not None and acao.tipo != TipoDeAcao.LEITURA:
                raise ContratoDoSdkInvalido("paginacao pode apenas consultar")

    def compilar(self) -> Json:
        acoes = tuple(acao for acao in (self.anterior, self.proxima) if acao is not None)
        return {
            "type": "Container",
            "items": [
                {
                    "type": "Input.Text",
                    "id": f"paginacao_{self.campo}",
                    "campo": self.campo,
                    "value": self.cursor,
                    "isVisible": False,
                    "okmigoSomenteLeitura": True,
                },
                {
                    "type": "ActionSet",
                    "actions": _compilar(acoes),
                    "okmigoSegmentado": True,
                },
            ],
        }
