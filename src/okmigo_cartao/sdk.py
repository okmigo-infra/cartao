"""SDK tipado para escrever telas declaradas do OkMigo.

O SDK e uma camada de autoria: ele produz exatamente o contrato Adaptive Card
que o crivo ja aceita. Nenhum objeto daqui atravessa a fronteira em runtime e
nenhum componente permite HTML, JavaScript ou uma URL executavel.
"""

from __future__ import annotations

import re
from copy import deepcopy
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, Self
from urllib.parse import urlsplit

from .agente import AgenteDeDominio, AgenteInvalido

Json = dict[str, Any]
_NOME = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_.-]*|\{[A-Za-z][A-Za-z0-9_.-]*\})"
    r"(?:[A-Za-z0-9_.-]+|\{[A-Za-z][A-Za-z0-9_.-]*\})*$"
)


#: O nome de um parâmetro de rota: identificador simples, sem ponto, hífen nem
#: chaves. ⚠️ Mais estreito que `_NOME` de propósito: o nome vira o marcador
#: `{rota.<nome>}` no `pedido` de uma fonte da ponte, e um nome com chave ou
#: ponto faria o marcador ambíguo. É a MESMA régua do registro no OkMigo.
NOME_DE_PARAMETRO_DA_ROTA = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")

#: ⛔⛔ Nomes que um parâmetro de rota NUNCA pode ter. São os campos que a
#: PLATAFORMA afirma no pedido de tela (quem é o negócio, que dia é hoje, quais
#: grupos a pessoa alcança) e os dois envelopes da navegação. Um parâmetro
#: chamado `tenant` é o botão de um cartão tentando escolher de qual negócio a
#: tela lê — e um parâmetro de rota é dado que atravessa o cliente.
NOMES_RESERVADOS_DA_ROTA: frozenset[str] = frozenset({
    "credencial", "tenant", "hoje", "grupos", "grupos_nomes", "rota", "parametros",
})


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


class TipoDeParametroDaRota(StrEnum):
    TEXTO = "texto"
    INTEIRO = "inteiro"
    DECIMAL = "decimal"
    BOOLEANO = "booleano"


@dataclass(frozen=True, slots=True)
class ParametroDaRota:
    """Um parâmetro fechado que uma rota interna aceita.

    Rotas nunca recebem um endereço livre. O nome e o tipo são publicados no
    manifesto para que SDK, crivo e clientes rejeitem qualquer dado extra.
    """

    nome: str
    tipo: TipoDeParametroDaRota = TipoDeParametroDaRota.TEXTO
    obrigatorio: bool = True

    def __post_init__(self) -> None:
        if not NOME_DE_PARAMETRO_DA_ROTA.fullmatch(self.nome):
            raise ContratoDoSdkInvalido(
                "parametro da rota precisa ser um identificador simples "
                f"(letras, números e _), recebi {self.nome!r}"
            )
        if self.nome in NOMES_RESERVADOS_DA_ROTA:
            raise ContratoDoSdkInvalido(
                f"parametro da rota {self.nome!r} é reservado pela plataforma"
            )

    def compilar(self) -> Json:
        return {
            "nome": self.nome,
            "tipo": self.tipo.value,
            "obrigatorio": self.obrigatorio,
        }


@dataclass(frozen=True, slots=True)
class Rota:
    """Destino interno registrado pelo aplicativo."""

    nome: str
    superficie: str
    parametros: tuple[ParametroDaRota, ...] = ()
    compartilhavel: bool = False
    historico: bool = False
    favoritavel: bool = False

    def __post_init__(self) -> None:
        _nome(self.nome, "nome da rota")
        _nome(self.superficie, "superficie da rota")
        nomes = [parametro.nome for parametro in self.parametros]
        if len(nomes) != len(set(nomes)):
            raise ContratoDoSdkInvalido(f"rota {self.nome!r} repete parametros")

    def compilar(self) -> Json:
        return {
            "nome": self.nome,
            "superficie": self.superficie,
            "parametros": _compilar(self.parametros),
            "compartilhavel": self.compartilhavel,
            "historico": self.historico,
            "favoritavel": self.favoritavel,
        }


@dataclass(frozen=True, slots=True)
class DestinoDaRota:
    """Uma ida tipada para uma rota registrada, nunca para uma URL."""

    rota: str
    parametros: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _nome(self.rota, "rota de destino")
        for nome in self.parametros:
            _nome(nome, "parametro do destino")

    def compilar(self) -> Json:
        return {
            "rota": self.rota,
            "parametros": deepcopy(dict(self.parametros)),
        }


class EstadoDoIndicador(StrEnum):
    CONTAGEM = "contagem"
    NOVO = "novo"
    ATENCAO = "atencao"
    ERRO = "erro"


@dataclass(frozen=True, slots=True)
class IndicadorDeNavegacao:
    """Resumo não sensível exibido junto de uma área ou superfície."""

    operacao: str
    rotulo: str
    estado: EstadoDoIndicador = EstadoDoIndicador.CONTAGEM
    caminho: str | None = None

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao do indicador")
        if self.caminho is not None:
            _nome(self.caminho, "caminho do indicador")
        if not self.rotulo.strip():
            raise ContratoDoSdkInvalido("indicador precisa de rotulo acessivel")

    def compilar(self) -> Json:
        no: Json = {
            "operacao": self.operacao,
            "rotulo": self.rotulo,
            "estado": self.estado.value,
        }
        if self.caminho is not None:
            no["caminho"] = self.caminho
        return no


