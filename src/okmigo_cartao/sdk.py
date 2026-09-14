"""Piloto do SDK tipado para escrever telas declaradas do OkMigo.

O SDK e uma camada de autoria: ele produz exatamente o contrato Adaptive Card
que o crivo ja aceita. Nenhum objeto daqui atravessa a fronteira em runtime e
nenhum componente permite HTML, JavaScript ou uma URL executavel.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, Self
from urllib.parse import urlsplit

Json = dict[str, Any]
_NOME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.{}-]*$")


class ContratoDoSdkInvalido(ValueError):
    """O erro de autoria que o SDK consegue detectar antes do crivo."""


def _nome(valor: str, papel: str) -> str:
    valor = valor.strip()
    if not _NOME.fullmatch(valor):
        raise ContratoDoSdkInvalido(
            f"{papel} precisa ser um identificador, recebi {valor!r}"
        )
    return valor


class Componente(Protocol):
    def compilar(self) -> Json: ...


def _compilar(componentes: Iterable[Componente]) -> list[Json]:
    return [componente.compilar() for componente in componentes]


class Tema(StrEnum):
    FINANCEIRO = "financeiro-violeta"
    JORNADA = "jornada-ativa"
    MERCADO = "mercado-editorial"
    OPERACAO = "operacao-direta"


class Navegacao(StrEnum):
    INFERIOR = "inferior"


class PapelDoTexto(StrEnum):
    TITULO = "titulo"
    SECAO = "secao"
    DESTAQUE = "destaque"
    CORPO = "corpo"
    AUXILIAR = "auxiliar"


class Alinhamento(StrEnum):
    ESQUERDA = "left"
    CENTRO = "center"
    DIREITA = "right"


class Espaco(StrEnum):
    NENHUM = "none"
    PEQUENO = "small"
    PADRAO = "default"
    MEDIO = "medium"
    GRANDE = "large"
    EXTRA_GRANDE = "extraLarge"


@dataclass(frozen=True, slots=True)
class Texto:
    texto: str
    papel: PapelDoTexto = PapelDoTexto.CORPO
    negrito: bool = False
    alinhamento: Alinhamento | None = None
    separador: bool | None = None
    espaco: Espaco | None = None

    def __post_init__(self) -> None:
        if not self.texto:
            raise ContratoDoSdkInvalido("texto nao pode ser vazio")

    def compilar(self) -> Json:
        no: Json = {"type": "TextBlock", "text": self.texto, "wrap": True}
        if self.papel == PapelDoTexto.TITULO:
            no.update(size="extraLarge", weight="bolder", spacing="none")
        elif self.papel == PapelDoTexto.SECAO:
            no.update(size="large", weight="bolder", spacing="large", separator=True)
        elif self.papel == PapelDoTexto.DESTAQUE:
            no.update(size="large", weight="bolder")
        elif self.papel == PapelDoTexto.AUXILIAR:
            no.update(size="small", isSubtle=True)
        if self.negrito:
            no["weight"] = "bolder"
        if self.alinhamento is not None:
            no["horizontalAlignment"] = self.alinhamento.value
        if self.separador is not None:
            no["separator"] = self.separador
        if self.espaco is not None:
            no["spacing"] = self.espaco.value
        return no


@dataclass(frozen=True, slots=True)
class Opcao:
    titulo: str
    valor: str

    def compilar(self) -> Json:
        if not self.titulo or not self.valor:
            raise ContratoDoSdkInvalido("opcao precisa de titulo e valor")
        return {"title": self.titulo, "value": self.valor}


@dataclass(frozen=True, slots=True)
class Busca:
    id: str
    campo: str
    rotulo: str
    placeholder: str
    sugestoes_por: str
    sugestoes_iniciais: tuple[Opcao, ...] = ()
    valor: str = ""
    obrigatoria: bool = True
    estrita: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id do campo")
        _nome(self.campo, "campo")
        _nome(self.sugestoes_por, "operacao de sugestoes")
        if not self.rotulo or not self.placeholder:
            raise ContratoDoSdkInvalido("busca precisa de rotulo e placeholder")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Input.ChoiceSet",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "placeholder": self.placeholder,
            "isRequired": self.obrigatoria,
            "style": "filtered",
            "okmigoBuscar": self.sugestoes_por,
            "choices": [opcao.compilar() for opcao in self.sugestoes_iniciais],
        }
        if self.valor:
            no["value"] = self.valor
        if self.estrita:
            no["okmigoEstrito"] = True
        return no


@dataclass(frozen=True, slots=True)
class CampoOculto:
    """Valor de contexto que uma acao pode enviar sem pedir nova digitacao."""

    id: str
    campo: str
    valor: str

    def __post_init__(self) -> None:
        _nome(self.id, "id do campo oculto")
        _nome(self.campo, "campo oculto")

    def compilar(self) -> Json:
        return {
            "type": "Input.Text",
            "id": self.id,
            "campo": self.campo,
            "value": self.valor,
            "isVisible": False,
            "okmigoSomenteLeitura": True,
        }


class TipoDeAcao(StrEnum):
    LEITURA = "leitura"
    ESCRITA = "escrita"


class EnfaseDaAcao(StrEnum):
    PADRAO = "padrao"
    PRIMARIA = "primaria"
    DESTRUTIVA = "destrutiva"
    SECUNDARIA = "secundaria"


@dataclass(frozen=True, slots=True)
class Acao:
    titulo: str
    operacao: str
    tipo: TipoDeAcao
    enfase: EnfaseDaAcao = EnfaseDaAcao.PADRAO
    icone: str | None = None

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao")
        if not self.titulo:
            raise ContratoDoSdkInvalido("acao precisa de titulo acessivel")
        if self.icone is not None and self.icone != "lixeira":
            raise ContratoDoSdkInvalido("o piloto aceita apenas o icone 'lixeira'")

    @classmethod
    def consultar(
        cls,
        titulo: str,
        operacao: str,
        *,
        enfase: EnfaseDaAcao = EnfaseDaAcao.PADRAO,
    ) -> Self:
        return cls(titulo, operacao, TipoDeAcao.LEITURA, enfase)

    @classmethod
    def escrever(
        cls,
        titulo: str,
        operacao: str,
        *,
        enfase: EnfaseDaAcao = EnfaseDaAcao.PADRAO,
        icone: str | None = None,
    ) -> Self:
        return cls(titulo, operacao, TipoDeAcao.ESCRITA, enfase, icone)

    def compilar(self) -> Json:
        no: Json = {
            "type": "Action.Execute"
            if self.tipo == TipoDeAcao.LEITURA
            else "Action.Submit",
            "title": self.titulo,
            "data": {"operacao": self.operacao},
        }
        if self.enfase == EnfaseDaAcao.PRIMARIA:
            no["style"] = "positive"
        elif self.enfase == EnfaseDaAcao.DESTRUTIVA:
            no["style"] = "destructive"
        elif self.enfase == EnfaseDaAcao.SECUNDARIA:
            no["mode"] = "secondary"
        if self.icone == "lixeira":
            no["okmigoIcone"] = "delete"
        return no


@dataclass(frozen=True, slots=True)
class Acoes:
    itens: tuple[Acao, ...]
    rodape: bool = False

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("grupo de acoes nao pode ser vazio")

    def compilar(self) -> Json:
        no: Json = {"type": "ActionSet", "actions": _compilar(self.itens)}
        if self.rodape:
            no["okmigoRodape"] = True
        return no


@dataclass(frozen=True, slots=True)
class Painel:
    itens: tuple[Componente, ...]
    destaque: bool = False
    grade: str | bool | None = None
    neutro: bool = False

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("painel nao pode ser vazio")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Container",
            "style": (
                "accent" if self.destaque else "default" if self.neutro else "emphasis"
            ),
            "items": _compilar(self.itens),
        }
        if self.grade is not None:
            if self.grade not in (True, False, "larga", "compacta", "etiquetas"):
                raise ContratoDoSdkInvalido("forma de grade desconhecida")
            no["okmigoGrade"] = self.grade
        return no


class LarguraDaArea(StrEnum):
    AUTOMATICA = "auto"
    FLEXIVEL = "stretch"


@dataclass(frozen=True, slots=True)
class Area:
    itens: tuple[Componente, ...]
    largura: LarguraDaArea = LarguraDaArea.FLEXIVEL

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("area de colunas nao pode ser vazia")

    def compilar(self) -> Json:
        return {
            "type": "Column",
            "width": self.largura.value,
            "items": _compilar(self.itens),
        }


@dataclass(frozen=True, slots=True)
class Faixa:
    areas: tuple[Area, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.areas) <= 12:
            raise ContratoDoSdkInvalido("faixa precisa ter entre 1 e 12 areas")

    def compilar(self) -> Json:
        return {"type": "ColumnSet", "columns": _compilar(self.areas)}


@dataclass(frozen=True, slots=True)
class Fato:
    titulo: str
    valor: str

    def compilar(self) -> Json:
        if not self.titulo:
            raise ContratoDoSdkInvalido("fato precisa de titulo")
        return {"title": self.titulo, "value": self.valor}


@dataclass(frozen=True, slots=True)
class Fatos:
    itens: tuple[Fato, ...]

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("conjunto de fatos nao pode ser vazio")

    def compilar(self) -> Json:
        return {"type": "FactSet", "facts": _compilar(self.itens)}


class FormaDoGrafico(StrEnum):
    BARRAS = "barras"
    LINHA = "linha"


class TomDoGrafico(StrEnum):
    POSITIVO = "positivo"
    NEGATIVO = "negativo"
    NEUTRO = "neutro"
    ATENCAO = "atencao"
    PRINCIPAL = "principal"
    SUAVE = "suave"


@dataclass(frozen=True, slots=True)
class Serie:
    rotulo: str
    tom: TomDoGrafico = TomDoGrafico.NEUTRO

    def compilar(self) -> Json:
        if not self.rotulo:
            raise ContratoDoSdkInvalido("serie precisa de rotulo")
        return {"rotulo": self.rotulo, "cor": self.tom.value}


@dataclass(frozen=True, slots=True)
class Ponto:
    rotulo: str
    valores: tuple[float | int | None, ...]

    def compilar(self) -> Json:
        if not self.valores:
            raise ContratoDoSdkInvalido("ponto precisa de pelo menos um valor")
        return {"rotulo": self.rotulo, "valores": list(self.valores)}


@dataclass(frozen=True, slots=True)
class Grafico:
    titulo: str
    series: tuple[Serie, ...]
    pontos: tuple[Ponto, ...]
    forma: FormaDoGrafico = FormaDoGrafico.BARRAS
    fallback: Texto | None = None

    def __post_init__(self) -> None:
        if not self.titulo or not 1 <= len(self.series) <= 4:
            raise ContratoDoSdkInvalido("grafico precisa de titulo e de 1 a 4 series")
        if len(self.pontos) > 24:
            raise ContratoDoSdkInvalido("grafico aceita no maximo 24 pontos")

    def compilar(self) -> Json:
        no: Json = {
            "type": "okmigoGrafico",
            "forma": self.forma.value,
            "titulo": self.titulo,
            "series": _compilar(self.series),
            "pontos": _compilar(self.pontos),
        }
        if self.fallback is not None:
            no["fallback"] = self.fallback.compilar()
        return no


@dataclass(frozen=True, slots=True)
class Autorizar:
    rotulo: str
    motivo: str
    url: str

    def __post_init__(self) -> None:
        if not self.rotulo or not self.motivo or not self.url:
            raise ContratoDoSdkInvalido("autorizacao precisa de rotulo, motivo e url")
        if "{" not in self.url:
            partes = urlsplit(self.url)
            if partes.scheme != "https" or not partes.hostname:
                raise ContratoDoSdkInvalido("autorizacao precisa apontar para https")

    def compilar(self) -> Json:
        return {
            "type": "okmigoAutorizar",
            "rotulo": self.rotulo,
            "motivo": self.motivo,
            "url": self.url,
        }


@dataclass(frozen=True, slots=True)
class Coluna:
    titulo: str
    conteudo: tuple[Componente, ...]
    largura: int = 1

    def __post_init__(self) -> None:
        if not self.titulo or not self.conteudo:
            raise ContratoDoSdkInvalido("coluna precisa de titulo e conteudo")
        if not 1 <= self.largura <= 12:
            raise ContratoDoSdkInvalido("largura da coluna precisa estar entre 1 e 12")


@dataclass(frozen=True, slots=True)
class Tabela:
    colunas: tuple[Coluna, ...]
    campos_da_linha: tuple[CampoOculto, ...] = ()
    ao_tocar: Acao | None = None
    acoes_da_linha: tuple[Acao, ...] = ()
    vazio: str = "Nada para mostrar agora."
    titulo_acoes: str = "Ações"
    largura_acoes: int = 1

    def __post_init__(self) -> None:
        if not 1 <= len(self.colunas) <= 15:
            raise ContratoDoSdkInvalido("tabela precisa ter entre 1 e 15 colunas")
        if self.ao_tocar is not None and self.ao_tocar.tipo != TipoDeAcao.LEITURA:
            raise ContratoDoSdkInvalido("tocar numa linha pode apenas consultar")
        if not 1 <= self.largura_acoes <= 12:
            raise ContratoDoSdkInvalido(
                "largura da coluna de acoes precisa estar entre 1 e 12"
            )

    @staticmethod
    def _celula(itens: Iterable[Componente]) -> Json:
        return {"type": "TableCell", "items": _compilar(itens)}

    def compilar(self) -> Json:
        cabecalho = {
            "type": "TableRow",
            "cells": [
                self._celula(
                    (Texto(coluna.titulo, PapelDoTexto.AUXILIAR, negrito=True),)
                )
                for coluna in self.colunas
            ]
            + (
                [
                    self._celula(
                        (Texto(self.titulo_acoes, PapelDoTexto.AUXILIAR, negrito=True),)
                    )
                    if self.titulo_acoes
                    else {"type": "TableCell", "items": []}
                ]
                if self.acoes_da_linha
                else []
            ),
        }
        linha: Json = {
            "type": "TableRow",
            "cells": [self._celula(coluna.conteudo) for coluna in self.colunas],
        }
        if self.ao_tocar is not None:
            linha["selectAction"] = self.ao_tocar.compilar()
        if self.acoes_da_linha:
            linha["cells"].append(
                self._celula((*self.campos_da_linha, Acoes(self.acoes_da_linha)))
            )
        elif self.campos_da_linha:
            linha["cells"][0]["items"] = [
                *_compilar(self.campos_da_linha),
                *linha["cells"][0]["items"],
            ]
        return {
            "type": "Table",
            "columns": [{"width": coluna.largura} for coluna in self.colunas]
            + ([{"width": self.largura_acoes}] if self.acoes_da_linha else []),
            "firstRowAsHeader": True,
            "showGridLines": False,
            "rows": [cabecalho, {"_repetir_lista": linha}],
            "fallback": Texto(self.vazio, PapelDoTexto.AUXILIAR).compilar(),
        }


@dataclass(frozen=True, slots=True)
class Tela:
    titulo: str
    componentes: tuple[Componente, ...]
    descricao: str | None = None
    tema: Tema | None = None
    navegacao: Navegacao | None = None
    versao: str = "1.5"
    mostrar_cabecalho: bool = True
    _cabecalho: tuple[Componente, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.titulo or not self.componentes:
            raise ContratoDoSdkInvalido("tela precisa de titulo e componentes")
        cabecalho: tuple[Componente, ...] = ()
        if self.mostrar_cabecalho:
            cabecalho = (Texto(self.titulo, PapelDoTexto.TITULO),)
        if self.descricao and self.mostrar_cabecalho:
            cabecalho += (Texto(self.descricao, PapelDoTexto.AUXILIAR),)
        object.__setattr__(self, "_cabecalho", cabecalho)

    def compilar(self) -> Json:
        cartao: Json = {
            "type": "AdaptiveCard",
            "version": self.versao,
            "body": _compilar((*self._cabecalho, *self.componentes)),
        }
        if self.tema is not None:
            cartao["okmigoTema"] = self.tema.value
        if self.navegacao is not None:
            cartao["okmigoNavegacao"] = self.navegacao.value
        return cartao

    def conferir(
        self,
        *,
        leituras: set[str] | frozenset[str] = frozenset(),
        escrituras: set[str] | frozenset[str] = frozenset(),
    ) -> Json:
        """Compila e passa pelo crivo, falhando cedo com uma mensagem útil."""
        from .crivo import validar

        normalizada, erro = validar(
            self.compilar(), leituras=leituras, escrituras=escrituras
        )
        if erro or normalizada is None:
            raise ContratoDoSdkInvalido(erro or "o crivo recusou a tela")
        return normalizada


@dataclass(frozen=True, slots=True)
class Fonte:
    operacao: str
    caminho: str | None = None

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao da fonte")
        if self.caminho is not None:
            _nome(self.caminho, "caminho da lista")

    def compilar(self) -> Json:
        fonte: Json = {"resumo": {"operacao": self.operacao}}
        if self.caminho:
            fonte["lista"] = {
                "operacao": self.operacao,
                "caminho": self.caminho,
            }
        return fonte


@dataclass(frozen=True, slots=True)
class Superficie:
    nome: str
    titulo: str
    rotulo: str
    icone: str
    hint: str
    fonte: Fonte
    tela: Tela

    def __post_init__(self) -> None:
        _nome(self.nome, "nome da superficie")
        _nome(self.icone, "icone da superficie")
        if not self.titulo or not self.rotulo or not self.hint:
            raise ContratoDoSdkInvalido(
                "superficie precisa de titulo, rotulo e explicacao"
            )

    def compilar(self) -> Json:
        return {
            "nome": self.nome,
            "titulo": self.titulo,
            "rotulo": self.rotulo,
            "icone": self.icone,
            "hint": self.hint,
            "fonte": self.fonte.compilar(),
            "cartao": self.tela.compilar(),
        }


@dataclass(frozen=True, slots=True)
class Aplicativo:
    slug: str
    endpoint: str
    para_tipo: str
    descricao: str
    descricao_humana: str
    nome_visivel: str
    versao: str
    conversa: tuple[str, ...]
    superficies: tuple[Superficie, ...]
    forma: str = "do_operador"

    def __post_init__(self) -> None:
        _nome(self.slug, "slug")
        if self.forma != "do_operador" or self.para_tipo not in {"amigo", "socio"}:
            raise ContratoDoSdkInvalido("forma ou destinatario do aplicativo invalido")
        if not self.endpoint.startswith(("http://", "https://")):
            raise ContratoDoSdkInvalido("endpoint precisa ser http ou https")
        if not self.superficies:
            raise ContratoDoSdkInvalido("aplicativo precisa de superficies")
        for operacao in self.conversa:
            _nome(operacao, "operacao de conversa")

    def compilar(self) -> Json:
        return {
            "slug": self.slug,
            "endpoint": self.endpoint,
            "forma": self.forma,
            "para_tipo": self.para_tipo,
            "descricao": self.descricao,
            "descricao_humana": self.descricao_humana,
            "nome_visivel": self.nome_visivel,
            "versao": self.versao,
            "conversa": list(self.conversa),
            "superficies": _compilar(self.superficies),
        }
