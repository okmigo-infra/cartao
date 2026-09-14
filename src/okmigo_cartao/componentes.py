"""Catálogo amplo de autoria sobre o vocabulário fechado do OkMigo.

As classes deste módulo não criam uma segunda linguagem de tela. Cada uma
compila para um nó que o crivo já conhece ou para uma composição desses nós.
O JSON continua sem HTML, JavaScript, CSS ou URL de ação.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .sdk import (
    Acao,
    Acoes,
    Componente,
    ContratoDoSdkInvalido,
    EnfaseDaAcao,
    Fato,
    Fatos,
    Painel,
    PapelDoTexto,
    Texto,
    _compilar,
    _nome,
)

Json = dict[str, Any]
Escalar = str | int | float | bool


def _obrigatorio(valor: str, papel: str) -> str:
    if not valor.strip():
        raise ContratoDoSdkInvalido(f"{papel} nao pode ser vazio")
    return valor


class FormaDaEscolha(StrEnum):
    LISTA = "compact"
    CARTOES = "expanded"
    BUSCA = "filtered"


@dataclass(frozen=True, slots=True)
class CampoTexto:
    id: str
    campo: str
    rotulo: str
    placeholder: str = ""
    valor: str = ""
    obrigatorio: bool = False
    varias_linhas: bool = False
    maximo_de_caracteres: int | None = None
    somente_leitura: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id do campo")
        _nome(self.campo, "campo")
        _obrigatorio(self.rotulo, "rotulo do campo")
        if self.maximo_de_caracteres is not None and self.maximo_de_caracteres < 1:
            raise ContratoDoSdkInvalido("maximo de caracteres precisa ser positivo")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Input.Text",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "isRequired": self.obrigatorio,
            "isMultiline": self.varias_linhas,
        }
        if self.placeholder:
            no["placeholder"] = self.placeholder
        if self.valor:
            no["value"] = self.valor
        if self.maximo_de_caracteres is not None:
            no["maxLength"] = self.maximo_de_caracteres
        if self.somente_leitura:
            no["okmigoSomenteLeitura"] = True
        return no


@dataclass(frozen=True, slots=True)
class CampoNumero:
    id: str
    campo: str
    rotulo: str
    placeholder: str = ""
    valor: str | int | float | None = None
    obrigatorio: bool = False
    minimo: int | float | None = None
    maximo: int | float | None = None
    somente_leitura: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id do campo")
        _nome(self.campo, "campo")
        _obrigatorio(self.rotulo, "rotulo do campo")
        if self.minimo is not None and self.maximo is not None:
            if self.minimo > self.maximo:
                raise ContratoDoSdkInvalido("minimo nao pode ser maior que maximo")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Input.Number",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "isRequired": self.obrigatorio,
        }
        if self.placeholder:
            no["placeholder"] = self.placeholder
        if self.valor is not None:
            no["value"] = self.valor
        if self.minimo is not None:
            no["min"] = self.minimo
        if self.maximo is not None:
            no["max"] = self.maximo
        if self.somente_leitura:
            no["okmigoSomenteLeitura"] = True
        return no


@dataclass(frozen=True, slots=True)
class Escolha:
    id: str
    campo: str
    rotulo: str
    opcoes: tuple[Componente, ...] = ()
    forma: FormaDaEscolha = FormaDaEscolha.LISTA
    placeholder: str = ""
    valor: str = ""
    obrigatoria: bool = False
    quem_opera: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id da escolha")
        _nome(self.campo, "campo")
        _obrigatorio(self.rotulo, "rotulo da escolha")
        if not self.opcoes and not self.quem_opera:
            raise ContratoDoSdkInvalido("escolha precisa de opcoes")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Input.ChoiceSet",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "choices": _compilar(self.opcoes),
            "isRequired": self.obrigatoria,
        }
        if self.forma != FormaDaEscolha.LISTA:
            no["style"] = self.forma.value
        if self.forma == FormaDaEscolha.BUSCA:
            no["okmigoEstrito"] = True
        if self.placeholder:
            no["placeholder"] = self.placeholder
        if self.valor:
            no["value"] = self.valor
        if self.quem_opera:
            no["okmigoQuemOpera"] = True
        return no


class AlturaDaImagem(StrEnum):
    PEQUENA = "small"
    MEDIA = "medium"
    GRANDE = "large"
    DISPONIVEL = "stretch"


@dataclass(frozen=True, slots=True)
class Imagem:
    url: str
    descricao: str
    altura: AlturaDaImagem = AlturaDaImagem.MEDIA
    alternativa: Componente | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.url, "url da imagem")
        _obrigatorio(self.descricao, "descricao acessivel da imagem")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Image",
            "url": self.url,
            "altText": self.descricao,
            "height": self.altura.value,
        }
        if self.alternativa is not None:
            no["fallback"] = self.alternativa.compilar()
        return no


class FormatoDeArquivo(StrEnum):
    PDF = "pdf"
    IMAGEM = "imagem"
    XML = "xml"
    PLANILHA = "planilha"
    TEXTO = "texto"


@dataclass(frozen=True, slots=True)
class Arquivo:
    id: str
    campo: str
    rotulo: str
    aceita: tuple[FormatoDeArquivo, ...] = ()
    maximo_de_bytes: int | None = None
    obrigatorio: bool = False

    def __post_init__(self) -> None:
        _nome(self.id, "id do arquivo")
        _nome(self.campo, "campo")
        _obrigatorio(self.rotulo, "rotulo do arquivo")
        if self.maximo_de_bytes is not None and self.maximo_de_bytes < 1:
            raise ContratoDoSdkInvalido("maximo de bytes precisa ser positivo")

    def compilar(self) -> Json:
        no: Json = {
            "type": "okmigoArquivo",
            "id": self.id,
            "campo": self.campo,
            "label": self.rotulo,
            "aceita": [formato.value for formato in self.aceita],
            "isRequired": self.obrigatorio,
        }
        if self.maximo_de_bytes is not None:
            no["maxBytes"] = self.maximo_de_bytes
        return no


@dataclass(frozen=True, slots=True)
class Documento:
    titulo: str
    nome: str
    tipo_mime: str
    operacao_de_leitura: str
    pedido: Mapping[str, Escalar]
    tamanho: str | int | float | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo or self.nome, "titulo do documento")
        _nome(self.operacao_de_leitura, "operacao de leitura do documento")
        for chave, valor in self.pedido.items():
            _nome(chave, "campo do pedido do documento")
            if not isinstance(valor, (str, int, float, bool)):
                raise ContratoDoSdkInvalido("pedido do documento aceita apenas escalares")

    def compilar(self) -> Json:
        no: Json = {
            "type": "okmigoDocumento",
            "titulo": self.titulo,
            "nome": self.nome,
            "tipo": self.tipo_mime,
            "ler": {
                "operacao": self.operacao_de_leitura,
                "pedido": dict(self.pedido),
            },
        }
        if self.tamanho is not None:
            no["tamanho"] = self.tamanho
        return no


@dataclass(frozen=True, slots=True)
class Copiar:
    rotulo: str
    valor: str

    def __post_init__(self) -> None:
        _obrigatorio(self.rotulo, "rotulo de copiar")
        _obrigatorio(self.valor, "valor de copiar")

    def compilar(self) -> Json:
        return {"type": "okmigoCopiar", "rotulo": self.rotulo, "valor": self.valor}


@dataclass(frozen=True, slots=True)
class Cronometro:
    rotulo: str
    segundos: int

    def __post_init__(self) -> None:
        _obrigatorio(self.rotulo, "rotulo do cronometro")
        if not 1 <= self.segundos <= 3600:
            raise ContratoDoSdkInvalido("cronometro precisa ter de 1 a 3600 segundos")

    def compilar(self) -> Json:
        return {
            "type": "okmigoCronometro",
            "rotulo": self.rotulo,
            "segundos": self.segundos,
            "fallback": Texto(f"{self.rotulo}: {self.segundos} s").compilar(),
        }


class TomFinanceiro(StrEnum):
    PRINCIPAL = "principal"
    SUAVE = "suave"
    VIOLETA = "violeta"
    VERDE = "verde"
    LARANJA = "laranja"
    VERMELHO = "vermelho"
    AZUL = "azul"
    ESCURO = "escuro"
    CINZA = "cinza"


@dataclass(frozen=True, slots=True)
class Progresso:
    feito: int | float | str
    de: int | float | str
    rotulo: str = ""
    tom: TomFinanceiro | None = None

    def compilar(self) -> Json:
        no: Json = {
            "type": "okmigoProgresso",
            "feito": self.feito,
            "de": self.de,
            "fallback": Texto(
                f"{self.rotulo}: {self.feito} de {self.de}".strip(": ")
            ).compilar(),
        }
        if self.rotulo:
            no["rotulo"] = self.rotulo
        if self.tom is not None:
            no["tom"] = self.tom.value
        return no


@dataclass(frozen=True, slots=True)
class AlvoDeVisibilidade:
    id: str
    mostrar: bool | None = None

    def __post_init__(self) -> None:
        _nome(self.id, "id do alvo")

    def compilar(self) -> str | Json:
        if self.mostrar is None:
            return self.id
        return {"elementId": self.id, "isVisible": self.mostrar}


@dataclass(frozen=True, slots=True)
class Alternar:
    titulo: str
    alvos: tuple[AlvoDeVisibilidade, ...]
    enfase: EnfaseDaAcao = EnfaseDaAcao.PADRAO

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo da acao")
        if not self.alvos:
            raise ContratoDoSdkInvalido("alternar precisa de pelo menos um alvo")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Action.ToggleVisibility",
            "title": self.titulo,
            "targetElements": [alvo.compilar() for alvo in self.alvos],
        }
        if self.enfase == EnfaseDaAcao.PRIMARIA:
            no["style"] = "positive"
        elif self.enfase == EnfaseDaAcao.DESTRUTIVA:
            no["style"] = "destructive"
        elif self.enfase == EnfaseDaAcao.SECUNDARIA:
            no["mode"] = "secondary"
        return no


@dataclass(frozen=True, slots=True)
class EnviarEAvancar:
    titulo: str
    operacao: str
    alvos_apos_enviar: tuple[AlvoDeVisibilidade, ...]
    enfase: EnfaseDaAcao = EnfaseDaAcao.PRIMARIA

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo da acao")
        _nome(self.operacao, "operacao")
        if not self.alvos_apos_enviar:
            raise ContratoDoSdkInvalido("transicao precisa de alvos")
        if any(alvo.mostrar is None for alvo in self.alvos_apos_enviar):
            raise ContratoDoSdkInvalido(
                "transicao apos envio exige mostrar verdadeiro ou falso"
            )

    def compilar(self) -> Json:
        no = Acao.escrever(self.titulo, self.operacao, enfase=self.enfase).compilar()
        no["okmigoAposEnviar"] = {
            "type": "Action.ToggleVisibility",
            "targetElements": [alvo.compilar() for alvo in self.alvos_apos_enviar],
        }
        return no


class TomDaSecao(StrEnum):
    PADRAO = "default"
    ENFASE = "emphasis"
    ACENTO = "accent"
    POSITIVO = "good"
    ATENCAO = "attention"
    ALERTA = "warning"


class AlturaDaSecao(StrEnum):
    BAIXA = "48px"
    MEDIA = "96px"
    ALTA = "160px"


@dataclass(frozen=True, slots=True)
class Secao:
    itens: tuple[Componente, ...]
    id: str | None = None
    visivel: bool = True
    tom: TomDaSecao = TomDaSecao.PADRAO
    grade: str | bool | None = None
    altura: AlturaDaSecao | None = None
    sobreposta: bool = False
    ao_tocar: tuple[AlvoDeVisibilidade, ...] = ()

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("secao nao pode ser vazia")
        if self.id is not None:
            _nome(self.id, "id da secao")
        if self.grade not in (None, True, False, "larga", "compacta", "etiquetas"):
            raise ContratoDoSdkInvalido("forma de grade desconhecida")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Container",
            "style": self.tom.value,
            "items": _compilar(self.itens),
        }
        if self.id is not None:
            no["id"] = self.id
        if not self.visivel:
            no["isVisible"] = False
        if self.grade is not None:
            no["okmigoGrade"] = self.grade
        if self.altura is not None:
            no["minHeight"] = self.altura.value
        if self.sobreposta:
            no["okmigoSobreposto"] = True
        if self.ao_tocar:
            no["selectAction"] = {
                "type": "Action.ToggleVisibility",
                "targetElements": [alvo.compilar() for alvo in self.ao_tocar],
            }
        return no


@dataclass(frozen=True, slots=True)
class ComAlternativa:
    principal: Componente
    alternativa: Componente

    def compilar(self) -> Json:
        no = deepcopy(self.principal.compilar())
        no["fallback"] = self.alternativa.compilar()
        return no


@dataclass(frozen=True, slots=True)
class Condicao:
    campo: str
    em: tuple[Escalar, ...]

    def __post_init__(self) -> None:
        _nome(self.campo, "campo da condicao")
        if not self.em:
            raise ContratoDoSdkInvalido("condicao precisa de valores")

    def compilar(self) -> Json:
        return {"campo": self.campo, "em": list(self.em)}


@dataclass(frozen=True, slots=True)
class Repetir:
    modelo: Componente
    de: str | None = None
    quando: Condicao | None = None

    def __post_init__(self) -> None:
        if self.de is not None:
            _nome(self.de, "lista aninhada")

    def compilar(self) -> Json:
        no: Json = {"_repetir_lista": self.modelo.compilar()}
        if self.de is not None:
            no["_de"] = self.de
        if self.quando is not None:
            no["_quando"] = self.quando.compilar()
        return no


class VistaDoCalendario(StrEnum):
    MES = "mes"
    SEMANA = "semana"
    DIA = "dia"


class TipoDeEvento(StrEnum):
    ATENDIMENTO = "atendimento"
    COMPROMISSO = "compromisso"


@dataclass(frozen=True, slots=True)
class Evento:
    inicio: str
    titulo: str
    fim: str = ""
    detalhe: str = ""
    id: str = ""
    tipo: TipoDeEvento | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.inicio, "inicio do evento")
        _obrigatorio(self.titulo, "titulo do evento")

    def compilar(self) -> Json:
        no: Json = {
            "inicio": self.inicio,
            "fim": self.fim,
            "titulo": self.titulo,
            "detalhe": self.detalhe,
            "id": self.id,
        }
        if self.tipo is not None:
            no["tipo"] = self.tipo.value
        return no


@dataclass(frozen=True, slots=True)
class AoTocarODia:
    mostrar: str
    campo_da_data: str

    def __post_init__(self) -> None:
        _nome(self.mostrar, "id da secao do dia")
        _nome(self.campo_da_data, "campo da data")

    def compilar(self) -> Json:
        return {"mostrar": self.mostrar, "preencher": {self.campo_da_data: "data"}}


class GestoDoEvento(StrEnum):
    TOCAR = "tocar"
    ARRASTAR = "arrastar"


_DADOS_DO_EVENTO = {
    "id",
    "data",
    "hora",
    "duracao_minutos",
    "titulo",
    "detalhe",
    "novo_inicio",
    "nova_data",
    "nova_hora",
}


@dataclass(frozen=True, slots=True)
class AcaoDoEvento:
    para: TipoDeEvento
    campos: Mapping[str, str]
    titulo: str = ""
    gesto: GestoDoEvento = GestoDoEvento.TOCAR
    enviar: str | None = None
    mostrar: str | None = None

    def __post_init__(self) -> None:
        if self.gesto == GestoDoEvento.TOCAR:
            _obrigatorio(self.titulo, "titulo da acao do evento")
        if bool(self.enviar) == bool(self.mostrar):
            raise ContratoDoSdkInvalido("acao do evento escolhe enviar ou mostrar")
        if self.enviar:
            _nome(self.enviar, "operacao do evento")
        if self.mostrar:
            _nome(self.mostrar, "id da secao do evento")
        for campo, dado in self.campos.items():
            _nome(campo, "campo da acao do evento")
            if dado not in _DADOS_DO_EVENTO:
                raise ContratoDoSdkInvalido(f"dado do evento desconhecido: {dado}")

    def compilar(self) -> Json:
        no: Json = {
            "para": self.para.value,
            "titulo": self.titulo,
            "gesto": self.gesto.value,
        }
        if self.enviar:
            no["enviar"] = self.enviar
            no["campos"] = dict(self.campos)
        else:
            no["mostrar"] = self.mostrar
            no["preencher"] = dict(self.campos)
        return no


@dataclass(frozen=True, slots=True)
class Calendario:
    eventos: tuple[Evento, ...]
    vista: VistaDoCalendario = VistaDoCalendario.MES
    de: str = ""
    ao_tocar_o_dia: AoTocarODia | None = None
    acoes_do_evento: tuple[AcaoDoEvento, ...] = ()

    def compilar(self) -> Json:
        no: Json = {
            "type": "okmigoCalendario",
            "vista": self.vista.value,
            "de": self.de,
            "eventos": _compilar(self.eventos),
            "acoesDoEvento": _compilar(self.acoes_do_evento),
        }
        if self.ao_tocar_o_dia is not None:
            no["aoTocarODia"] = self.ao_tocar_o_dia.compilar()
        return no


class SemanticaFinanceira(StrEnum):
    POSITIVO = "positivo"
    NEGATIVO = "negativo"
    NEUTRO = "neutro"


@dataclass(frozen=True, slots=True)
class LancamentoFinanceiro:
    titulo: str
    valor: str
    subtitulo: str = ""
    icone: str = ""
    semantica: SemanticaFinanceira = SemanticaFinanceira.NEUTRO
    id: str = ""
    grupo: str = ""
    tipo: str = "todas"

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo do lancamento")

    def compilar(self) -> Json:
        return {
            "id": self.id,
            "grupo": self.grupo,
            "tipo": self.tipo,
            "icone": self.icone,
            "titulo": self.titulo,
            "subtitulo": self.subtitulo,
            "valor": self.valor,
            "semantica": self.semantica.value,
        }


@dataclass(frozen=True, slots=True)
class CartaoFinanceiro:
    titulo: str
    id: str = ""
    tipo: str = ""
    bandeira: str = ""
    numero: str = ""
    titular: str = ""
    validade: str = ""
    tom: TomFinanceiro = TomFinanceiro.PRINCIPAL
    fatura_rotulo: str = ""
    fatura: str = ""
    limite_rotulo: str = ""
    limite: str = ""
    progresso_rotulo: str = ""
    progresso_texto: str = ""
    progresso_feito: int | float | str = 0
    progresso_de: int | float | str = 100
    lancamentos: tuple[LancamentoFinanceiro, ...] = ()

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo do cartao")

    def compilar(self) -> Json:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "tipo": self.tipo,
            "bandeira": self.bandeira,
            "numero": self.numero,
            "titular": self.titular,
            "validade": self.validade,
            "tom": self.tom.value,
            "fatura_rotulo": self.fatura_rotulo,
            "fatura": self.fatura,
            "limite_rotulo": self.limite_rotulo,
            "limite": self.limite,
            "progresso_rotulo": self.progresso_rotulo,
            "progresso_texto": self.progresso_texto,
            "progresso_feito": self.progresso_feito,
            "progresso_de": self.progresso_de,
            "lancamentos": _compilar(self.lancamentos),
        }


@dataclass(frozen=True, slots=True)
class CartoesFinanceiros:
    cartoes: tuple[CartaoFinanceiro, ...]

    def __post_init__(self) -> None:
        if not self.cartoes:
            raise ContratoDoSdkInvalido("bloco precisa de cartoes")

    def compilar(self) -> Json:
        return {"type": "okmigoCartaoBancario", "cartoes": _compilar(self.cartoes)}


@dataclass(frozen=True, slots=True)
class ItemDeDistribuicao:
    rotulo: str
    valor: int | float | str
    texto: str = ""
    tom: TomFinanceiro = TomFinanceiro.PRINCIPAL

    def __post_init__(self) -> None:
        _obrigatorio(self.rotulo, "rotulo da distribuicao")

    def compilar(self) -> Json:
        return {
            "rotulo": self.rotulo,
            "valor": self.valor,
            "texto": self.texto,
            "tom": self.tom.value,
        }


@dataclass(frozen=True, slots=True)
class Distribuicao:
    titulo: str
    itens: tuple[ItemDeDistribuicao, ...]

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("distribuicao precisa de itens")

    def compilar(self) -> Json:
        return {
            "type": "okmigoDistribuicao",
            "titulo": self.titulo,
            "itens": _compilar(self.itens),
        }


@dataclass(frozen=True, slots=True)
class ListaFinanceira:
    titulo: str
    itens: tuple[LancamentoFinanceiro, ...]
    busca: bool = False
    filtros: tuple[str, ...] = ("todas",)

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("lista financeira precisa de itens")
        if not set(self.filtros).issubset({"todas", "entradas", "saidas"}):
            raise ContratoDoSdkInvalido("filtro financeiro desconhecido")

    def compilar(self) -> Json:
        return {
            "type": "okmigoListaFinanceira",
            "titulo": self.titulo,
            "busca": self.busca,
            "filtros": list(self.filtros),
            "itens": _compilar(self.itens),
        }


# ── Composições frequentes; todas viram primitivas acima ───────────────────


@dataclass(frozen=True, slots=True)
class Metrica:
    rotulo: str
    valor: str
    detalhe: str = ""

    def compilar(self) -> Json:
        itens: tuple[Componente, ...] = (
            Texto(self.rotulo, PapelDoTexto.AUXILIAR),
            Texto(self.valor, PapelDoTexto.DESTAQUE),
        )
        if self.detalhe:
            itens += (Texto(self.detalhe, PapelDoTexto.AUXILIAR),)
        return Painel(itens, neutro=True).compilar()


@dataclass(frozen=True, slots=True)
class GradeDeMetricas:
    metricas: tuple[Metrica, ...]

    def __post_init__(self) -> None:
        if not self.metricas:
            raise ContratoDoSdkInvalido("grade precisa de metricas")

    def compilar(self) -> Json:
        return Painel(self.metricas, grade=True, neutro=True).compilar()


@dataclass(frozen=True, slots=True)
class EstadoVazio:
    titulo: str
    explicacao: str
    acao: Acao | None = None

    def compilar(self) -> Json:
        itens: tuple[Componente, ...] = (
            Texto(self.titulo, PapelDoTexto.DESTAQUE),
            Texto(self.explicacao, PapelDoTexto.AUXILIAR),
        )
        if self.acao is not None:
            itens += (Acoes((self.acao,)),)
        return Painel(itens, neutro=True).compilar()


@dataclass(frozen=True, slots=True)
class Ficha:
    titulo: str
    subtitulo: str = ""
    fatos: tuple[Fato, ...] = ()
    conteudo: tuple[Componente, ...] = ()
    acoes: tuple[Componente, ...] = ()
    destaque: bool = False

    def compilar(self) -> Json:
        itens: tuple[Componente, ...] = (Texto(self.titulo, negrito=True),)
        if self.subtitulo:
            itens += (Texto(self.subtitulo, PapelDoTexto.AUXILIAR),)
        if self.fatos:
            itens += (Fatos(self.fatos),)
        itens += self.conteudo
        if self.acoes:
            itens += (Acoes(self.acoes),)
        return Painel(itens, destaque=self.destaque).compilar()


@dataclass(frozen=True, slots=True)
class Formulario:
    titulo: str
    campos: tuple[Componente, ...]
    acoes: tuple[Componente, ...]
    explicacao: str = ""
    rodape: bool = False

    def __post_init__(self) -> None:
        if not self.campos or not self.acoes:
            raise ContratoDoSdkInvalido("formulario precisa de campos e acoes")

    def compilar(self) -> Json:
        itens: tuple[Componente, ...] = (Texto(self.titulo, negrito=True),)
        if self.explicacao:
            itens += (Texto(self.explicacao, PapelDoTexto.AUXILIAR),)
        itens += (*self.campos, Acoes(self.acoes, rodape=self.rodape))
        return Painel(itens).compilar()