#: Os ícones de tela que os DOIS clientes do OkMigo (web e app) desenham.
#:
#: ⛔ Um nome fora daqui não quebra nada — o cliente desenha um ícone padrão —
#: e é exatamente esse o defeito: todas as abas viram a mesma casinha, sem
#: erro em lugar nenhum. Aconteceu duas vezes com os ícones das SUPERFÍCIES
#: (que este SDK não confere, por compatibilidade). O grupo de navegação é novo
#: e nasce conferido. Ícone novo entra aqui junto com o desenho nos clientes.
ICONES_DE_TELA: frozenset[str] = frozenset({
    "agenda", "alunos", "ano", "arquivo", "ativos", "avisos", "balcao",
    "bloqueios", "cardapio", "carteira", "cartoes", "categorias", "chamados",
    "clientes", "cobrancas", "comunicados", "contador", "contas", "cozinha",
    "cvm", "desempenho", "enviados", "enviar", "espacos", "especialidade",
    "evolucao", "expediente", "extrato", "fiis", "gestao", "hoje", "inicio",
    "local", "meu-lar", "meu-predio", "nutricao", "pacientes", "patio",
    "pendencias", "perfil", "predio", "radar", "recebidos", "regras",
    "renda-fixa", "salao", "sem_assunto", "servicos", "sorteios", "treino",
    "visao-geral",
})


@dataclass(frozen=True, slots=True)
class GrupoDeNavegacao:
    """Um destino principal e as telas relacionadas que vivem dentro dele.

    O grupo vira um item da barra inferior. As ``superficies`` viram abas
    horizontais no topo; ``inicial`` define qual delas abre ao trocar de grupo.
    """

    nome: str
    rotulo: str
    icone: str
    superficies: tuple[str, ...]
    inicial: str | None = None
    indicador: IndicadorDeNavegacao | None = None

    def __post_init__(self) -> None:
        _nome(self.nome, "nome do grupo de navegacao")
        _nome(self.icone, "icone do grupo de navegacao")
        if self.icone not in ICONES_DE_TELA:
            raise ContratoDoSdkInvalido(
                f"icone {self.icone!r} do grupo {self.nome!r} nao e desenhado "
                "pelos clientes do OkMigo — viraria o icone padrao, igual aos "
                "outros; use um de ICONES_DE_TELA"
            )
        if not self.rotulo.strip():
            raise ContratoDoSdkInvalido(
                "grupo de navegacao precisa de rotulo"
            )
        if not self.superficies:
            raise ContratoDoSdkInvalido(
                f"grupo de navegacao {self.nome!r} precisa de superficies"
            )
        repetidas = {
            nome for nome in self.superficies
            if self.superficies.count(nome) > 1
        }
        for superficie in self.superficies:
            _nome(superficie, "superficie do grupo de navegacao")
        if repetidas:
            raise ContratoDoSdkInvalido(
                f"grupo de navegacao {self.nome!r} repete superficies: "
                + ", ".join(sorted(repetidas))
            )
        if self.inicial is not None and self.inicial not in self.superficies:
            raise ContratoDoSdkInvalido(
                f"superficie inicial {self.inicial!r} nao pertence ao grupo "
                f"{self.nome!r}"
            )

    def compilar(self) -> Json:
        compilado: Json = {
            "nome": self.nome,
            "rotulo": self.rotulo,
            "icone": self.icone,
            "superficies": list(self.superficies),
            "inicial": self.inicial or self.superficies[0],
        }
        if self.indicador is not None:
            compilado["indicador"] = self.indicador.compilar()
        return compilado


@dataclass(frozen=True, slots=True)
class NavegacaoAgrupada:
    """Navegação em até cinco áreas, sem transformar a última em gaveta."""

    grupos: tuple[GrupoDeNavegacao, ...]

    def __post_init__(self) -> None:
        if not 2 <= len(self.grupos) <= 5:
            raise ContratoDoSdkInvalido(
                "navegacao agrupada precisa ter de 2 a 5 grupos"
            )
        nomes = [grupo.nome for grupo in self.grupos]
        repetidos = {nome for nome in nomes if nomes.count(nome) > 1}
        if repetidos:
            raise ContratoDoSdkInvalido(
                "navegacao agrupada repete grupos: "
                + ", ".join(sorted(repetidos))
            )

    def conferir(self, superficies: tuple[str, ...]) -> None:
        declaradas = [
            superficie
            for grupo in self.grupos
            for superficie in grupo.superficies
        ]
        repetidas = {
            nome for nome in declaradas if declaradas.count(nome) > 1
        }
        desconhecidas = set(declaradas) - set(superficies)
        ausentes = set(superficies) - set(declaradas)
        problemas = []
        if repetidas:
            problemas.append("repetidas: " + ", ".join(sorted(repetidas)))
        if desconhecidas:
            problemas.append(
                "desconhecidas: " + ", ".join(sorted(desconhecidas))
            )
        if ausentes:
            problemas.append("sem grupo: " + ", ".join(sorted(ausentes)))
        if problemas:
            raise ContratoDoSdkInvalido(
                "navegacao agrupada nao cobre as superficies exatamente uma vez ("
                + "; ".join(problemas)
                + ")"
            )

    def compilar(self) -> Json:
        return {"tipo": "agrupada", "grupos": _compilar(self.grupos)}


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
    tamanho: str | None = None
    peso: str | None = None
    sutil: bool | None = None
    quebrar: bool | None = True

    def __post_init__(self) -> None:
        if not self.texto:
            raise ContratoDoSdkInvalido("texto nao pode ser vazio")

    def compilar(self) -> Json:
        no: Json = {"type": "TextBlock", "text": self.texto}
        if self.quebrar is not None:
            no["wrap"] = self.quebrar
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
        if self.tamanho is not None:
            no["size"] = self.tamanho
        if self.peso is not None:
            no["weight"] = self.peso
        if self.sutil is not None:
            no["isSubtle"] = self.sutil
        return no


