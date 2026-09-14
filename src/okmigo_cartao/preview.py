"""Galeria local para conferir uma tela do SDK antes de ligá-la ao produto.

O preview executa um alvo Python local, compila o SDK, expande os dados e só
desenha a árvore reconstruída pelo crivo. Ele não abre uma nova fronteira do
contrato: ações são simuladas no navegador e nunca fazem requisição externa.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

from .casca import expandir
from .crivo import Config, validar
from .manifesto import e_manifesto

Json = dict[str, Any]


class ErroDePreview(ValueError):
    """Entrada local que não consegue virar uma tela conferida."""


def _separar_alvo(alvo: str) -> tuple[Path, str]:
    arquivo, separador, fabrica = alvo.rpartition(":")
    if not separador or not arquivo or not fabrica:
        raise ErroDePreview(
            "o alvo precisa ter a forma arquivo.py:objeto, por exemplo "
            "exemplos/sdk_radaria.py:tela_de_ativos"
        )
    caminho = Path(arquivo).expanduser().resolve()
    if caminho.suffix != ".py":
        raise ErroDePreview("o alvo do SDK precisa apontar para um arquivo .py")
    if not caminho.is_file():
        raise ErroDePreview(f"arquivo não encontrado: {caminho}")
    return caminho, fabrica


def _carregar_modulo(caminho: Path) -> ModuleType:
    nome = f"_okmigo_preview_{abs(hash(caminho))}"
    spec = importlib.util.spec_from_file_location(nome, caminho)
    if spec is None or spec.loader is None:
        raise ErroDePreview(f"não consegui importar {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _compilar_objeto(objeto: Any, nome: str) -> Json:
    resultado = objeto() if callable(objeto) else objeto
    if hasattr(resultado, "compilar") and callable(resultado.compilar):
        resultado = resultado.compilar()
    if not isinstance(resultado, dict):
        raise ErroDePreview(
            f"{nome} precisa ser Tela, Aplicativo, uma fábrica ou dict; "
            f"recebi {type(resultado).__name__}"
        )
    return resultado


def carregar_alvo(alvo: str) -> Json:
    """Carrega ``arquivo.py:objeto`` e devolve o cartão/app bruto compilado."""
    caminho, fabrica = _separar_alvo(alvo)
    modulo = _carregar_modulo(caminho)
    objeto = getattr(modulo, fabrica, None)
    if objeto is None:
        raise ErroDePreview(f"{fabrica!r} não existe em {caminho}")
    return _compilar_objeto(objeto, fabrica)


def _respostas_do_preview(
    modulo: ModuleType | None,
    dados: Json,
    escrituras: frozenset[str],
    leituras: frozenset[str],
) -> list[Json]:
    """Compila respostas locais de operações sem colocá-las no manifesto.

    O JSON fornece somente conteúdo de demonstração e o nome da fábrica Python.
    O layout continua vindo do SDK e cada resposta passa pelo mesmo crivo.
    """
    configuracao = dados.get("_preview") or {}
    if not configuracao:
        return []
    if modulo is None or not isinstance(configuracao, dict):
        raise ErroDePreview("respostas do preview exigem um alvo Python")
    declaracoes = configuracao.get("respostas") or []
    if not isinstance(declaracoes, list) or len(declaracoes) > 20:
        raise ErroDePreview("_preview.respostas precisa ser uma lista de até 20 itens")

    respostas: list[Json] = []
    for declaracao in declaracoes:
        if not isinstance(declaracao, dict):
            raise ErroDePreview("cada resposta do preview precisa ser um objeto")
        operacao = str(declaracao.get("operacao") or "")
        fabrica = str(declaracao.get("fabrica") or "")
        campo = str(declaracao.get("campo") or "ticker")
        voltar_para = str(declaracao.get("voltar_para") or "")
        exemplos = declaracao.get("exemplos") or []
        if operacao not in leituras or not fabrica or not voltar_para:
            raise ErroDePreview(
                "resposta precisa nomear uma leitura, fábrica e superfície de volta"
            )
        if not isinstance(exemplos, list) or len(exemplos) > 20:
            raise ErroDePreview("resposta aceita uma lista de até 20 exemplos")
        funcao = getattr(modulo, fabrica, None)
        if not callable(funcao):
            raise ErroDePreview(f"fábrica de resposta {fabrica!r} não encontrada")
        for exemplo in exemplos:
            if not isinstance(exemplo, dict) or campo not in exemplo:
                raise ErroDePreview(
                    f"cada exemplo de {operacao!r} precisa do campo {campo!r}"
                )
            bruto = funcao(exemplo)
            if hasattr(bruto, "compilar") and callable(bruto.compilar):
                bruto = bruto.compilar()
            if not isinstance(bruto, dict):
                raise ErroDePreview(f"{fabrica} não devolveu uma Tela compilável")
            tela, erro = validar(bruto, escrituras, leituras, config=Config())
            if erro or tela is None:
                raise ErroDePreview(
                    f"resposta {operacao!r} recusada pelo crivo: {erro or 'sem corpo'}"
                )
            respostas.append(
                {
                    "operacao": operacao,
                    "campo": campo,
                    "valor": str(exemplo[campo]),
                    "voltar_para": voltar_para,
                    "tela": tela,
                }
            )
    return respostas


def _dados(caminho: Path | None) -> tuple[Json, list[Any]]:
    if caminho is None:
        return {}, []
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise ErroDePreview(f"arquivo de dados não encontrado: {caminho}") from erro
    except json.JSONDecodeError as erro:
        raise ErroDePreview(
            f"JSON inválido em {caminho}:{erro.lineno}:{erro.colno}: {erro.msg}"
        ) from erro
    if isinstance(bruto, list):
        return {}, bruto
    if not isinstance(bruto, dict):
        raise ErroDePreview("--dados precisa conter {resumo, linhas} ou uma lista")
    linhas = bruto.get("linhas") or []
    if not isinstance(linhas, list):
        raise ErroDePreview("dados.linhas precisa ser uma lista")
    resumo = bruto.get("resumo") or {}
    if not isinstance(resumo, dict):
        raise ErroDePreview("dados.resumo precisa ser um objeto")
    return resumo, linhas


def inferir_operacoes(cartao: Any) -> tuple[frozenset[str], frozenset[str]]:
    """Extrai o contrato mínimo do código local para a conferência do piloto."""
    escrituras: set[str] = set()
    leituras: set[str] = set()

    def visitar(valor: Any) -> None:
        if isinstance(valor, list):
            for item in valor:
                visitar(item)
            return
        if not isinstance(valor, dict):
            return
        tipo = valor.get("type")
        dados = valor.get("data")
        operacao = dados.get("operacao") if isinstance(dados, dict) else None
        if isinstance(operacao, str) and operacao:
            if tipo == "Action.Submit":
                escrituras.add(operacao)
            elif tipo == "Action.Execute":
                leituras.add(operacao)
        buscar = valor.get("okmigoBuscar")
        if isinstance(buscar, str) and buscar:
            leituras.add(buscar)
        # Blocos nativos também nomeiam capacidades sem usar Action.*. É o
        # caso do calendário: arrastar um evento leva ``enviar``. A inferência
        # precisa enxergar essa escrita para o preview conferir o mesmo
        # contrato que o renderer real confere.
        enviar = valor.get("enviar")
        if isinstance(enviar, str) and enviar:
            escrituras.add(enviar)
        consultar = valor.get("consultar")
        if isinstance(consultar, str) and consultar:
            leituras.add(consultar)
        for filho in valor.values():
            visitar(filho)

    visitar(cartao)
    return frozenset(escrituras), frozenset(leituras)


def construir_tela(
    alvo: str,
    dados: Path | None,
    *,
    escrituras: frozenset[str] | None = None,
    leituras: frozenset[str] | None = None,
) -> tuple[Json, frozenset[str], frozenset[str]]:
    bruto = carregar_alvo(alvo)
    inferidas_escrita, inferidas_leitura = inferir_operacoes(bruto)
    resumo, linhas = _dados(dados)
    if dados is not None:
        bruto = expandir(bruto, resumo, linhas)
    esc = inferidas_escrita if escrituras is None else escrituras
    lei = inferidas_leitura if leituras is None else leituras
    tela, erro = validar(bruto, esc, lei, config=Config())
    if erro or tela is None:
        raise ErroDePreview(f"tela recusada pelo crivo: {erro or 'sem corpo'}")
    return tela, esc, lei


def construir_aplicativo(
    alvo: str,
    dados: Path | None,
    *,
    escrituras: frozenset[str] | None = None,
    leituras: frozenset[str] | None = None,
) -> tuple[Json, frozenset[str], frozenset[str]]:
    """Carrega um Aplicativo/manifesto ou embrulha uma Tela como app de 1 tela."""
    modulo: ModuleType | None = None
    if ":" in alvo:
        caminho, nome_do_objeto = _separar_alvo(alvo)
        modulo = _carregar_modulo(caminho)
        objeto = getattr(modulo, nome_do_objeto, None)
        if objeto is None:
            raise ErroDePreview(f"{nome_do_objeto!r} não existe em {caminho}")
        compilado = _compilar_objeto(objeto, nome_do_objeto)
        if not e_manifesto(compilado):
            tela, esc, lei = construir_tela(
                alvo, dados, escrituras=escrituras, leituras=leituras
            )
            return (
                {
                    "nome": caminho.stem,
                    "atual": "preview",
                    "superficies": [
                        {
                            "nome": "preview",
                            "rotulo": "Preview",
                            "icone": "ativos",
                            "tela": tela,
                        }
                    ],
                },
                esc,
                lei,
            )
        manifesto = compilado
    else:
        caminho = Path(alvo).expanduser().resolve()
        try:
            manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        except FileNotFoundError as erro:
            raise ErroDePreview(f"manifesto não encontrado: {caminho}") from erro
        except json.JSONDecodeError as erro:
            raise ErroDePreview(
                f"JSON inválido em {caminho}:{erro.lineno}:{erro.colno}: {erro.msg}"
            ) from erro
    if not e_manifesto(manifesto):
        raise ErroDePreview(
            "sem ':objeto', o alvo precisa ser um manifesto com superficies"
        )

    dados_lidos: Json = {}
    dados_do_app: Json = {}
    if dados is not None:
        try:
            lidos = json.loads(dados.read_text(encoding="utf-8"))
        except FileNotFoundError as erro:
            raise ErroDePreview(f"arquivo de dados não encontrado: {dados}") from erro
        except json.JSONDecodeError as erro:
            raise ErroDePreview(
                f"JSON inválido em {dados}:{erro.lineno}:{erro.colno}: {erro.msg}"
            ) from erro
        if not isinstance(lidos, dict):
            raise ErroDePreview(
                "para um manifesto, --dados precisa mapear cada nome de superfície"
            )
        dados_lidos = lidos
        dados_do_app = lidos.get("superficies", lidos)
        if not isinstance(dados_do_app, dict):
            raise ErroDePreview("dados.superficies precisa ser um objeto")

    brutos: list[tuple[Json, Json]] = []
    inferidas_escrita: set[str] = set()
    inferidas_leitura: set[str] = set()
    for superficie in manifesto.get("superficies") or []:
        if not isinstance(superficie, dict) or not isinstance(
            superficie.get("cartao"), dict
        ):
            continue
        cartao = superficie["cartao"]
        brutos.append((superficie, cartao))
        esc, lei = inferir_operacoes(cartao)
        inferidas_escrita.update(esc)
        inferidas_leitura.update(lei)
    if not brutos:
        raise ErroDePreview("o manifesto não tem nenhuma superfície com cartão")

    esc_final = frozenset(inferidas_escrita) if escrituras is None else escrituras
    lei_final = frozenset(inferidas_leitura) if leituras is None else leituras
    prontas = []
    for superficie, molde in brutos:
        nome = str(superficie.get("nome") or "")
        dado = dados_do_app.get(nome, {})
        if dado and not isinstance(dado, dict):
            raise ErroDePreview(f"os dados de {nome!r} precisam ser um objeto")
        resumo = (dado or {}).get("resumo") or {}
        linhas = (dado or {}).get("linhas") or []
        if not isinstance(resumo, dict) or not isinstance(linhas, list):
            raise ErroDePreview(
                f"os dados de {nome!r} precisam ter resumo objeto e linhas lista"
            )
        bruto = expandir(molde, resumo, linhas)
        tela, erro = validar(bruto, esc_final, lei_final, config=Config())
        if erro and not dado and "nenhum elemento" in erro:
            # Algumas telas são integralmente dirigidas por dados (uma tabela
            # sem título, por exemplo). Sem fixture o preview não deve apagar
            # a rota inteira: mantém o destino navegável e explicita que falta
            # conteúdo de demonstração. Com dados fornecidos, qualquer erro
            # continua sendo fatal.
            substituto = {
                "type": "AdaptiveCard",
                "version": "1.5",
                "okmigoTema": molde.get("okmigoTema"),
                "okmigoNavegacao": molde.get("okmigoNavegacao"),
                "body": [
                    {"type": "TextBlock", "text": str(superficie.get("titulo") or nome), "size": "large", "weight": "bolder"},
                    {"type": "TextBlock", "text": "Adicione dados de demonstração para visualizar o conteúdo desta tela.", "wrap": True, "isSubtle": True},
                ],
            }
            tela, erro = validar(substituto, esc_final, lei_final, config=Config())
        if erro or tela is None:
            raise ErroDePreview(
                f"superfície {nome!r} recusada pelo crivo: {erro or 'sem corpo'}"
            )
        prontas.append(
            {
                "nome": nome,
                "rotulo": str(
                    superficie.get("rotulo_superficie")
                    or superficie.get("rotulo")
                    or superficie.get("titulo")
                    or nome
                )[:24],
                "icone": str(superficie.get("icone") or nome)[:30],
                "tela": tela,
            }
        )
    respostas = _respostas_do_preview(modulo, dados_lidos, esc_final, lei_final)
    return (
        {
            "nome": str(
                manifesto.get("nome_visivel") or manifesto.get("slug") or caminho.stem
            )[:40],
            "atual": prontas[0]["nome"],
            "superficies": prontas,
            "respostas": respostas,
        },
        esc_final,
        lei_final,
    )


def _e(valor: Any) -> str:
    return html.escape(str(valor or ""), quote=True)


def _atributos_acao(acao: Json) -> str:
    operacao = acao.get("consultar") or acao.get("enviar") or "alternar"
    campos = json.dumps(acao.get("campos") or [], ensure_ascii=False)
    destrutiva = "true" if acao.get("enfase") == "destrutiva" else "false"
    return (
        f'data-operacao="{_e(operacao)}" '
        f'data-campos="{_e(campos)}" '
        f'data-destrutiva="{destrutiva}"'
    )


def _texto_visivel(itens: list[Json]) -> str:
    return " ".join(
        str(item.get("texto") or "") for item in itens if item.get("tipo") == "texto"
    ).strip()


def _render_texto(no: Json) -> str:
    tamanho = no.get("tamanho", "default")
    classe = ["texto", f"texto-{_e(tamanho)}"]
    if no.get("peso") == "bolder":
        classe.append("negrito")
    if no.get("discreto"):
        classe.append("discreto")
    alinhamento = no.get("alinhamento")
    if alinhamento in {"left", "center", "right"}:
        classe.append(f"alinhamento-{alinhamento}")
    conteudo = _e(no.get("texto"))
    if tamanho == "extraLarge":
        tag = "h1"
    elif tamanho == "large":
        tag = "h2"
    else:
        tag = "p"
    return f'<{tag} class="{" ".join(classe)}">{conteudo}</{tag}>'


def _render_acao(acao: Json, *, extra: str = "") -> str:
    enfase = _e(acao.get("enfase") or "padrao")
    titulo = _e(acao.get("titulo") or "Executar")
    icone = ""
    if acao.get("icone") == "lixeira":
        icone = '<span aria-hidden="true" class="icone-lixeira"></span>'
    return (
        f'<button type="button" class="acao acao-{enfase} {extra}" '
        f"{_atributos_acao(acao)}>{icone}<span>{titulo}</span></button>"
    )


def _render_tabela(no: Json) -> str:
    linhas = no.get("linhas") or []
    if not linhas:
        return ""
    tem_cabecalho = bool(no.get("cabecalho"))
    cabecalho = linhas[0] if tem_cabecalho else None
    dados = linhas[1:] if tem_cabecalho else linhas
    rotulos = (
        [_texto_visivel(c.get("itens") or []) for c in cabecalho.get("celulas") or []]
        if cabecalho
        else []
    )
    larguras = [max(1, int(c.get("largura") or 1)) for c in no.get("colunas") or []]
    estilo = " ".join(f"minmax(0,{largura}fr)" for largura in larguras)
    partes = [
        (
            f'<div class="tabela" role="table" style="--colunas:{_e(estilo)}" '
            'aria-label="Ativos acompanhados">'
        )
    ]
    if cabecalho:
        partes.append('<div class="linha-tabela cabecalho-tabela" role="row">')
        for celula in cabecalho.get("celulas") or []:
            partes.append('<div role="columnheader">')
            partes.extend(_render_no(item) for item in celula.get("itens") or [])
            partes.append("</div>")
        partes.append("</div>")
    for indice, linha in enumerate(dados):
        celulas = linha.get("celulas") or []
        nome = _texto_visivel((celulas[0].get("itens") or []) if celulas else [])
        partes.append('<div class="linha-tabela linha-dado" role="row">')
        acao_linha = linha.get("acao")
        if isinstance(acao_linha, dict):
            titulo = _e(acao_linha.get("titulo") or "Ver detalhes")
            partes.append(
                f'<button type="button" class="abrir-linha" '
                f'aria-label="{titulo}: {_e(nome or f"linha {indice + 1}")}" '
                f"{_atributos_acao(acao_linha)}></button>"
            )
        for coluna, celula in enumerate(celulas):
            rotulo = rotulos[coluna] if coluna < len(rotulos) else ""
            classe = " celula-acoes" if rotulo.lower() in {"ações", "acoes"} else ""
            partes.append(
                f'<div class="celula{classe}" role="cell" data-rotulo="{_e(rotulo)}">'
            )
            partes.extend(_render_no(item) for item in celula.get("itens") or [])
            partes.append("</div>")
        partes.append("</div>")
    partes.append("</div>")
    return "".join(partes)


def _render_fatos(no: Json) -> str:
    fatos = no.get("fatos") or []
    if not fatos:
        return ""
    itens = "".join(
        '<div class="fato">'
        f"<dt>{_e(fato.get('titulo'))}</dt>"
        f"<dd>{_e(fato.get('valor'))}</dd>"
        "</div>"
        for fato in fatos
    )
    return f'<dl class="fatos">{itens}</dl>'


def _numeros_do_grafico(no: Json) -> list[float]:
    return [
        float(valor)
        for ponto in no.get("pontos") or []
        for valor in ponto.get("valores") or []
        if isinstance(valor, (int, float)) and not isinstance(valor, bool)
    ]


def _render_grafico(no: Json) -> str:
    pontos = no.get("pontos") or []
    series = no.get("series") or []
    numeros = _numeros_do_grafico(no)
    if not pontos or not series or not numeros:
        return ""
    minimo, maximo = min(numeros), max(numeros)
    alcance = max(maximo - minimo, 1e-9)
    largura, altura, margem = 360, 150, 12
    cores = [str(serie.get("cor") or "neutro") for serie in series]
    desenhos = []
    for indice, serie in enumerate(series):
        coordenadas = []
        for posicao, ponto in enumerate(pontos):
            valores = ponto.get("valores") or []
            valor = valores[indice] if indice < len(valores) else None
            if not isinstance(valor, (int, float)) or isinstance(valor, bool):
                continue
            x = margem + (largura - 2 * margem) * posicao / max(len(pontos) - 1, 1)
            y = margem + (altura - 2 * margem) * (maximo - float(valor)) / alcance
            coordenadas.append((x, y))
        if not coordenadas:
            continue
        pontos_svg = " ".join(f"{x:.1f},{y:.1f}" for x, y in coordenadas)
        tom = _e(cores[indice])
        rotulo = _e(serie.get("rotulo") or f"Série {indice + 1}")
        desenhos.append(
            f'<polyline class="linha-grafico tom-{tom}" points="{pontos_svg}" '
            f'aria-label="{rotulo}"></polyline>'
        )
    legenda = " · ".join(_e(serie.get("rotulo")) for serie in series)
    extremos = f"Mínimo {minimo:g} · máximo {maximo:g}"
    return (
        '<figure class="grafico">'
        f"<figcaption><strong>{_e(no.get('titulo') or 'Gráfico')}</strong>"
        f"<span>{legenda}</span></figcaption>"
        f'<svg viewBox="0 0 {largura} {altura}" role="img" '
        f'aria-label="{_e(extremos)}" preserveAspectRatio="none">'
        '<path class="grade-grafico" d="M12 12H348M12 75H348M12 138H348"></path>'
        + "".join(desenhos)
        + "</svg>"
        f'<p class="resumo-grafico">{_e(extremos)}</p></figure>'
    )


def _render_no(no: Json) -> str:
    if not no.get("visivel", True) and no.get("tipo") != "campo":
        return ""
    tipo = no.get("tipo")
    if tipo == "texto":
        return _render_texto(no)
    if tipo == "caixa":
        itens = "".join(_render_no(item) for item in no.get("itens") or [])
        grade = no.get("grade")
        classe_grade = f" caixa-grade-{_e(grade)}" if grade else ""
        return f'<section class="caixa caixa-{_e(no.get("estilo") or "default")}{classe_grade}">{itens}</section>'
    if tipo == "colunas":
        colunas = "".join(
            '<div class="coluna">'
            + "".join(_render_no(item) for item in coluna.get("itens") or [])
            + "</div>"
            for coluna in no.get("colunas") or []
        )
        return f'<div class="colunas">{colunas}</div>'
    if tipo == "acoes":
        botoes = "".join(_render_acao(botao) for botao in no.get("botoes") or [])
        return f'<div class="acoes">{botoes}</div>'
    if tipo == "escolha_livre":
        campo_id = _e(no.get("id") or "busca")
        lista_id = f"{campo_id}-opcoes"
        obrigatorio = " required" if no.get("obrigatorio") else ""
        opcoes = "".join(
            f'<option value="{_e(opcao.get("valor"))}">{_e(opcao.get("rotulo"))}</option>'
            for opcao in no.get("opcoes") or []
        )
        return (
            '<div class="campo-busca">'
            f'<label for="{campo_id}">{_e(no.get("rotulo") or "Buscar")}</label>'
            '<div class="entrada-com-icone"><span aria-hidden="true" class="lupa"></span>'
            f'<input id="{campo_id}" name="{_e(no.get("campo") or campo_id)}" '
            f'value="{_e(no.get("valor"))}" placeholder="{_e(no.get("dica"))}" '
            f'list="{lista_id}" autocomplete="off"{obrigatorio}></div>'
            f'<datalist id="{lista_id}">{opcoes}</datalist>'
            f'<p class="ajuda">Autocompletar por {_e(no.get("buscar") or "opções locais")}</p>'
            "</div>"
        )
    if tipo == "campo":
        campo_id = _e(no.get("id") or "campo")
        if not no.get("visivel", True):
            return (
                f'<input type="hidden" id="{campo_id}" '
                f'name="{_e(no.get("campo") or campo_id)}" value="{_e(no.get("valor"))}">'
            )
        return (
            '<div class="campo-comum">'
            f'<label for="{campo_id}">{_e(no.get("rotulo") or no.get("campo"))}</label>'
            f'<input id="{campo_id}" value="{_e(no.get("valor"))}" '
            f'placeholder="{_e(no.get("dica"))}"></div>'
        )
    if tipo == "tabela":
        return _render_tabela(no)
    if tipo == "fatos":
        return _render_fatos(no)
    if tipo == "grafico":
        return _render_grafico(no)
    if tipo == "autorizar":
        return (
            '<section class="autorizar">'
            f"<p>{_e(no.get('motivo'))}</p>"
            f'<button type="button" class="acao acao-primaria" data-autorizacao="{_e(no.get("onde"))}">'
            f"{_e(no.get('rotulo') or 'Autorizar')}</button>"
            f"<small>Você sairia para {_e(no.get('onde'))}</small></section>"
        )
    return f'<aside class="nao-renderizado">Componente {_e(tipo)} validado, ainda sem desenho nesta galeria.</aside>'


def _conteudo_da_tela(tela: Json) -> str:
    return "".join(_render_no(no) for no in tela.get("corpo") or [])


def _icone_da_navegacao(nome: str) -> str:
    # Vocabulário fechado e controlado pelo renderer. Nenhum SVG vem do app.
    desenhos = {
        "radar": '<circle cx="12" cy="12" r="8"></circle><circle cx="12" cy="12" r="3"></circle><path d="M12 4v3M20 12h-3"></path>',
        "ativos": '<path d="M4 17l5-5 3 3 7-8"></path><path d="M14 7h5v5"></path>',
        "fiis": '<path d="M4 20V9l8-5 8 5v11"></path><path d="M8 20v-6h8v6M8 10h.01M12 10h.01M16 10h.01"></path>',
        "carteira": '<path d="M3 7h15a2 2 0 012 2v9H5a2 2 0 01-2-2V7z"></path><path d="M5 7V5h11v2M15 12h5"></path>',
        "comunicados": '<path d="M6 3h9l3 3v15H6z"></path><path d="M15 3v4h4M9 12h6M9 16h6"></path>',
        "mais": '<circle cx="5" cy="12" r="1"></circle><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle>',
    }
    corpo = desenhos.get(nome, '<circle cx="12" cy="12" r="7"></circle>')
    return (
        '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{corpo}</svg>'
    )


def _navegacao_inferior(aplicativo: Json) -> str:
    superficies = aplicativo.get("superficies") or []
    if len(superficies) < 2:
        return ""
    botoes = []
    atual = aplicativo.get("atual")

    def destino(item: Json, *, extra: bool = False) -> str:
        selecionado = item.get("nome") == atual
        corrente = ' aria-current="page"' if selecionado else ""
        classe = " atual" if selecionado else ""
        classe_extra = " destino-extra" if extra else ""
        return (
            f'<button type="button" class="destino{classe}{classe_extra}" data-destino="{_e(item.get("nome"))}"{corrente}>'
            f"{_icone_da_navegacao(str(item.get('icone') or ''))}"
            f"<span>{_e(item.get('rotulo'))}</span></button>"
        )

    tem_mais = len(superficies) > 5
    principais = superficies[:4] if tem_mais else superficies
    extras = superficies[4:] if tem_mais else []
    botoes.extend(destino(item) for item in principais)
    if tem_mais:
        nomes_extras = ",".join(str(item.get("nome") or "") for item in extras)
        classe = " atual" if any(item.get("nome") == atual for item in extras) else ""
        menu = "".join(destino(item, extra=True) for item in extras)
        botoes.append(
            '<div class="destino-mais">'
            f'<button type="button" class="destino{classe}" data-abrir-mais data-extras="{_e(nomes_extras)}" aria-expanded="false">'
            f'{_icone_da_navegacao("mais")}<span>Mais</span></button>'
            f'<div class="menu-mais" role="menu" hidden>{menu}</div></div>'
        )
    return (
        f'<nav class="menu-inferior" aria-label="Telas de {_e(aplicativo.get("nome") or "serviço")}">'
        + "".join(botoes)
        + "</nav>"
    )


_CSS = r"""
:root { color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; min-width: 320px; background: #101114; color: #f5f5f3; }
button, input { font: inherit; }
button { cursor: pointer; }
.pular { position: fixed; left: 12px; top: -80px; z-index: 30; padding: 10px 14px; background: white; color: #111; border-radius: 8px; }
.pular:focus { top: 12px; }
.barra { position: sticky; top: 0; z-index: 20; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; min-height: 64px; padding: 10px clamp(16px, 3vw, 36px); border-bottom: 1px solid #34363b; background: rgba(16,17,20,.94); backdrop-filter: blur(14px); }
.marca { margin-right: auto; }
.marca strong, .marca small { display: block; }
.marca small { color: #afb2b9; margin-top: 2px; }
.controle { display: inline-flex; gap: 3px; padding: 3px; border: 1px solid #45474e; border-radius: 11px; background: #1b1d22; }
.controle button { min-height: 40px; padding: 7px 11px; border: 0; border-radius: 8px; background: transparent; color: #d8dae0; }
.controle button[aria-pressed="true"] { background: #f2f3f5; color: #17181b; }
.galeria { display: grid; grid-template-columns: minmax(620px, 1fr) 390px; align-items: start; gap: 28px; max-width: 1530px; margin: 0 auto; padding: 28px; overflow-x: auto; }
.galeria.somente-desktop { grid-template-columns: minmax(620px, 1040px); justify-content: center; }
.galeria.somente-mobile { grid-template-columns: 390px; justify-content: center; }
.galeria.somente-desktop .dispositivo-mobile, .galeria.somente-mobile .dispositivo-desktop { display: none; }
.dispositivo { min-width: 0; }
.rotulo-dispositivo { display: flex; justify-content: space-between; align-items: center; min-height: 34px; color: #c8cad0; font-size: 13px; }
.rotulo-dispositivo span:last-child { color: #8d9098; }
.moldura { overflow: hidden; border: 1px solid #41434a; border-radius: 20px; box-shadow: 0 24px 70px rgba(0,0,0,.26); }
.dispositivo-mobile .moldura { border-radius: 34px; }
.status-aparelho { height: 26px; padding: 6px 16px 0; text-align: right; background: var(--fundo); color: var(--texto); font-size: 11px; }
.surface { --respiro:clamp(22px, 4cqw, 48px); container-type: inline-size; display:flex; flex-direction:column; min-height: 700px; padding: var(--respiro); background: var(--fundo); color: var(--texto); transition: background .18s, color .18s; }
.dispositivo-mobile .surface { --respiro:16px; min-height: 760px; padding: 20px var(--respiro) 0; }
.surface[data-theme="light"] { --fundo:#ffffff; --painel:#f8fafc; --painel2:#e8eef8; --linha:#cbd5e5; --trilha:#64748b; --texto:#172033; --muted:#5d687a; --acento:#2457b8; --acento-fraco:#dce8fa; --sobre-acento:#ffffff; --perigo:#b83545; --foco:#805300; }
.surface[data-theme="dark"] { --fundo:#101a2b; --painel:#111d31; --painel2:#17243a; --linha:#2a3a52; --trilha:#607697; --texto:#f4f7fb; --muted:#aeb9ca; --acento:#4f8cff; --acento-fraco:#142a4c; --sobre-acento:#ffffff; --perigo:#ff6b7a; --foco:#f8c15c; }
.surface h1 { max-width: 22ch; margin: 0; font-family: ui-serif, Georgia, serif; font-size: clamp(26px, 3cqw, 28px); line-height: 1.08; letter-spacing: -.025em; }
.tela-app > h2, .detalhe-app > h2 { margin: 32px 0 5px; padding-top: 18px; border-top: 1px solid var(--linha); font-size: 18px; letter-spacing: -.01em; }
.caixa h2, .colunas h2 { margin: 5px 0; padding: 0; border: 0; font-size: 18px; }
.texto { margin: 5px 0; line-height: 1.45; }
.texto-small { font-size: 12px; }
.texto-default { font-size: 14px; }
.discreto { color: var(--muted); }
.negrito { font-weight: 720; }
.alinhamento-center { text-align: center; }
.alinhamento-right { text-align: right; }
.caixa { margin: 24px 0; padding: 18px; border: 1px solid var(--linha); border-radius: 14px; background: var(--painel); }
.caixa-emphasis { background: var(--painel2); }
.caixa-accent { border-color: var(--acento); background: var(--acento-fraco); }
.caixa-grade-compacta { display: grid; grid-template-columns: repeat(auto-fit,minmax(150px,1fr)); gap: 9px; }
.caixa-grade-compacta > .caixa { margin: 0; padding: 13px; background: var(--fundo); }
.colunas { display: flex; gap: 12px; margin: 12px 0; }
.coluna { flex: 1 1 0; min-width: 0; }
.campo-busca label, .campo-comum label { display: block; margin-bottom: 7px; font-size: 13px; font-weight: 700; }
.entrada-com-icone { position: relative; }
.lupa { position: absolute; left: 14px; top: 50%; width: 15px; height: 15px; border: 2px solid var(--muted); border-radius: 50%; transform: translateY(-58%); pointer-events: none; }
.lupa::after { content: ""; position: absolute; width: 7px; height: 2px; right: -6px; bottom: -3px; background: var(--muted); transform: rotate(45deg); }
.surface input:not([type="hidden"]) { width: 100%; min-height: 46px; padding: 10px 12px; border: 1px solid var(--trilha); border-radius: 10px; outline: none; background: var(--fundo); color: var(--texto); }
.entrada-com-icone input { padding-left: 42px !important; }
.surface input::placeholder { color: var(--muted); opacity: 1; }
.surface input:focus-visible, .surface button:focus-visible { outline: 3px solid var(--foco); outline-offset: 3px; }
.ajuda { margin: 7px 0 0; color: var(--muted); font-size: 11px; }
.acoes { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 14px; }
.acao { position: relative; z-index: 3; display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; padding: 9px 15px; border: 1px solid var(--trilha); border-radius: 10px; background: transparent; color: var(--texto); font-weight: 700; }
.acao:hover { background: var(--acento-fraco); }
.acao-primaria { border-color: var(--acento); background: var(--acento); color: var(--sobre-acento); }
.acao-primaria:hover { filter: brightness(.92); background: var(--acento); }
.acao-destrutiva { min-width: 44px; padding-inline: 11px; border-color: transparent; color: var(--perigo); }
.icone-lixeira { width: 14px; height: 16px; border: 2px solid currentColor; border-top: 0; border-radius: 0 0 3px 3px; }
.icone-lixeira::before { content:""; display:block; width:16px; height:2px; margin:-4px 0 0 -3px; background:currentColor; }
.tabela { width: 100%; margin-top: 13px; }
.linha-tabela { display: grid; grid-template-columns: var(--colunas); column-gap: 12px; align-items: center; }
.cabecalho-tabela { min-height: 36px; border-bottom: 1px solid var(--linha); }
.cabecalho-tabela .texto { margin: 0; color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .055em; }
.linha-dado { position: relative; min-height: 61px; border-bottom: 1px solid var(--linha); transition: background .14s; }
.linha-dado:hover { background: var(--acento-fraco); }
.celula { min-width: 0; padding: 9px 5px; }
.celula .texto { overflow-wrap: anywhere; }
.celula-acoes { position: relative; z-index: 2; display: flex; justify-content: flex-end; }
.celula-acoes .acoes { margin: 0; }
.celula-acoes .acao span:last-child { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.abrir-linha { position: absolute; inset: 0; z-index: 1; width: 100%; border: 0; background: transparent; color: transparent; }
.fatos { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:1px; margin:14px 0; overflow:hidden; border:1px solid var(--linha); border-radius:12px; background:var(--linha); }
.fato { padding:12px 14px; background:var(--painel); }
.fato dt { color:var(--muted); font-size:11px; font-weight:700; }
.fato dd { margin:5px 0 0; font-size:14px; font-weight:750; }
.grafico { margin:20px 0; padding:16px; border:1px solid var(--linha); border-radius:14px; background:var(--painel); }
.grafico figcaption { display:flex; justify-content:space-between; gap:12px; margin-bottom:12px; }
.grafico figcaption span, .resumo-grafico { color:var(--muted); font-size:11px; }
.grafico svg { display:block; width:100%; height:170px; overflow:visible; }
.grade-grafico { fill:none; stroke:var(--linha); stroke-width:1; vector-effect:non-scaling-stroke; }
.linha-grafico { fill:none; stroke:var(--acento); stroke-width:2.5; stroke-linecap:round; stroke-linejoin:round; vector-effect:non-scaling-stroke; }
.tom-positivo { stroke:#16865c; }
.tom-negativo { stroke:var(--perigo); }
.tom-atencao { stroke:#c27b16; }
.resumo-grafico { margin:8px 0 0; }
.nao-renderizado { padding: 12px; border: 1px dashed var(--trilha); color: var(--muted); }
.autorizar { margin: 16px 0; padding: 16px; border: 1px solid var(--linha); border-radius: 12px; background: var(--painel); }
.autorizar p { margin: 0 0 12px; }
.autorizar small { display: block; margin-top: 8px; color: var(--muted); }
.tela-app[hidden], .detalhe-app[hidden] { display: none; }
.tela-app:focus-visible, .detalhe-app:focus-visible { outline: 3px solid var(--foco); outline-offset: 4px; }
.barra-detalhe { display:flex; align-items:center; margin:0 0 18px; }
.voltar { display:inline-flex; align-items:center; gap:8px; min-width:44px; min-height:44px; padding:8px 12px; border:1px solid var(--trilha); border-radius:10px; background:transparent; color:var(--texto); font-weight:700; white-space:nowrap; }
.voltar:hover { background:var(--acento-fraco); }
.voltar svg { width:18px; height:18px; }
.nota-preview { margin: 24px 0 0; padding: 11px 13px; border-radius: 10px; background: var(--acento-fraco); color: var(--muted); font-size: 11px; }
.menu-inferior { position: sticky; z-index: 10; bottom: 0; display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); gap: 2px; margin: 22px calc(-1 * var(--respiro)) calc(-1 * var(--respiro)); padding: 6px 8px 9px; border-top: 1px solid var(--linha); background: color-mix(in srgb, var(--fundo) 94%, transparent); backdrop-filter: blur(14px); }
.menu-inferior { margin-top: auto; }
.dispositivo-mobile .menu-inferior { margin-bottom: 0; }
.destino { min-width: 0; min-height: 54px; padding: 5px 2px; border: 0; border-radius: 9px; background: transparent; color: var(--muted); font-size: 10px; }
.destino svg { display: block; width: 22px; height: 22px; margin: 0 auto 3px; }
.destino span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.destino:hover { background: var(--acento-fraco); color: var(--texto); }
.destino.atual { color: var(--acento); font-weight: 800; }
.destino-mais { position: relative; min-width: 0; }
.destino-mais > .destino { width: 100%; }
.menu-mais { position: absolute; right: 0; bottom: 62px; z-index: 14; display: grid; min-width: 210px; max-height: 320px; overflow-y: auto; padding: 6px; border: 1px solid var(--linha); border-radius: 12px; background: var(--painel); box-shadow: 0 18px 45px rgba(0,0,0,.28); }
.menu-mais[hidden] { display: none; }
.menu-mais .destino { display: grid; grid-template-columns: 28px 1fr; align-items: center; gap: 10px; min-height: 48px; padding: 8px 10px; text-align: left; font-size: 12px; }
.menu-mais .destino svg { width: 20px; height: 20px; margin: 0; }
.resultado { position: fixed; z-index: 50; left: 50%; bottom: 24px; width: min(560px, calc(100% - 32px)); padding: 13px 16px; border: 1px solid #5c606a; border-radius: 12px; background: #202228; color: white; box-shadow: 0 18px 50px rgba(0,0,0,.35); transform: translate(-50%, 140px); transition: transform .2s; }
.resultado.visivel { transform: translate(-50%, 0); }
@container (max-width: 600px) {
  .surface h1 { font-size: 28px; }
  .caixa { margin: 20px 0; padding: 14px; }
  .acoes > .acao { flex: 1 1 145px; }
  .cabecalho-tabela { display: none; }
  .tabela { display: grid; gap: 8px; }
  .linha-dado { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; min-height: 0; padding: 10px 12px; border: 1px solid var(--linha); border-radius: 12px; background: var(--painel); }
  .celula { padding: 4px 2px; }
  .celula::before { content: attr(data-rotulo); display: block; margin-bottom: 1px; color: var(--muted); font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
  .celula:first-of-type { grid-column: 1 / -1; padding-right: 52px; }
  .celula-acoes { position: absolute; z-index: 3; right: 7px; top: 7px; padding: 0; }
  .celula-acoes::before { display: none; }
  .linha-dado:hover { background: var(--acento-fraco); }
}
@media (max-width: 760px) {
  .barra { position: static; }
  .galeria { grid-template-columns: 390px; justify-content: start; padding: 16px; }
  .dispositivo-desktop { display: none; }
  .controle-viewport { display: none; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; } }
"""


_JS = r"""
const galeria = document.querySelector('.galeria');
const resultado = document.querySelector('.resultado');
let timer;

function anunciar(texto) {
  resultado.textContent = texto;
  resultado.classList.add('visivel');
  clearTimeout(timer);
  timer = setTimeout(() => resultado.classList.remove('visivel'), 4200);
}

function marcarDestino(destino) {
  document.querySelectorAll('[data-destino]').forEach((item) => {
    const atual = item.dataset.destino === destino;
    item.classList.toggle('atual', atual);
    if (atual) item.setAttribute('aria-current', 'page'); else item.removeAttribute('aria-current');
  });
  document.querySelectorAll('[data-abrir-mais]').forEach((item) => {
    const atual = (item.dataset.extras || '').split(',').includes(destino);
    item.classList.toggle('atual', atual);
    if (atual) item.setAttribute('aria-current', 'page'); else item.removeAttribute('aria-current');
  });
}

function abrirTela(destino, focar = false) {
  document.querySelectorAll('.surface').forEach((surface) => {
    surface.querySelectorAll('.tela-app, .detalhe-app').forEach((tela) => tela.hidden = true);
    const tela = surface.querySelector('.tela-app[data-tela="' + CSS.escape(destino) + '"]');
    if (tela) {
      tela.hidden = false;
      if (focar && surface.closest('.dispositivo-mobile')) tela.focus();
    }
  });
  marcarDestino(destino);
}

function abrirResposta(operacao, valores) {
  let encontrou = false;
  let origem = '';
  document.querySelectorAll('.surface').forEach((surface) => {
    const candidatas = surface.querySelectorAll('.detalhe-app[data-operacao="' + CSS.escape(operacao) + '"]');
    const resposta = Array.from(candidatas).find((item) => {
      const campo = item.dataset.campo;
      return String(valores[campo] || '').toUpperCase() === item.dataset.valor.toUpperCase();
    });
    if (!resposta) return;
    encontrou = true;
    origem = resposta.dataset.voltar;
    surface.querySelectorAll('.tela-app, .detalhe-app').forEach((tela) => tela.hidden = true);
    resposta.hidden = false;
    if (surface.closest('.dispositivo-mobile')) resposta.focus();
  });
  if (encontrou) {
    marcarDestino(origem);
    anunciar('Detalhes abertos · ' + String(Object.values(valores)[0] || 'ativo'));
  }
  return encontrou;
}

document.querySelectorAll('[data-tema]').forEach((botao) => {
  botao.addEventListener('click', () => {
    const tema = botao.dataset.tema;
    document.querySelectorAll('.surface').forEach((surface) => surface.dataset.theme = tema);
    document.querySelectorAll('[data-tema]').forEach((item) => item.setAttribute('aria-pressed', String(item === botao)));
  });
});

document.querySelectorAll('[data-viewport]').forEach((botao) => {
  botao.addEventListener('click', () => {
    galeria.classList.remove('somente-desktop', 'somente-mobile');
    if (botao.dataset.viewport !== 'ambos') galeria.classList.add('somente-' + botao.dataset.viewport);
    document.querySelectorAll('[data-viewport]').forEach((item) => item.setAttribute('aria-pressed', String(item === botao)));
  });
});

document.querySelectorAll('[data-operacao]').forEach((botao) => {
  botao.addEventListener('click', () => {
    const campos = JSON.parse(botao.dataset.campos || '[]');
    const escopo = botao.closest('.linha-dado') || botao.closest('.detalhe-app, .tela-app') || botao.closest('.surface');
    const valores = {};
    for (const id of campos) {
      const campo = escopo.querySelector('#' + CSS.escape(id)) || botao.closest('.surface').querySelector('#' + CSS.escape(id));
      if (campo) valores[campo.name || id] = campo.value;
      if (campo && campo.required && !campo.value.trim()) {
        campo.focus();
        anunciar('Preencha “' + (campo.previousElementSibling?.textContent || campo.name) + '” antes de continuar.');
        return;
      }
    }
    if (botao.dataset.destrutiva === 'true' && !window.confirm('Simular esta remoção? Nenhum dado real será alterado.')) return;
    if (abrirResposta(botao.dataset.operacao, valores)) return;
    const complemento = Object.keys(valores).length ? ' · dados: ' + JSON.stringify(valores) : '';
    anunciar('Simulação local · ' + botao.dataset.operacao + complemento);
  });
});

document.querySelectorAll('[data-destino]').forEach((botao) => {
  botao.addEventListener('click', () => {
    const destino = botao.dataset.destino;
    abrirTela(destino);
    document.querySelectorAll('.menu-mais').forEach((menu) => menu.hidden = true);
    document.querySelectorAll('[data-abrir-mais]').forEach((item) => item.setAttribute('aria-expanded', 'false'));
    anunciar('Tela aberta · ' + botao.textContent.trim());
  });
});

document.querySelectorAll('[data-abrir-mais]').forEach((botao) => {
  botao.addEventListener('click', () => {
    const menu = botao.parentElement.querySelector('.menu-mais');
    const abrir = menu.hidden;
    menu.hidden = !abrir;
    botao.setAttribute('aria-expanded', String(abrir));
  });
});

document.addEventListener('keydown', (evento) => {
  if (evento.key !== 'Escape') return;
  document.querySelectorAll('.menu-mais').forEach((menu) => menu.hidden = true);
  document.querySelectorAll('[data-abrir-mais]').forEach((item) => item.setAttribute('aria-expanded', 'false'));
});

document.querySelectorAll('[data-voltar-detalhe]').forEach((botao) => {
  botao.addEventListener('click', () => {
    abrirTela(botao.dataset.voltarDetalhe, true);
    anunciar('Voltando para ' + botao.textContent.replace('Voltar para', '').trim());
  });
});

document.querySelectorAll('[data-autorizacao]').forEach((botao) => {
  botao.addEventListener('click', () => anunciar('Simulação local · abriria autorização em ' + botao.dataset.autorizacao));
});
"""


def pagina(tela: Json, alvo: str, esc: frozenset[str], lei: frozenset[str]) -> str:
    aplicativo = {
        "nome": Path(alvo.split(":", 1)[0]).stem,
        "atual": "preview",
        "superficies": [
            {
                "nome": "preview",
                "rotulo": "Preview",
                "icone": "ativos",
                "tela": tela,
            }
        ],
    }
    return pagina_aplicativo(aplicativo, alvo, esc, lei)


def pagina_aplicativo(
    aplicativo: Json, alvo: str, esc: frozenset[str], lei: frozenset[str]
) -> str:
    atual = aplicativo.get("atual")
    blocos = []
    for superficie in aplicativo.get("superficies") or []:
        tela = superficie["tela"]
        oculto = "" if superficie.get("nome") == atual else " hidden"
        blocos.append(
            f'<section class="tela-app" tabindex="-1" data-tela="{_e(superficie.get("nome"))}"{oculto}>'
            + _conteudo_da_tela(tela)
            + f'<p class="nota-preview">Tema {_e(tela.get("tema") or "padrão")} · superfície {_e(superficie.get("nome"))}</p>'
            + "</section>"
        )
    detalhes = []
    rotulos = {
        str(superficie.get("nome")): str(
            superficie.get("rotulo") or superficie.get("nome") or "lista"
        )
        for superficie in aplicativo.get("superficies") or []
    }
    for resposta in aplicativo.get("respostas") or []:
        voltar_para = str(resposta.get("voltar_para") or "")
        rotulo = rotulos.get(voltar_para, voltar_para)
        detalhes.append(
            '<section class="detalhe-app" tabindex="-1" hidden '
            f'data-operacao="{_e(resposta.get("operacao"))}" '
            f'data-campo="{_e(resposta.get("campo"))}" '
            f'data-valor="{_e(resposta.get("valor"))}" '
            f'data-voltar="{_e(voltar_para)}">'
            '<div class="barra-detalhe">'
            f'<button type="button" class="voltar" data-voltar-detalhe="{_e(voltar_para)}">'
            '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"></path></svg>'
            f"<span>Voltar para {_e(rotulo)}</span></button></div>"
            + _conteudo_da_tela(resposta["tela"])
            + "</section>"
        )
    conteudo = "".join((*blocos, *detalhes))
    navegacao = _navegacao_inferior(aplicativo)
    operacoes = ", ".join(sorted((*lei, *esc))) or "nenhuma"
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Preview · {_e(alvo)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <a class="pular" href="#preview">Pular para o preview</a>
  <header class="barra">
    <div class="marca"><strong>OkMigo Cartão</strong><small>Preview local · não é o renderer de produção</small></div>
    <div class="controle controle-viewport" aria-label="Tamanho do preview">
      <button type="button" data-viewport="ambos" aria-pressed="true">Ambos</button>
      <button type="button" data-viewport="desktop" aria-pressed="false">Desktop</button>
      <button type="button" data-viewport="mobile" aria-pressed="false">Celular</button>
    </div>
    <div class="controle" aria-label="Tema do preview">
      <button type="button" data-tema="light" aria-pressed="true">Claro</button>
      <button type="button" data-tema="dark" aria-pressed="false">Escuro</button>
    </div>
  </header>
  <main id="preview" class="galeria">
    <section class="dispositivo dispositivo-desktop" aria-labelledby="rotulo-desktop">
      <div class="rotulo-dispositivo"><strong id="rotulo-desktop">Desktop</strong><span>fluido · até 1040 px</span></div>
      <div class="moldura"><div class="surface" data-theme="light">{conteudo}<p class="nota-preview">Operações conferidas: {_e(operacoes)}</p>{navegacao}</div></div>
    </section>
    <section class="dispositivo dispositivo-mobile" aria-labelledby="rotulo-mobile">
      <div class="rotulo-dispositivo"><strong id="rotulo-mobile">Celular</strong><span>390 px</span></div>
      <div class="moldura"><div class="status-aparelho">09:41</div><div class="surface" data-theme="light">{conteudo}{navegacao}</div></div>
    </section>
  </main>
  <div class="resultado" role="status" aria-live="polite"></div>
  <script>{_JS}</script>
</body>
</html>"""


def _lista(valor: str | None) -> frozenset[str] | None:
    if valor is None:
        return None
    return frozenset(item.strip() for item in valor.split(",") if item.strip())


def main_preview(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="okmigo-cartao preview",
        description="Compila, confere e mostra uma tela do SDK no desktop e no celular.",
    )
    parser.add_argument(
        "alvo",
        help="manifesto.json ou arquivo.py:objeto (Tela, Aplicativo ou fábrica)",
    )
    parser.add_argument(
        "--dados",
        type=Path,
        help="JSON da tela ou mapa {superficie: {resumo, linhas}} do aplicativo",
    )
    parser.add_argument(
        "--escrituras", help="operações de escrita; por padrão são inferidas do SDK"
    )
    parser.add_argument(
        "--leituras", help="operações de leitura; por padrão são inferidas do SDK"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="interface do servidor (padrão: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=4173, help="porta do servidor (padrão: 4173)"
    )
    parser.add_argument(
        "--saida", type=Path, help="grava um HTML autocontido e não inicia servidor"
    )
    args = parser.parse_args(argv)

    def construir() -> tuple[str, frozenset[str], frozenset[str]]:
        aplicativo, esc, lei = construir_aplicativo(
            args.alvo,
            args.dados,
            escrituras=_lista(args.escrituras),
            leituras=_lista(args.leituras),
        )
        return pagina_aplicativo(aplicativo, args.alvo, esc, lei), esc, lei

    try:
        documento, esc, lei = construir()
    except (ErroDePreview, OSError, AttributeError, TypeError, ValueError) as erro:
        print(f"✗ preview recusado — {erro}", file=sys.stderr)
        return 1

    print(f"✓ preview validado · {len(lei)} leitura(s) · {len(esc)} escrita(s)")
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(documento, encoding="utf-8")
        print(f"  HTML escrito em {args.saida.resolve()}")
        return 0

    class Manipulador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/favicon.ico"):
                self.send_response(204)
                self.end_headers()
                return
            try:
                atual, _, _ = construir()
                corpo = atual.encode("utf-8")
                status = 200
            except Exception as erro:  # noqa: BLE001 — código-alvo pode falhar ao importar
                corpo = (
                    "<!doctype html><meta charset=utf-8><title>Erro no preview</title>"
                    f"<pre>{_e(erro)}</pre><p>Corrija o arquivo e recarregue a página.</p>"
                ).encode()
                status = 500
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, formato: str, *valores: Any) -> None:
            return

    try:
        servidor = ThreadingHTTPServer((args.host, args.port), Manipulador)
    except OSError as erro:
        print(f"✗ não consegui abrir {args.host}:{args.port} — {erro}", file=sys.stderr)
        return 1
    print(f"  desktop + celular: http://localhost:{args.port}")
    print("  no container, publique/encaminhe essa porta; Ctrl+C encerra")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  preview encerrado")
    finally:
        servidor.server_close()
    return 0
