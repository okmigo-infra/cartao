"""Componentes de LEITURA DE DADOS — ranking, tendência, comparação e estado.

Os módulos vizinhos cobrem formulário, navegação e finanças pessoais. Falta a
família que um produto de DADOS precisa: uma lista ordenada por um critério
declarado, uma tendência que cabe numa linha, uma ficha que abre sobre o
contexto, uma comparação lado a lado e — o mais esquecido — a maneira de dizer
que o número na tela está VELHO.

⛔ Nenhum nome aqui pertence a um produto. `Ranking` serve a ativo, produto,
jogador e chamado; `EstadoDoDado` serve a qualquer tela que leia cache. Um
componente que só o autor de um app entenderia não é vocabulário público.

⭐ Duas regras atravessam o módulo inteiro:

1. **Cor nunca é a única pista.** Toda variação carrega o TEXTO já formatado
   pelo serviço (`↑ +2,4%`), e o `tom` é redundância, não informação. Quem lê
   em preto e branco, com daltonismo ou por leitor de tela recebe o mesmo.
2. **Todo componente novo traz `fallback`.** O cliente velho não conhece
   `okmigoRanking`; sem o `fallback` a lista inteira sumiria em silêncio no
   aparelho que ainda não atualizou. O `fallback` é escrito em nós que o
   contrato tem desde o começo — texto, fatos e caixa.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .componentes_avancados import (
    Etiqueta,
    MenuDeAcoes,
    TomDaEtiqueta,
)
from .sdk import (
    Acao,
    Componente,
    ContratoDoSdkInvalido,
    Fato,
    Fatos,
    PapelDoTexto,
    Texto,
    TipoDeAcao,
    _compilar,
    _nome,
)

Json = dict[str, object]

#: Tetos do SDK. O crivo repete cada um — ele é a fronteira, e uma trava que só
#: existe aqui é uma trava que o serviço contorna mandando o JSON à mão.
MAX_PONTOS_DA_TENDENCIA = 48
MAX_ITENS_DO_RANKING = 50
MAX_ITENS_COMPARADOS = 4
MAX_CRITERIOS_COMPARADOS = 24
MAX_ITENS_DA_AGENDA = 120
MAX_ETIQUETAS_DO_CABECALHO = 4


def _obrigatorio(valor: str, papel: str) -> str:
    if not valor.strip():
        raise ContratoDoSdkInvalido(f"{papel} nao pode ser vazio")
    return valor


def _so_leitura(acao: Acao | None, papel: str) -> Acao | None:
    """Componente de leitura não escreve na conta de ninguém.

    ⛔ Um toque num item de ranking é `Action.Execute` — consulta. Aceitar
    escrita aqui daria ao autor um botão de gravar disfarçado de linha de
    lista, que é exatamente o gesto que a pessoa não sabe que deu.
    """
    if acao is not None and acao.tipo != TipoDeAcao.LEITURA:
        raise ContratoDoSdkInvalido(f"{papel} pode apenas consultar")
    return acao


# ── Tendência numa linha ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Minigrafico:
    """A tendência que cabe ao lado de um número, sem eixo nem legenda.

    É o `okmigoGrafico` sem a moldura: não há título, rótulo de ponto nem
    escala visível — só a FORMA da série. Por isso a `alternativa` é
    obrigatória e não tem padrão: um desenho de 40 px sem texto é um dado que
    existe para quem enxerga e não existe para o resto.
    """

    valores: tuple[float | int, ...]
    alternativa: str
    rotulo: str = ""
    tom: TomDaEtiqueta = TomDaEtiqueta.NEUTRO

    def __post_init__(self) -> None:
        _obrigatorio(self.alternativa, "alternativa textual da tendencia")
        numeros = [v for v in self.valores if isinstance(v, (int, float))]
        if len(numeros) < 2:
            raise ContratoDoSdkInvalido("tendencia precisa de ao menos dois pontos")
        if len(self.valores) > MAX_PONTOS_DA_TENDENCIA:
            raise ContratoDoSdkInvalido(
                f"tendencia aceita ate {MAX_PONTOS_DA_TENDENCIA} pontos"
            )

    def compilar(self) -> Json:
        return {
            "type": "okmigoMinigrafico",
            "rotulo": self.rotulo,
            "valores": list(self.valores),
            "tom": self.tom.value,
            "alternativa": self.alternativa,
            "fallback": Texto(self.alternativa, PapelDoTexto.AUXILIAR).compilar(),
        }


# ── Ranking ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ItemDeRanking:
    """Uma posição da lista. A `posicao` é do RANKING, não do item.

    Quem numera é o componente, na ordem recebida — item que traz o próprio
    número consegue mentir sobre a ordem (dois «1º», um «3º» sem «2º»), e o
    leitor acredita no número impresso, não na sequência.
    """

    rotulo: str
    valor: str
    apoio: str = ""
    variacao: str = ""
    tom: TomDaEtiqueta = TomDaEtiqueta.NEUTRO
    id: str = ""
    tendencia: Minigrafico | None = None
    ao_tocar: Acao | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.rotulo, "rotulo do item de ranking")
        _obrigatorio(self.valor, "valor do item de ranking")
        _so_leitura(self.ao_tocar, "item de ranking")

    def compilar(self) -> Json:
        item: Json = {
            "rotulo": self.rotulo,
            "valor": self.valor,
            "apoio": self.apoio,
            "variacao": self.variacao,
            "tom": self.tom.value,
            "id": self.id,
        }
        if self.tendencia is not None:
            item["tendencia"] = self.tendencia.compilar()
        if self.ao_tocar is not None:
            item["aoTocar"] = self.ao_tocar.compilar()
        return item


@dataclass(frozen=True, slots=True)
class Ranking:
    """Lista ordenada por um critério que o serviço é obrigado a declarar.

    ⛔ `criterio` e `base` não são decoração: uma lista ordenada sem dizer POR
    QUE e DE QUANDO é a forma mais fácil de transformar dado bruto em conselho.
    «Maiores altas» sem data-base e sem universo não é informação — é palpite
    com aparência de tabela. Por isso os dois campos são obrigatórios.
    """

    titulo: str
    criterio: str
    itens: tuple[ItemDeRanking, ...]
    base: str = ""
    universo: str = ""
    nota: str = ""
    ver_todos: Acao | None = None
    #: Nome da sublista do dado sobre a qual o PRIMEIRO item é repetido.
    #:
    #: ⭐ Sem isto, um ranking só serve para dado fixo escrito no código —
    #: e um ranking de mercado é, por definição, dinâmico. Com `itens_de`, o
    #: primeiro item vira o MOLDE e a ponte o expande uma vez por linha da
    #: sublista, do mesmo jeito que `Repetir` faz com qualquer componente.
    itens_de: str | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo do ranking")
        _obrigatorio(self.criterio, "criterio do ranking")
        if not self.itens:
            raise ContratoDoSdkInvalido("ranking precisa de ao menos um item")
        if self.itens_de is not None:
            _nome(self.itens_de, "sublista do ranking")
        if len(self.itens) > MAX_ITENS_DO_RANKING:
            raise ContratoDoSdkInvalido(
                f"ranking aceita ate {MAX_ITENS_DO_RANKING} itens"
            )
        _so_leitura(self.ver_todos, "ver todos do ranking")

    def compilar(self) -> Json:
        # O fallback é a mesma lista em `FactSet`: o cliente velho perde a
        # posição desenhada e o sparkline, e continua com rótulo → valor.
        fatos = Fatos(
            tuple(
                Fato(
                    f"{i}. {item.rotulo}",
                    " · ".join(p for p in (item.valor, item.variacao) if p),
                )
                for i, item in enumerate(self.itens, start=1)
            )
        )
        compilado: Json = {
            "type": "okmigoRanking",
            "titulo": self.titulo,
            "criterio": self.criterio,
            "base": self.base,
            "universo": self.universo,
            "nota": self.nota,
            "itens": (
                # O molde: a ponte expande uma cópia por linha da sublista.
                [{"_repetir_lista": self.itens[0].compilar(), "_de": self.itens_de}]
                if self.itens_de is not None
                else [item.compilar() for item in self.itens]
            ),
            "fallback": fatos.compilar(),
        }
        if self.ver_todos is not None:
            compilado["verTodos"] = self.ver_todos.compilar()
        return compilado


# ── Cabeçalho de uma ficha ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CabecalhoDeDetalhe:
    """O topo de um detalhe: identidade, número principal e as ações de sempre.

    Existe porque toda ficha repetia a mesma composição à mão — título, valor,
    variação, etiquetas e um botão de favorito — e cada repetição escolhia uma
    ordem de leitura diferente. Aqui a ordem é do componente, e o cliente
    garante que o foco de teclado passa pelo favorito antes do menu.
    """

    titulo: str
    valor: str = ""
    subtitulo: str = ""
    variacao: str = ""
    tom: TomDaEtiqueta = TomDaEtiqueta.NEUTRO
    base: str = ""
    etiquetas: tuple[Etiqueta, ...] = ()
    destacar: Acao | None = None
    destacado: bool = False
    desfazer_destaque: Acao | None = None
    menu: MenuDeAcoes | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo do cabecalho")
        if len(self.etiquetas) > MAX_ETIQUETAS_DO_CABECALHO:
            raise ContratoDoSdkInvalido(
                f"cabecalho aceita ate {MAX_ETIQUETAS_DO_CABECALHO} etiquetas"
            )
        # ⭐ `destacar` é a ÚNICA ação de escrita tolerada num componente de
        # leitura, e é escrita na conta de quem toca — favoritar. Continua
        # sendo uma operação declarada, conferida pelo crivo como qualquer
        # outra; o que o componente garante é que ela não se disfarça de link.

    def compilar(self) -> Json:
        linhas = [self.titulo]
        if self.subtitulo:
            linhas.append(self.subtitulo)
        resumo = " · ".join(p for p in (self.valor, self.variacao, self.base) if p)
        if resumo:
            linhas.append(resumo)
        compilado: Json = {
            "type": "okmigoCabecalhoDeDetalhe",
            "titulo": self.titulo,
            "subtitulo": self.subtitulo,
            "valor": self.valor,
            "variacao": self.variacao,
            "tom": self.tom.value,
            "base": self.base,
            "etiquetas": _compilar(self.etiquetas),
            "destacado": self.destacado,
            "fallback": Texto("\n".join(linhas), PapelDoTexto.TITULO).compilar(),
        }
        if self.destacar is not None:
            compilado["destacar"] = self.destacar.compilar()
        if self.desfazer_destaque is not None:
            compilado["desfazerDestaque"] = self.desfazer_destaque.compilar()
        if self.menu is not None:
            compilado["menu"] = self.menu.compilar()
        return compilado


# ── O estado do dado ────────────────────────────────────────────────────────


class EstadoDaInformacao(StrEnum):
    """Por que a tela não tem o número que deveria ter.

    ⛔ `VAZIO` e `DESATUALIZADO` não são o mesmo estado, e tratá-los como um só
    foi o defeito que este componente existe para impedir: «nenhum dado» diz à
    pessoa que não há nada, quando o que houve foi o coletor parar às 3 da
    manhã. A distinção muda o gesto — esperar, recarregar, ou entender que
    aquele dado não existe para aquela classe de item.
    """

    CARREGANDO = "carregando"
    VAZIO = "vazio"
    PARCIAL = "parcial"
    DESATUALIZADO = "desatualizado"
    ERRO = "erro"
    OFFLINE = "offline"
    SEM_PERMISSAO = "sem_permissao"
    NAO_APLICAVEL = "nao_aplicavel"


@dataclass(frozen=True, slots=True)
class EstadoDoDado:
    """O aviso honesto sobre o que a tela está mostrando.

    Irmão do `EstadoVazio`, que continua valendo para a lista sem nenhum item.
    Este cobre os outros sete casos, e o `base` carrega a data que transforma
    «desatualizado» de adjetivo em fato conferível.
    """

    situacao: EstadoDaInformacao
    titulo: str
    explicacao: str = ""
    base: str = ""
    acao: Acao | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo do estado do dado")

    def compilar(self) -> Json:
        texto = " — ".join(p for p in (self.titulo, self.explicacao, self.base) if p)
        compilado: Json = {
            "type": "okmigoEstadoDoDado",
            "situacao": self.situacao.value,
            "titulo": self.titulo,
            "explicacao": self.explicacao,
            "base": self.base,
            "fallback": Texto(texto, PapelDoTexto.AUXILIAR).compilar(),
        }
        if self.acao is not None:
            compilado["acao"] = self.acao.compilar()
        return compilado


# ── Comparação lado a lado ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ItemComparado:
    rotulo: str
    apoio: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        _obrigatorio(self.rotulo, "rotulo do item comparado")

    def compilar(self) -> Json:
        return {"rotulo": self.rotulo, "apoio": self.apoio, "id": self.id}


@dataclass(frozen=True, slots=True)
class CriterioComparado:
    """Uma linha da comparação: os valores casam com os itens por ÍNDICE.

    ⛔ Valor faltando é `""`, e o componente desenha «—»: encurtar a lista
    deslocaria a coluna e o número de um item apareceria embaixo de outro. É a
    mesma regra do `okmigoGrafico`, pelo mesmo motivo.
    """

    rotulo: str
    valores: tuple[str, ...]
    explicacao: str = ""
    melhor: int | None = None
    rotulo_do_melhor: str = "destaque"

    def __post_init__(self) -> None:
        _obrigatorio(self.rotulo, "rotulo do criterio")
        # ⛔ O rótulo do destaque é DECLARADO porque «melhor» depende do
        # critério, e o cliente não sabe qual. A tela mostrou isto: com o
        # texto fixo «maior», o menor P/L — que é o extremo desejável —
        # aparecia rotulado como «maior» ao lado de 5,10x contra 8,20x.
        if self.melhor is not None:
            _obrigatorio(self.rotulo_do_melhor, "rotulo do destaque")
        if self.melhor is not None and not 0 <= self.melhor < len(self.valores):
            raise ContratoDoSdkInvalido("indice de melhor fora dos valores")

    def compilar(self) -> Json:
        compilado: Json = {
            "rotulo": self.rotulo,
            "valores": [v or "" for v in self.valores],
            "explicacao": self.explicacao,
        }
        if self.melhor is not None:
            compilado["melhor"] = self.melhor
            compilado["rotuloDoMelhor"] = self.rotulo_do_melhor
        return compilado


@dataclass(frozen=True, slots=True)
class Comparador:
    """Itens em colunas, critérios em linhas, sem eleger um vencedor.

    ⛔ `melhor` marca o extremo de UM critério e o cliente é obrigado a
    rotulá-lo por texto («maior»), nunca só por cor. Não existe campo de nota
    final: somar critérios de naturezas diferentes num score é produzir uma
    recomendação, e este é um componente de leitura.
    """

    titulo: str
    itens: tuple[ItemComparado, ...]
    criterios: tuple[CriterioComparado, ...]
    base: str = ""
    nota: str = ""

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo do comparador")
        if not 2 <= len(self.itens) <= MAX_ITENS_COMPARADOS:
            raise ContratoDoSdkInvalido(
                f"comparador aceita de 2 a {MAX_ITENS_COMPARADOS} itens"
            )
        if not self.criterios:
            raise ContratoDoSdkInvalido("comparador precisa de ao menos um criterio")
        if len(self.criterios) > MAX_CRITERIOS_COMPARADOS:
            raise ContratoDoSdkInvalido(
                f"comparador aceita ate {MAX_CRITERIOS_COMPARADOS} criterios"
            )
        for criterio in self.criterios:
            if len(criterio.valores) != len(self.itens):
                raise ContratoDoSdkInvalido(
                    f"criterio {criterio.rotulo!r} tem "
                    f"{len(criterio.valores)} valores para {len(self.itens)} itens"
                )

    def compilar(self) -> Json:
        cabecalho = " × ".join(item.rotulo for item in self.itens)
        fatos = Fatos(
            tuple(
                Fato(
                    criterio.rotulo,
                    " · ".join(v or "—" for v in criterio.valores),
                )
                for criterio in self.criterios
            )
        )
        return {
            "type": "okmigoComparador",
            "titulo": self.titulo,
            "base": self.base,
            "nota": self.nota,
            "itens": [item.compilar() for item in self.itens],
            "criterios": [criterio.compilar() for criterio in self.criterios],
            "fallback": {
                "type": "Container",
                "items": [
                    Texto(f"{self.titulo}: {cabecalho}", PapelDoTexto.SECAO).compilar(),
                    fatos.compilar(),
                ],
            },
        }


# ── Agenda ──────────────────────────────────────────────────────────────────


class EstadoDoCompromisso(StrEnum):
    """O quanto se sabe sobre um evento futuro.

    ⛔ `PREVISTO` nunca é desenhado como `CONFIRMADO`. Um pagamento anunciado
    pela companhia e uma projeção do próprio serviço têm pesos diferentes para
    quem planeja o mês, e a tela que os iguala mente por omissão.
    """

    CONFIRMADO = "confirmado"
    ANUNCIADO = "anunciado"
    PREVISTO = "previsto"
    REALIZADO = "realizado"
    SEM_DATA = "sem_data"
    CANCELADO = "cancelado"


@dataclass(frozen=True, slots=True)
class ItemDaAgenda:
    data: str
    titulo: str
    apoio: str = ""
    valor: str = ""
    estado: EstadoDoCompromisso = EstadoDoCompromisso.ANUNCIADO
    id: str = ""
    ao_tocar: Acao | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo do item da agenda")
        if self.estado is not EstadoDoCompromisso.SEM_DATA:
            _obrigatorio(self.data, "data do item da agenda")
        _so_leitura(self.ao_tocar, "item da agenda")

    def compilar(self) -> Json:
        item: Json = {
            "data": self.data,
            "titulo": self.titulo,
            "apoio": self.apoio,
            "valor": self.valor,
            "estado": self.estado.value,
            "id": self.id,
        }
        if self.ao_tocar is not None:
            item["aoTocar"] = self.ao_tocar.compilar()
        return item


@dataclass(frozen=True, slots=True)
class Agenda:
    """A lista do que vem por data — o irmão de lista do `okmigoCalendario`.

    A grade de mês responde «o que cai no dia 12?»; a agenda responde «o que
    vem agora?». São perguntas diferentes e por isso são dois componentes: em
    telefone a grade de 30 células é ilegível, e forçar a agenda dentro dela
    foi o que fez a tela de proventos caber em nenhum dos dois.
    """

    titulo: str
    itens: tuple[ItemDaAgenda, ...]
    base: str = ""
    vazio: str = "Nada agendado para o período."
    agrupar_por_data: bool = True
    #: Como em `Ranking`: o primeiro item vira molde e a ponte o repete.
    itens_de: str | None = None

    def __post_init__(self) -> None:
        _obrigatorio(self.titulo, "titulo da agenda")
        if self.itens_de is not None:
            if not self.itens:
                raise ContratoDoSdkInvalido("agenda com `itens_de` precisa de um molde")
            _nome(self.itens_de, "sublista da agenda")
        if len(self.itens) > MAX_ITENS_DA_AGENDA:
            raise ContratoDoSdkInvalido(
                f"agenda aceita ate {MAX_ITENS_DA_AGENDA} itens"
            )

    def compilar(self) -> Json:
        # Agenda sem item não some: o vazio de uma agenda é informação («não há
        # provento anunciado»), diferente de uma tabela que ficou só com o
        # cabeçalho por acidente de repetição.
        if self.itens:
            corpo: Componente = Fatos(
                tuple(
                    Fato(
                        item.data or "sem data",
                        " · ".join(p for p in (item.titulo, item.valor) if p),
                    )
                    for item in self.itens
                )
            )
        else:
            corpo = Texto(self.vazio, PapelDoTexto.AUXILIAR)
        return {
            "type": "okmigoAgenda",
            "titulo": self.titulo,
            "base": self.base,
            "vazio": self.vazio,
            "agruparPorData": self.agrupar_por_data,
            "itens": (
                [{"_repetir_lista": self.itens[0].compilar(), "_de": self.itens_de}]
                if self.itens_de is not None
                else [item.compilar() for item in self.itens]
            ),
            "fallback": {
                "type": "Container",
                "items": [
                    Texto(self.titulo, PapelDoTexto.SECAO).compilar(),
                    corpo.compilar(),
                ],
            },
        }


__all__ = [
    "MAX_CRITERIOS_COMPARADOS",
    "MAX_ETIQUETAS_DO_CABECALHO",
    "MAX_ITENS_COMPARADOS",
    "MAX_ITENS_DA_AGENDA",
    "MAX_ITENS_DO_RANKING",
    "MAX_PONTOS_DA_TENDENCIA",
    "Agenda",
    "CabecalhoDeDetalhe",
    "Comparador",
    "CriterioComparado",
    "EstadoDaInformacao",
    "EstadoDoCompromisso",
    "EstadoDoDado",
    "ItemComparado",
    "ItemDaAgenda",
    "ItemDeRanking",
    "Minigrafico",
    "Ranking",
]