@dataclass(frozen=True, slots=True)
class Opcao:
    titulo: str
    valor: str
    nota: str | None = None
    icone: str | None = None
    #: A FOTO da opção, quando a escolha é em cartões (OMINFRA-559).
    #:
    #: ⭐ O `icone` é um glifo — um emoji, doze pontos de código no máximo. Há
    #: escolha em que a imagem É o conteúdo: uma grade de áreas de treino em
    #: que cada tile mostra o exercício-símbolo, e não um bonequinho.
    #:
    #: ⛔ **URL DA CASA, como toda imagem do cartão.** Quem hospeda é o
    #: produto; endereço de outro domínio é recusado pelo crivo — uma imagem
    #: servida pelo terceiro faria o aparelho de CADA pessoa que abre a tela
    #: bater no servidor dele, entregando o IP de quem ela não escolheu
    #: contatar. Vale `/img/<chave>` ou a URL absoluta da base de imagens.
    imagem: str | None = None

    def compilar(self) -> Json:
        if not self.titulo or not self.valor:
            raise ContratoDoSdkInvalido("opcao precisa de titulo e valor")
        no = {"title": self.titulo, "value": self.valor}
        if self.nota:
            no["okmigoNota"] = self.nota
        if self.icone:
            no["okmigoIcone"] = self.icone
        if self.imagem:
            no["okmigoImagem"] = self.imagem
        return no


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
    #: A consulta disparada ao ESCOLHER uma sugestao — sem segundo toque.
    #:
    #: ⛔ Sem isto a busca so PREENCHE o campo, e quem escolhe um resultado
    #: fica olhando para a tela sem nada acontecer: o valor esta la e nenhuma
    #: acao o consome. Foi defeito de tela real (21/09).
    #:
    #: ⚠️ So LEITURA. Escrever ao escolher seria gravar por engano de toque,
    #: sem confirmacao — o crivo recusa.
    ao_escolher: Acao | None = None

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
        if self.ao_escolher is not None:
            if self.ao_escolher.tipo is not TipoDeAcao.LEITURA:
                raise ContratoDoSdkInvalido(
                    "ao_escolher so aceita acao de LEITURA: escolher uma "
                    "sugestao nao pode gravar nada"
                )
            no["okmigoAoEscolher"] = self.ao_escolher.compilar()
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
    NAVEGACAO = "navegacao"


class EnfaseDaAcao(StrEnum):
    PADRAO = "padrao"
    PRIMARIA = "primaria"
    DESTRUTIVA = "destrutiva"
    SECUNDARIA = "secundaria"


@dataclass(frozen=True, slots=True)
class Confirmacao:
    """Confirma uma operação antes de atravessar a fronteira do produto."""

    titulo: str
    mensagem: str
    confirmar: str = "Confirmar"
    cancelar: str = "Cancelar"

    def __post_init__(self) -> None:
        if not all((self.titulo.strip(), self.mensagem.strip(), self.confirmar.strip(), self.cancelar.strip())):
            raise ContratoDoSdkInvalido("confirmacao precisa de todos os textos")

    def compilar(self) -> Json:
        return {
            "titulo": self.titulo,
            "mensagem": self.mensagem,
            "confirmar": self.confirmar,
            "cancelar": self.cancelar,
        }


@dataclass(frozen=True, slots=True)
class Acao:
    titulo: str
    operacao: str | None
    tipo: TipoDeAcao
    enfase: EnfaseDaAcao = EnfaseDaAcao.PADRAO
    icone: str | None = None
    confirmacao: Confirmacao | None = None
    dados: Mapping[str, Any] = field(default_factory=dict)
    modo_secundario: bool = False
    alvos_apos_enviar: tuple[Componente, ...] = ()
    transicao_tipada: bool = True
    destino: DestinoDaRota | None = None

    def __post_init__(self) -> None:
        if self.tipo == TipoDeAcao.NAVEGACAO:
            if self.operacao is not None or self.destino is None:
                raise ContratoDoSdkInvalido(
                    "acao de navegacao precisa apenas de um destino tipado"
                )
        else:
            if self.operacao is None:
                raise ContratoDoSdkInvalido("acao precisa de operacao")
            _nome(self.operacao, "operacao")
            if self.destino is not None:
                raise ContratoDoSdkInvalido(
                    "leitura ou escrita nao pode carregar rota interna"
                )
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
        confirmacao: Confirmacao | None = None,
        dados: Mapping[str, Any] | None = None,
        modo_secundario: bool = False,
        alvos_apos_enviar: tuple[Componente, ...] = (),
        transicao_tipada: bool = True,
    ) -> Self:
        return cls(
            titulo, operacao, TipoDeAcao.LEITURA, enfase, None,
            confirmacao, dados or {}, modo_secundario,
            alvos_apos_enviar, transicao_tipada, None,
        )

    @classmethod
    def escrever(
        cls,
        titulo: str,
        operacao: str,
        *,
        enfase: EnfaseDaAcao = EnfaseDaAcao.PADRAO,
        icone: str | None = None,
        confirmacao: Confirmacao | None = None,
        dados: Mapping[str, Any] | None = None,
        modo_secundario: bool = False,
        alvos_apos_enviar: tuple[Componente, ...] = (),
        transicao_tipada: bool = True,
    ) -> Self:
        return cls(
            titulo, operacao, TipoDeAcao.ESCRITA, enfase, icone,
            confirmacao, dados or {}, modo_secundario,
            alvos_apos_enviar, transicao_tipada, None,
        )

    @classmethod
    def navegar(
        cls,
        titulo: str,
        rota: str,
        *,
        parametros: Mapping[str, Any] | None = None,
        enfase: EnfaseDaAcao = EnfaseDaAcao.PADRAO,
        modo_secundario: bool = False,
    ) -> Self:
        """Abre uma rota interna declarada sem executar leitura ou escrita."""
        return cls(
            titulo,
            None,
            TipoDeAcao.NAVEGACAO,
            enfase,
            None,
            None,
            {},
            modo_secundario,
            (),
            True,
            DestinoDaRota(rota, parametros or {}),
        )

    def compilar(self) -> Json:
        if self.tipo == TipoDeAcao.NAVEGACAO:
            no: Json = {
                "type": "Action.Execute",
                "title": self.titulo,
                "data": {"okmigoNavegar": self.destino.compilar()},
            }
        else:
            no = {
                "type": "Action.Execute"
                if self.tipo == TipoDeAcao.LEITURA
                else "Action.Submit",
                "title": self.titulo,
                "data": {"operacao": self.operacao, **deepcopy(dict(self.dados))},
            }
        if self.enfase == EnfaseDaAcao.PRIMARIA:
            no["style"] = "positive"
        elif self.enfase == EnfaseDaAcao.DESTRUTIVA:
            no["style"] = "destructive"
        elif self.enfase == EnfaseDaAcao.SECUNDARIA:
            no["mode"] = "secondary"
        if self.modo_secundario:
            no["mode"] = "secondary"
        if self.icone == "lixeira":
            no["okmigoIcone"] = "delete"
        if self.confirmacao is not None:
            no["okmigoConfirmacao"] = self.confirmacao.compilar()
        if self.alvos_apos_enviar:
            alvos = _compilar(self.alvos_apos_enviar)
            no["okmigoAposEnviar"] = (
                {"type": "Action.ToggleVisibility", "targetElements": alvos}
                if self.transicao_tipada
                else alvos
            )
        return no


@dataclass(frozen=True, slots=True)
class Acoes:
    itens: tuple[Componente, ...]
    rodape: bool = False
    espaco: Espaco | None = None

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("grupo de acoes nao pode ser vazio")

    def compilar(self) -> Json:
        no: Json = {"type": "ActionSet", "actions": _compilar(self.itens)}
        if self.rodape:
            no["okmigoRodape"] = True
        if self.espaco is not None:
            no["spacing"] = self.espaco.value
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
    tom: str | None = None
    alinhamento_vertical: str | None = None

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("area de colunas nao pode ser vazia")

    def compilar(self) -> Json:
        no: Json = {
            "type": "Column",
            "width": self.largura.value,
            "items": _compilar(self.itens),
        }
        if self.tom is not None:
            no["style"] = self.tom
        if self.alinhamento_vertical is not None:
            no["verticalContentAlignment"] = self.alinhamento_vertical
        return no


@dataclass(frozen=True, slots=True)
class Faixa:
    areas: tuple[Area, ...]
    espaco: Espaco | None = None

    def __post_init__(self) -> None:
        if not 1 <= len(self.areas) <= 12:
            raise ContratoDoSdkInvalido("faixa precisa ter entre 1 e 12 areas")

    def compilar(self) -> Json:
        no: Json = {"type": "ColumnSet", "columns": _compilar(self.areas)}
        if self.espaco is not None:
            no["spacing"] = self.espaco.value
        return no


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
    espaco: Espaco | None = None
    separador: bool | None = None

    def __post_init__(self) -> None:
        if not self.itens:
            raise ContratoDoSdkInvalido("conjunto de fatos nao pode ser vazio")

    def compilar(self) -> Json:
        no: Json = {"type": "FactSet", "facts": _compilar(self.itens)}
        if self.espaco is not None:
            no["spacing"] = self.espaco.value
        if self.separador is not None:
            no["separator"] = self.separador
        return no


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
        rotas: Mapping[str, Mapping[str, str]] | None = None,
    ) -> Json:
        """Compila e passa pelo crivo, falhando cedo com uma mensagem útil."""
        from .crivo import validar

        normalizada, erro = validar(
            self.compilar(), leituras=leituras, escrituras=escrituras,
            rotas={nome: dict(parametros) for nome, parametros in rotas.items()}
            if rotas is not None else None,
        )
        if erro or normalizada is None:
            raise ContratoDoSdkInvalido(erro or "o crivo recusou a tela")
        return normalizada


@dataclass(frozen=True, slots=True)
class ConsultaDaFonte:
    """Uma chamada declarada para preencher resumo ou lista de uma superfície."""

    operacao: str
    caminho: str | None = None
    pedido: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao da fonte")
        if self.caminho is not None:
            _nome(self.caminho, "caminho da fonte")
        for chave in self.pedido:
            _nome(chave, "campo do pedido da fonte")

    def compilar(self) -> Json:
        consulta: Json = {"operacao": self.operacao}
        if self.pedido:
            consulta["pedido"] = deepcopy(dict(self.pedido))
        if self.caminho is not None:
            consulta["caminho"] = self.caminho
        return consulta


@dataclass(frozen=True, slots=True)
class Fonte:
    """Fontes independentes para o resumo e a lista de uma superfície.

    ``Fonte("operacao", "itens")`` continua sendo o atalho usado pelo
    piloto do RadarIA: a mesma operação alimenta o resumo e a lista.
    """

    resumo: ConsultaDaFonte | str
    lista: ConsultaDaFonte | str | None = None

    def __post_init__(self) -> None:
        resumo = self.resumo
        if isinstance(resumo, str):
            resumo = ConsultaDaFonte(resumo)
            object.__setattr__(self, "resumo", resumo)
        if isinstance(self.lista, str):
            object.__setattr__(
                self,
                "lista",
                ConsultaDaFonte(resumo.operacao, caminho=self.lista),
            )

    def compilar(self) -> Json:
        fonte: Json = {"resumo": self.resumo.compilar()}
        if self.lista is not None:
            fonte["lista"] = self.lista.compilar()
        return fonte


@dataclass(frozen=True, slots=True)
class OperacaoParametrizada:
    operacao: str
    parametro: str

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao")
        _nome(self.parametro, "parametro")

    def compilar(self) -> Json:
        return {"operacao": self.operacao, "parametro": self.parametro}


@dataclass(frozen=True, slots=True)
class Convite:
    operacao: str
    parametro: str
    par: str
    pares: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao do convite")
        _nome(self.parametro, "parametro do convite")
        _nome(self.par, "par do convite")
        if len(self.pares) > 4 or len(set(self.pares)) != len(self.pares):
            raise ContratoDoSdkInvalido("convite aceita ate quatro pares adicionais distintos")
        for adicional in self.pares:
            _nome(adicional, "par adicional do convite")
            if adicional == self.par:
                raise ContratoDoSdkInvalido("par adicional ja e o par principal")

    def compilar(self) -> Json:
        convite: Json = {"operacao": self.operacao, "parametro": self.parametro, "par": self.par}
        if self.pares:
            convite["pares"] = list(self.pares)
        return convite


@dataclass(frozen=True, slots=True)
class MarcaSolicitada:
    operacao: str
    nome: str
    logo: str

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao da marca")
        _nome(self.nome, "campo do nome da marca")
        _nome(self.logo, "campo do logo da marca")

    def compilar(self) -> Json:
        return {"operacao": self.operacao, "nome": self.nome, "logo": self.logo}


@dataclass(frozen=True, slots=True)
class ContatoAceito:
    operacao: str
    parametro: str
    rotulo: str

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao do contato")
        _nome(self.parametro, "parametro do contato")
        _nome(self.rotulo, "campo do rotulo do contato")

    def compilar(self) -> Json:
        return {"operacao": self.operacao, "parametro": self.parametro, "rotulo": self.rotulo}


@dataclass(frozen=True, slots=True)
class CatalogoPublico:
    ofertas: str
    expediente: str | None = None

    def __post_init__(self) -> None:
        _nome(self.ofertas, "operacao das ofertas publicas")
        if self.expediente is not None:
            _nome(self.expediente, "operacao do expediente publico")

    def compilar(self) -> Json:
        publico: Json = {"ofertas": self.ofertas}
        if self.expediente is not None:
            publico["expediente"] = self.expediente
        return publico


@dataclass(frozen=True, slots=True)
class MarcaHorario:
    operacao: str
    ofertas: str

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao de horario")
        _nome(self.ofertas, "operacao das ofertas do horario")

    def compilar(self) -> Json:
        return {"operacao": self.operacao, "ofertas": self.ofertas}


@dataclass(frozen=True, slots=True)
class PainelResumido:
    rotulo: str
    valor: str
    quebra: tuple[str, ...] = ()

    def compilar(self) -> Json:
        painel: Json = {"rotulo": self.rotulo, "valor": self.valor}
        if self.quebra:
            painel["quebra"] = list(self.quebra)
        return painel


@dataclass(frozen=True, slots=True)
class ItemResumido:
    id: str
    texto: str
    apoio: str
    marca: str

    def compilar(self) -> Json:
        return {
            "id": self.id,
            "texto": self.texto,
            "apoio": self.apoio,
            "marca": self.marca,
        }


@dataclass(frozen=True, slots=True)
class TelaResumida:
    titulo: str
    resumo: str
    paineis: tuple[PainelResumido, ...]
    item: ItemResumido
    agrupar_por: str | None = None
    ordem_dos_grupos: tuple[str, ...] = ()
    titulo_do_grupo: Mapping[str, str] = field(default_factory=dict)

    def compilar(self) -> Json:
        tela: Json = {
            "titulo": self.titulo,
            "resumo": self.resumo,
            "paineis": _compilar(self.paineis),
            "item": self.item.compilar(),
        }
        if self.agrupar_por is not None:
            tela["agrupar_por"] = self.agrupar_por
        if self.ordem_dos_grupos:
            tela["ordem_dos_grupos"] = list(self.ordem_dos_grupos)
        if self.titulo_do_grupo:
            tela["titulo_do_grupo"] = deepcopy(dict(self.titulo_do_grupo))
        return tela


@dataclass(frozen=True, slots=True)
class Superficie:
    nome: str
    titulo: str
    rotulo: str | None
    icone: str | None
    hint: str
    fonte: Fonte
    tela: Tela
    representacao: TelaResumida | None = None
    visivel: bool | None = None
    rotulo_superficie: str | None = None

    def __post_init__(self) -> None:
        _nome(self.nome, "nome da superficie")
        if self.icone is not None:
            _nome(self.icone, "icone da superficie")
        if not self.titulo or not self.hint:
            raise ContratoDoSdkInvalido(
                "superficie precisa de titulo e explicacao"
            )

    def compilar(self) -> Json:
        superficie: Json = {
            "nome": self.nome,
            "titulo": self.titulo,
            "hint": self.hint,
            "fonte": self.fonte.compilar(),
            "cartao": self.tela.compilar(),
        }
        if self.rotulo is not None:
            superficie["rotulo"] = self.rotulo
        if self.icone is not None:
            superficie["icone"] = self.icone
        if self.representacao is not None:
            superficie["tela"] = self.representacao.compilar()
        if self.visivel is not None:
            superficie["isVisible"] = self.visivel
        if self.rotulo_superficie is not None:
            superficie["rotulo_superficie"] = self.rotulo_superficie
        return superficie


@dataclass(frozen=True, slots=True)
class DocumentoDeclarado:
    """Os campos de uma operação que carregam DOCUMENTO da pessoa, declarados.

    ⛔⛔ **Existe por causa de uma garantia, não de uma conveniência.** O okmigo
    passa todo pedido de saída por um filtro de privacidade (D21): o amigo
    traduz o que sabe no MÍNIMO que o outro agente precisa, e a camada
    estrutural barra documento, financeiro, saúde e credencial. Medido em
    18/09, era esse filtro que fazia CONECTAR UM BANCO ser impossível pela
    tela: o CPF que a pessoa digitava batia no padrão de `documento` e o pedido
    morria antes de sair, com o formulário certo e o serviço saudável do lado.

    ⭐ **O filtro continua valendo; o que muda é que a exceção passa a ser
    DECLARADA.** O serviço diz, no contrato que a pessoa aprova ao instalar,
    quais campos de qual operação recebem documento — e só esses. Um campo
    `cpf` numa operação não declarada segue barrado, e um serviço que queira
    colher documento tem de escrever isso onde se lê.

    ⛔ **Isto NÃO autoriza o modelo.** A exceção vale para valor DIGITADO pela
    pessoa num formulário de tela; o consumidor é quem faz cumprir. É a mesma
    distinção que o `pela_pessoa` já faz no portão de dois turnos: o portão
    existe para conter o modelo, e num formulário não há nada a provar.

    ⚠️ Documento é CPF e CNPJ. Senha nunca entra aqui, e não é por esquecimento
    — quem pede a senha do banco é o banco, na página dele.
    """

    operacao: str
    campos: tuple[str, ...]

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao que recebe documento")
        if not self.campos:
            raise ContratoDoSdkInvalido(
                "documento declarado sem campo nenhum: declare o que recebe")
        for campo in self.campos:
            _nome(campo, "campo de documento")
            if campo not in {"cpf", "cnpj"}:
                raise ContratoDoSdkInvalido(
                    f"campo de documento fora da lista fechada: {campo!r}. "
                    "Documento aqui e CPF ou CNPJ — senha o banco pede na "
                    "pagina dele.")

    def compilar(self) -> Json:
        return {"operacao": self.operacao, "campos": list(self.campos)}


@dataclass(frozen=True, slots=True)
class TipoDeResultadoDaBusca:
    """Uma categoria fechada de resultado da busca do aplicativo."""

    nome: str
    rotulo: str
    rota: str
    icone: str | None = None

    def __post_init__(self) -> None:
        _nome(self.nome, "tipo de resultado")
        _nome(self.rota, "rota do resultado")
        if not self.rotulo.strip():
            raise ContratoDoSdkInvalido("tipo de resultado precisa de rotulo")
        if self.icone is not None and self.icone not in ICONES_DE_TELA:
            raise ContratoDoSdkInvalido(f"icone de resultado desconhecido: {self.icone}")

    def compilar(self) -> Json:
        no: Json = {"nome": self.nome, "rotulo": self.rotulo, "rota": self.rota}
        if self.icone is not None:
            no["icone"] = self.icone
        return no


@dataclass(frozen=True, slots=True)
class BuscaDoAplicativo:
    """Busca transversal declarada no manifesto, isolada por aplicativo."""

    operacao: str
    tipos: tuple[TipoDeResultadoDaBusca, ...]
    placeholder: str = "Buscar"
    recentes: bool = True

    def __post_init__(self) -> None:
        _nome(self.operacao, "operacao da busca do aplicativo")
        if not self.tipos or len(self.tipos) > 12:
            raise ContratoDoSdkInvalido("busca do aplicativo aceita de 1 a 12 tipos")
        nomes = [tipo.nome for tipo in self.tipos]
        if len(nomes) != len(set(nomes)):
            raise ContratoDoSdkInvalido("busca do aplicativo repete tipos")
        if not self.placeholder.strip():
            raise ContratoDoSdkInvalido("busca do aplicativo precisa de placeholder")

    def compilar(self) -> Json:
        return {
            "operacao": self.operacao,
            "placeholder": self.placeholder,
            "recentes": self.recentes,
            "tipos": _compilar(self.tipos),
        }


class PersistenciaDoEstado(StrEnum):
    SESSAO = "sessao"
    SINCRONIZADA = "sincronizada"


@dataclass(frozen=True, slots=True)
class EstadoRestauravel:
    """Estado de UI que o produto pode restaurar sem guardar dado sensível."""

    superficie: str
    campos: tuple[str, ...] = ("filtros", "ordem", "paginacao", "rolagem")
    persistencia: PersistenciaDoEstado = PersistenciaDoEstado.SESSAO
    visoes_salvas: bool = False
    versao: str = "1"
    expira_em_horas: int = 24

    def __post_init__(self) -> None:
        _nome(self.superficie, "superficie do estado")
        permitidos = {"filtros", "ordem", "paginacao", "rolagem", "selecao", "rascunho"}
        if not self.campos or set(self.campos) - permitidos:
            raise ContratoDoSdkInvalido("estado restauravel usa campo desconhecido")
        if len(self.campos) != len(set(self.campos)):
            raise ContratoDoSdkInvalido("estado restauravel repete campos")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,39}", self.versao):
            raise ContratoDoSdkInvalido(
                "versao do estado restauravel precisa ter de 1 a 40 caracteres seguros"
            )
        if not 1 <= self.expira_em_horas <= 24 * 90:
            raise ContratoDoSdkInvalido("estado restauravel expira entre 1 hora e 90 dias")
        if self.visoes_salvas and self.persistencia != PersistenciaDoEstado.SINCRONIZADA:
            raise ContratoDoSdkInvalido(
                "visoes salvas precisam de persistencia sincronizada"
            )

    def compilar(self) -> Json:
        return {
            "superficie": self.superficie,
            "campos": list(self.campos),
            "persistencia": self.persistencia.value,
            "visoes_salvas": self.visoes_salvas,
            "versao": self.versao,
            "expira_em_horas": self.expira_em_horas,
        }


@dataclass(frozen=True, slots=True)
class HistoricoDeNavegacao:
    """Política mínima para recentes e favoritos de destinos internos."""

    recentes: bool = True
    favoritos: bool = True
    limite: int = 20
    retencao_dias: int = 30

    def __post_init__(self) -> None:
        if not 1 <= self.limite <= 50:
            raise ContratoDoSdkInvalido("historico aceita de 1 a 50 destinos")
        if not 1 <= self.retencao_dias <= 90:
            raise ContratoDoSdkInvalido("retencao do historico aceita de 1 a 90 dias")

    def compilar(self) -> Json:
        return {
            "recentes": self.recentes,
            "favoritos": self.favoritos,
            "limite": self.limite,
            "retencao_dias": self.retencao_dias,
        }


@dataclass(frozen=True, slots=True)
class Aplicativo:
    slug: str
    endpoint: str
    para_tipo: str | None
    descricao: str
    descricao_humana: str | None
    nome_visivel: str | None
    versao: str
    conversa: tuple[str, ...] | None
    superficies: tuple[Superficie, ...]
    navegacao_agrupada: NavegacaoAgrupada | None = None
    rotas: tuple[Rota, ...] = ()
    busca: BuscaDoAplicativo | None = None
    estados_restauraveis: tuple[EstadoRestauravel, ...] = ()
    historico_de_navegacao: HistoricoDeNavegacao | None = None
    forma: str = "do_operador"
    eventos: OperacaoParametrizada | None = None
    avisa_antes: OperacaoParametrizada | None = None
    relata_mudancas: OperacaoParametrizada | None = None
    convite: Convite | None = None
    quer_a_marca: MarcaSolicitada | None = None
    aceita_contato: ContatoAceito | None = None
    publico: CatalogoPublico | None = None
    marca_horario: MarcaHorario | None = None
    #: ⛔ As operações que recebem DOCUMENTO da pessoa, uma a uma.
    #: Vazio = nenhuma, e o filtro de privacidade do consumidor barra
    #: qualquer documento que tente sair — que é o padrão certo.
    recebe_documento: tuple[DocumentoDeclarado, ...] = ()
    so_por_convite: bool = False
    em_breve: bool = False
    tipo: str | None = None
    tenant_sondagem: str | None = None
    credencial_sondagem: str | None = None
    vitrine_url: str | None = None
    #: ⭐ O agente de domínio (contrato 1, ADR 001 do okmigo). Sem ele, o
    #: serviço segue só MCP — é a compatibilidade, não um modo degradado.
    agente: AgenteDeDominio | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _nome(self.slug, "slug")
        if self.forma != "do_operador" or self.para_tipo not in {None, "amigo", "socio"}:
            raise ContratoDoSdkInvalido("forma ou destinatario do aplicativo invalido")
        if not self.endpoint.startswith(("http://", "https://")):
            raise ContratoDoSdkInvalido("endpoint precisa ser http ou https")
        if not self.superficies:
            raise ContratoDoSdkInvalido("aplicativo precisa de superficies")
        nomes_das_superficies = tuple(
            superficie.nome for superficie in self.superficies
        )
        if len(set(nomes_das_superficies)) != len(nomes_das_superficies):
            raise ContratoDoSdkInvalido("aplicativo repete superficies")
        if self.navegacao_agrupada is not None:
            self.navegacao_agrupada.conferir(nomes_das_superficies)
        nomes_das_rotas = [rota.nome for rota in self.rotas]
        if len(nomes_das_rotas) != len(set(nomes_das_rotas)):
            raise ContratoDoSdkInvalido("aplicativo repete rotas")
        for rota in self.rotas:
            if rota.superficie not in nomes_das_superficies:
                raise ContratoDoSdkInvalido(
                    f"rota {rota.nome!r} aponta para superficie desconhecida {rota.superficie!r}"
                )
        if self.busca is not None:
            desconhecidas = {tipo.rota for tipo in self.busca.tipos} - set(nomes_das_rotas)
            if desconhecidas:
                raise ContratoDoSdkInvalido(
                    "busca aponta para rotas desconhecidas: " + ", ".join(sorted(desconhecidas))
                )
        for estado in self.estados_restauraveis:
            if estado.superficie not in nomes_das_superficies:
                raise ContratoDoSdkInvalido(
                    f"estado aponta para superficie desconhecida {estado.superficie!r}"
                )
        rotas_por_nome = {rota.nome: rota for rota in self.rotas}

        def conferir_destinos(valor: Any) -> None:
            if isinstance(valor, list):
                for item in valor:
                    conferir_destinos(item)
                return
            if not isinstance(valor, dict):
                return
            destino = valor.get("okmigoNavegar")
            if isinstance(destino, dict):
                nome_da_rota = destino.get("rota")
                if nome_da_rota not in rotas_por_nome:
                    raise ContratoDoSdkInvalido(
                        f"acao aponta para rota desconhecida {nome_da_rota!r}"
                    )
                parametros = destino.get("parametros") or {}
                if not isinstance(parametros, dict):
                    raise ContratoDoSdkInvalido("parametros da rota precisam ser um mapa")
                contrato = rotas_por_nome[nome_da_rota]
                declarados = {parametro.nome: parametro for parametro in contrato.parametros}
                extras = set(parametros) - set(declarados)
                ausentes = {
                    nome for nome, parametro in declarados.items()
                    if parametro.obrigatorio and nome not in parametros
                }
                if extras or ausentes:
                    partes = []
                    if extras:
                        partes.append("extras: " + ", ".join(sorted(extras)))
                    if ausentes:
                        partes.append("ausentes: " + ", ".join(sorted(ausentes)))
                    raise ContratoDoSdkInvalido(
                        f"destino da rota {nome_da_rota!r} tem parametros invalidos ("
                        + "; ".join(partes) + ")"
                    )
                for nome, valor_do_parametro in parametros.items():
                    # Um molde ``{campo}`` só ganha tipo depois de a ponte
                    # expandi-lo. Valores literais, porém, são conferidos já
                    # na autoria para não chegar um texto numa rota inteira.
                    if isinstance(valor_do_parametro, str) and re.fullmatch(
                        r"\{[A-Za-z][A-Za-z0-9_.-]*\}", valor_do_parametro
                    ):
                        continue
                    tipo = declarados[nome].tipo
                    certo = (
                        (tipo == TipoDeParametroDaRota.TEXTO and isinstance(valor_do_parametro, str))
                        or (
                            tipo == TipoDeParametroDaRota.INTEIRO
                            and isinstance(valor_do_parametro, int)
                            and not isinstance(valor_do_parametro, bool)
                        )
                        or (
                            tipo == TipoDeParametroDaRota.DECIMAL
                            and isinstance(valor_do_parametro, (int, float))
                            and not isinstance(valor_do_parametro, bool)
                        )
                        or (
                            tipo == TipoDeParametroDaRota.BOOLEANO
                            and isinstance(valor_do_parametro, bool)
                        )
                    )
                    if not certo:
                        raise ContratoDoSdkInvalido(
                            f"parametro {nome!r} da rota {nome_da_rota!r} "
                            f"precisa ser {tipo.value}"
                        )
            for filho in valor.values():
                conferir_destinos(filho)

        for superficie in self.superficies:
            conferir_destinos(superficie.tela.compilar())
        if self.conversa is not None:
            for operacao in self.conversa:
                _nome(operacao, "operacao de conversa")
        if self.agente is not None:
            try:
                self.agente.conferir_conversa(self.conversa)
            except AgenteInvalido as erro:
                raise ContratoDoSdkInvalido(str(erro)) from erro
        reservadas = {
            "slug", "endpoint", "forma", "para_tipo", "descricao",
            "descricao_humana", "nome_visivel", "versao", "conversa",
            # ⛔ `navegacao` é o nome COMPILADO de `navegacao_agrupada`. Só o
            # nome Python aqui deixava `extras={"navegacao": ...}` passar por
            # cima da conferência — um grupo apontando para tela inexistente.
            "superficies", "navegacao_agrupada", "navegacao", "rotas", "busca",
            "estados_restauraveis", "historico_de_navegacao",
            "eventos", "avisa_antes", "relata_mudancas",
            "convite", "quer_a_marca", "aceita_contato", "publico",
            "marca_horario", "recebe_documento", "so_por_convite",
            "em_breve", "tipo",
            "tenant_sondagem", "credencial_sondagem", "vitrine_url", "agente",
        }
        conflito = reservadas.intersection(self.extras)
        if conflito:
            raise ContratoDoSdkInvalido(
                "extras do aplicativo repetem campos reservados: "
                + ", ".join(sorted(conflito))
            )

    def compilar(self) -> Json:
        aplicativo: Json = {
            **deepcopy(dict(self.extras)),
            "slug": self.slug,
            "endpoint": self.endpoint,
            "forma": self.forma,
            "descricao": self.descricao,
            "versao": self.versao,
            "superficies": _compilar(self.superficies),
        }
        if self.conversa is not None:
            aplicativo["conversa"] = list(self.conversa)
        if self.navegacao_agrupada is not None:
            aplicativo["navegacao"] = self.navegacao_agrupada.compilar()
        if self.rotas:
            aplicativo["rotas"] = _compilar(self.rotas)
        if self.busca is not None:
            aplicativo["busca"] = self.busca.compilar()
        if self.estados_restauraveis:
            aplicativo["estados_restauraveis"] = _compilar(self.estados_restauraveis)
        if self.historico_de_navegacao is not None:
            aplicativo["historico_de_navegacao"] = self.historico_de_navegacao.compilar()
        opcionais = {
            "para_tipo": self.para_tipo,
            "descricao_humana": self.descricao_humana,
            "nome_visivel": self.nome_visivel,
            "tipo": self.tipo,
            "tenant_sondagem": self.tenant_sondagem,
            "credencial_sondagem": self.credencial_sondagem,
            "vitrine_url": self.vitrine_url,
        }
        aplicativo.update({chave: valor for chave, valor in opcionais.items() if valor is not None})
        compostos = {
            "eventos": self.eventos,
            "avisa_antes": self.avisa_antes,
            "relata_mudancas": self.relata_mudancas,
            "convite": self.convite,
            "quer_a_marca": self.quer_a_marca,
            "aceita_contato": self.aceita_contato,
            "publico": self.publico,
            "marca_horario": self.marca_horario,
        }
        aplicativo.update(
            {chave: valor.compilar() for chave, valor in compostos.items() if valor is not None}
        )
        if self.recebe_documento:
            aplicativo["recebe_documento"] = [
                d.compilar() for d in self.recebe_documento]
        if self.so_por_convite:
            aplicativo["so_por_convite"] = True
        if self.em_breve:
            aplicativo["em_breve"] = True
        if self.agente is not None:
            aplicativo["agente"] = self.agente.compilar()
        return aplicativo


@dataclass(frozen=True, slots=True)
class AplicativoDoContrato:
    """Ponte segura para trazer um manifesto existente ao ciclo do SDK.

    Serve para migrações grandes: mantém o contrato já testado pelo serviço,
    mas o transforma num objeto compilável pelo preview Python e aplica as
    intenções visuais compartilhadas sem editar dezenas de cartões à mão.
    Telas novas devem preferir os componentes tipados acima.
    """

    manifesto: Mapping[str, Any]
    tema_padrao: Tema | None = None
    navegacao: Navegacao | None = Navegacao.INFERIOR

    def __post_init__(self) -> None:
        slug = self.manifesto.get("slug")
        superficies = self.manifesto.get("superficies")
        if not isinstance(slug, str) or not slug.strip():
            raise ContratoDoSdkInvalido("manifesto precisa de slug")
        _nome(slug, "slug")
        if not isinstance(superficies, list) or not superficies:
            raise ContratoDoSdkInvalido("manifesto precisa de superficies")

        nomes: set[str] = set()
        for superficie in superficies:
            if not isinstance(superficie, dict):
                raise ContratoDoSdkInvalido("cada superficie precisa ser um objeto")
            nome = superficie.get("nome")
            if not isinstance(nome, str):
                raise ContratoDoSdkInvalido("superficie precisa de nome")
            _nome(nome, "nome da superficie")
            if nome in nomes:
                raise ContratoDoSdkInvalido(f"superficie repetida: {nome}")
            nomes.add(nome)
            cartao = superficie.get("cartao")
            if not isinstance(cartao, dict) or cartao.get("type") != "AdaptiveCard":
                raise ContratoDoSdkInvalido(
                    f"superficie {nome!r} precisa de um AdaptiveCard"
                )
            if not isinstance(cartao.get("body"), list) or not cartao["body"]:
                raise ContratoDoSdkInvalido(
                    f"superficie {nome!r} precisa de corpo"
                )

    def compilar(self) -> Json:
        manifesto = deepcopy(dict(self.manifesto))
        for superficie in manifesto["superficies"]:
            cartao = superficie["cartao"]
            if self.tema_padrao is not None:
                cartao.setdefault("okmigoTema", self.tema_padrao.value)
            if self.navegacao is not None:
                cartao.setdefault("okmigoNavegacao", self.navegacao.value)
        return manifesto
