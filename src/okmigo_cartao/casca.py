"""A casca: o cartão reconstruído em HTML SEM UMA LINHA DE CSS — e o relatório
do que o crivo comeu.

Quem escreve um app precisa de duas respostas antes de registrar a tela:

1. **O que passa, e com que forma sai?** A casca desenha o cartão RECONSTRUÍDO
   (a saída do crivo, não o original) como documento pelado: a hierarquia se
   prova antes da primeira cor. Se o documento pelado não faz sentido, nenhum
   renderizador conserta.
2. **O que o crivo comeu?** O modo de falha desta plataforma quase nunca é
   erro: é a tela sair sem o pedaço. O `relatorio()` compara o que entrou com
   o que saiu e nomeia o que sumiu.

E há a terceira coisa que torna o teste honesto: **validar o molde cru não
prova nada.** Um molde com `_repetir_lista` só existe depois que alguém o
expande com dados — e a linha de dado é o que vira tabela, grade, fichas. O
`expandir()` faz essa expansão do mesmo jeito que a ponte do produto faz, para
o que se valida aqui ser o que chega lá.
"""

from __future__ import annotations

import html
import re
from typing import Any

# ── A expansão do molde ─────────────────────────────────────────────────────

_CAMPO = re.compile(r"\{([a-zA-Z0-9_.]+)\}")
#: Teto de itens numa repetição aninhada (`_de`). É do produto: sem ele um
#: serviço que embutisse o extrato inteiro em cada conta faria o cartão explodir
#: antes de o crivo ter a chance de recusar.
_MAX_DE = 50


def _numero(v: float | int) -> str:
    """`840000.0` → `840.000`, `62900.5` → `62.900,50`. Regra única e sem
    sintaxe: todo número substituído num molde sai formatado para leitura.
    É por isso que o crivo aceita «1.234,25» como número."""
    inteiro = float(v).is_integer()
    txt = f"{float(v):,.0f}" if inteiro else f"{float(v):,.2f}"
    return txt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _preencher(molde: Any, dado: dict[str, Any]) -> str:
    """`"{marca} {modelo}"` + `{"marca": "X"}` → `"X ..."`. Substituição de campo
    e MAIS NADA — sem condicional, sem laço, sem expressão. Campo ausente vira
    vazio, os espaços colapsam, e o SEPARADOR que só existia para ligar duas
    coisas (`·`, `—`, `|`) colapsa junto."""
    def troca(m: re.Match) -> str:
        v: Any = dado
        for parte in m.group(1).split("."):
            v = v.get(parte) if isinstance(v, dict) else None
            if v is None:
                return ""
        return _numero(v) if isinstance(v, (int, float)) and not isinstance(v, bool) \
            else str(v)

    texto = " ".join(_CAMPO.sub(troca, str(molde)).split())
    for sep in ("·", "—", "|"):
        while f" {sep} {sep} " in texto:
            texto = texto.replace(f" {sep} {sep} ", f" {sep} ")
        texto = texto.strip().removeprefix(f"{sep} ").removesuffix(f" {sep}")
    return texto.strip()


def _peneirar(linhas: list[dict], quando: Any) -> list[dict]:
    """`_quando: {campo, em: [...]}` escolhe QUAIS itens entram na repetição."""
    if quando is None:
        return linhas
    if not isinstance(quando, dict):
        return linhas
    campo, valores = quando.get("campo"), quando.get("em")
    if not isinstance(campo, str) or not isinstance(valores, list) or not valores:
        return linhas
    aceitos = {str(v).strip() for v in valores}
    return [l for l in linhas if campo in l and str(l[campo]).strip() in aceitos]


def expandir(molde: Any, dado: dict[str, Any], linhas: list[dict] | None = None) -> Any:
    """Expande um molde de cartão com dados, como a ponte do produto faz.

    Quatro regras, e só quatro: `{campo}` em texto vira valor; o nó
    `{"_repetir_lista": <modelo>}` dentro de uma lista vira N cópias do modelo,
    uma por item de `linhas`; `_quando` ao lado dele escolhe quais itens; `_de`
    ao lado dele repete sobre uma lista DE DENTRO do dado da vez (a sublista
    de um item) em vez da lista da superfície. A expansão não sabe o que é um
    `TextBlock` — é genérica de propósito.

    `dado` é o resumo da superfície (o objeto de topo); `linhas` é a lista da
    superfície. Dentro de um item repetido, `linhas` chega vazia: uma
    superfície tem UMA lista, e repeti-la dentro dela mesma seria N×N.
    """
    linhas = linhas or []
    if isinstance(molde, str):
        return _preencher(molde, dado)
    if isinstance(molde, dict):
        if "_repetir_lista" in molde:
            fonte = linhas
            if isinstance(molde.get("_de"), str):
                de = dado.get(molde["_de"])
                fonte = [x for x in de if isinstance(x, dict)][:_MAX_DE] \
                    if isinstance(de, list) else []
            return [
                expandir(molde["_repetir_lista"], linha, [])
                for linha in _peneirar(fonte, molde.get("_quando"))
            ]
        return {k: expandir(v, dado, linhas) for k, v in molde.items()}
    if isinstance(molde, list):
        saida: list = []
        for filho in molde:
            pronto = expandir(filho, dado, linhas)
            # A repetição devolve LISTA no lugar de um item: ela se dissolve na
            # lista de cima, senão viraria uma lista dentro de um item.
            saida.extend(pronto) if isinstance(filho, dict) and "_repetir_lista" in filho \
                else saida.append(pronto)
        return saida
    return molde


# ── O relatório do que o crivo comeu ───────────────────────────────────────

#: Tipo de ENTRADA → tipos de SAÍDA que ele pode virar. Um tipo de entrada que
#: apareceu e não produziu nenhuma saída correspondente foi comido.
_ENTRA_SAI: dict[str, set[str]] = {
    "TextBlock": {"texto"},
    "Container": {"caixa"},
    "ColumnSet": {"colunas"},
    "Table": {"tabela"},
    "FactSet": {"fatos"},
    "Image": {"imagem", "sem_imagem"},
    "Input.Text": {"campo"},
    "Input.Number": {"campo"},
    "Input.ChoiceSet": {"escolha", "escolha_livre"},
    "ActionSet": {"acoes"},
    "okmigoCalendario": {"calendario"},
    "okmigoArquivo": {"arquivo"},
    "okmigoDocumento": {"documento"},
    "okmigoCopiar": {"copiar"},
    "okmigoAutorizar": {"autorizar"},
    "okmigoCronometro": {"cronometro"},
    "okmigoProgresso": {"progresso"},
    "okmigoGrafico": {"grafico"},
    "okmigoCartaoBancario": {"cartao_bancario"},
    "okmigoDistribuicao": {"distribuicao"},
    "okmigoListaFinanceira": {"lista_financeira"},
}
#: Chaves que o crivo LÊ E DESCARTA de propósito — não é «comeu», é regra.
_DESCARTADAS_DE_PROPOSITO = {
    ("TextBlock", "color"): "cor é do tema, não do serviço — o TOM vai na caixa (style)",
    ("Image", "size"): "tamanho de imagem é `height` em palavra",
    ("Image", "style"): "estilo de imagem não existe neste vocabulário",
}
_ACOES_RECUSADAS = {"Action.OpenUrl": "ação nomeia capacidade, nunca endereço",
                    "Action.ShowCard": "não existe neste subconjunto",
                    "Action.Execute": "não existe neste subconjunto"}
#: Filhos estruturais de tabela e de colunas: não são nós por si — vivem e
#: morrem com o pai.
_ESTRUTURAIS = {"TableRow", "TableCell", "Column"}
#: Por que um tipo conhecido costuma sumir — a frase que o autor precisa ler.
_POR_QUE_SOME = {
    "TextBlock": "texto vazio — ou o pai (tabela, caixa) foi descartado",
    "Table": "cabeçalho sem linha de dado, ou linhas fora do formato TableRow/TableCell",
    "ColumnSet": "sem nenhuma coluna válida",
    "FactSet": "nenhum fato com título",
    "Input.Text": "sem `id`",
    "Input.Number": "sem `id`",
    "Input.ChoiceSet": "sem `id`, ou lista estrita sem opção válida (title E value)",
    "ActionSet": "sem ação válida: Submit pede title e data.operacao; ToggleVisibility pede title e alvos; OpenUrl evapora",
    "okmigoArquivo": "sem `id`",
    "okmigoDocumento": "sem `ler.operacao`, ou sem título/nome",
    "okmigoCopiar": "sem valor ou sem rótulo",
    "okmigoAutorizar": "url fora das travas (https, sem credencial, sem porta/IP, não é domínio do produto), sem rótulo/motivo, ou já havia um no cartão",
    "okmigoCronometro": "sem rótulo, ou segundos fora de 1…3600",
    "okmigoProgresso": "`de` não numérico, ≤ 0 ou > 10000, ou `feito` não numérico",
    "okmigoGrafico": "nenhuma série com rótulo, ou nenhum ponto com valor numérico",
    "okmigoCalendario": "nunca some por si — o pai foi descartado",
    "okmigoCartaoBancario": "nenhum cartão com título",
    "okmigoDistribuicao": "nenhum item com valor numérico",
    "okmigoListaFinanceira": "nenhum item com título",
    "Image": "só some quando cai num `fallback` de outro tipo — sem URL válida vira `sem_imagem`",
    "Container": "nunca some por si — o pai foi descartado",
}


def _contar_entrada(no: Any, contagem: dict[str, int], avisos: list[str], caminho: str) -> None:
    if isinstance(no, list):
        for i, filho in enumerate(no):
            _contar_entrada(filho, contagem, avisos, f"{caminho}[{i}]")
        return
    if not isinstance(no, dict):
        return
    tipo = no.get("type")
    if isinstance(tipo, str) and tipo.startswith("Action."):
        if tipo in _ACOES_RECUSADAS:
            avisos.append(f"{caminho}: `{tipo}` recusado — {_ACOES_RECUSADAS[tipo]}")
        return
    if tipo in _ESTRUTURAIS:
        # linha e célula de tabela não são nós por si: vivem e morrem com a tabela
        if tipo == "TableRow" and no.get("selectAction", {}).get("type") not in (
            None,
            "Action.Execute",
        ):
            avisos.append(
                f"{caminho}: `TableRow.selectAction` só aceita `Action.Execute`"
            )
        for chave in ("cells", "items"):
            if chave in no:
                _contar_entrada(no[chave], contagem, avisos, f"{caminho}.{chave}")
        return
    if tipo:
        contagem[tipo] = contagem.get(tipo, 0) + 1
        if tipo not in _ENTRA_SAI:
            avisos.append(f"{caminho}: tipo `{tipo}` é DESCONHECIDO — some na tela"
                          + (" (tem `fallback`)" if isinstance(no.get("fallback"), dict) else ""))
        for (t, chave), motivo in _DESCARTADAS_DE_PROPOSITO.items():
            if tipo == t and chave in no:
                avisos.append(f"{caminho}: `{tipo}.{chave}` é descartado — {motivo}")
        if tipo == "Container" and no.get("selectAction", {}).get("type") not in (None, "Action.ToggleVisibility"):
            avisos.append(f"{caminho}: `selectAction` só aceita `Action.ToggleVisibility`")
    for chave in ("items", "columns", "rows", "cells", "actions", "fallback", "body"):
        if chave in no:
            _contar_entrada(no[chave], contagem, avisos, f"{caminho}.{chave}")


def _contar_saida(no: Any, contagem: dict[str, int]) -> None:
    if isinstance(no, list):
        for filho in no:
            _contar_saida(filho, contagem)
        return
    if not isinstance(no, dict):
        return
    t = no.get("tipo")
    if isinstance(t, str):
        contagem[t] = contagem.get(t, 0) + 1
    for chave in ("itens", "corpo"):
        if chave in no:
            _contar_saida(no[chave], contagem)
    for c in no.get("colunas") or []:
        if isinstance(c, dict):
            _contar_saida(c.get("itens"), contagem)
    # `linhas` é lista só na tabela; num `campo` é o número de linhas de texto.
    if t == "tabela":
        for l in no.get("linhas") or []:
            if isinstance(l, dict):
                for c in l.get("celulas") or []:
                    _contar_saida(c.get("itens"), contagem)


def relatorio(bruto: Any, tela: dict | None, erro: str | None) -> list[str]:
    """O que entrou e não saiu, em frases — para o autor ver o que o crivo
    comeu em silêncio. Vazio quando tudo o que entrou tem correspondente."""
    linhas: list[str] = []
    if erro:
        linhas.append(f"⛔ tela RECUSADA: {erro}")
    entrada: dict[str, int] = {}
    avisos: list[str] = []
    corpo = bruto.get("body") if isinstance(bruto, dict) else None
    _contar_entrada(corpo, entrada, avisos, "body")
    saida: dict[str, int] = {}
    if tela:
        _contar_saida(tela.get("corpo"), saida)
    # Tela recusada não tem «o que sumiu»: sumiu tudo, pelo motivo já dito.
    # Sobram só os avisos de entrada (tipo desconhecido, chave descartada).
    for tipo, n in (sorted(entrada.items()) if not erro else []):
        alvos = _ENTRA_SAI.get(tipo)
        if not alvos:
            continue  # desconhecido já foi avisado
        m = sum(saida.get(a, 0) for a in alvos)
        if m < n:
            linhas.append(f"⚠️ {n - m} de {n} `{tipo}` sumiram (saíram {m}) — "
                          + _POR_QUE_SOME.get(tipo, "o pai foi descartado"))
    # Degradações que não «somem» mas mudam o que a pessoa vê.
    if saida.get("sem_imagem"):
        linhas.append(f"⚠️ {saida['sem_imagem']} imagem(ns) viraram MARCADOR — URL vazia, ou fora do "
                      "domínio do produto (passe --dominio), ou sem https")
    linhas.extend(avisos)
    # Chaves de topo que o crivo conhece e não encontrou ficam de fora: são
    # opcionais. As que ele NÃO conhece merecem aviso.
    if isinstance(bruto, dict):
        for chave in bruto:
            if chave not in ("type", "version", "body", "okmigoTema", "okmigoNavegacao", "$schema"):
                linhas.append(f"ℹ️ chave de topo `{chave}` é ignorada")
    return linhas


# ── A casca: HTML sem CSS ───────────────────────────────────────────────────

def _e(t: Any) -> str:
    return html.escape(str(t if t is not None else ""))


def _no(n: dict, s: list[str]) -> None:
    tipo = n.get("tipo")
    escondido = " hidden" if n.get("visivel") is False else ""
    ident = f' id="{_e(n["id"])}"' if n.get("id") else ""
    if n.get("separador"):
        s.append("<hr>")

    if tipo == "texto":
        tag = {"extraLarge": "h1", "large": "h2", "medium": "h3"}.get(n["tamanho"], "p")
        abre = "<strong>" if n["peso"] == "bolder" and tag == "p" else ""
        fecha = "</strong>" if abre else ""
        sub = " <small>(discreto)</small>" if n.get("discreto") else ""
        s.append(f"<{tag}{ident}{escondido}>{abre}{_e(n['texto'])}{fecha}{sub}</{tag}>")
    elif tipo == "caixa":
        rot = f"style={_e(n['estilo'])}" if n.get("estilo") != "default" else ""
        grade = f" grade={_e(n['grade'])}" if n.get("grade") else ""
        sobre = " sobreposto" if n.get("sobreposto") else ""
        toque = f" (toque alterna: {', '.join(a['id'] for a in n['ao_tocar']['alvos'])})" if n.get("ao_tocar") else ""
        s.append(f"<section{ident}{escondido}><!-- caixa {rot}{grade}{sobre}{toque} -->")
        for f in n.get("itens") or []:
            _no(f, s)
        s.append("</section>")
    elif tipo == "colunas":
        s.append(f"<div{ident}{escondido}><!-- colunas -->")
        for c in n["colunas"]:
            s.append(f"<div><!-- coluna {c['largura']} -->")
            for f in c.get("itens") or []:
                _no(f, s)
            s.append("</div>")
        s.append("</div>")
    elif tipo == "tabela":
        s.append(f"<table{ident}{escondido}>")
        for i, l in enumerate(n["linhas"]):
            cel = "th" if n.get("cabecalho") and i == 0 else "td"
            s.append("<tr>")
            for c in l["celulas"]:
                s.append(f"<{cel}>")
                for f in c.get("itens") or []:
                    _no(f, s)
                s.append(f"</{cel}>")
            s.append("</tr>")
        s.append("</table>")
    elif tipo == "fatos":
        s.append(f"<dl{ident}{escondido}>")
        for f in n["fatos"]:
            s.append(f"<dt>{_e(f['titulo'])}</dt><dd>{_e(f['valor'])}</dd>")
        s.append("</dl>")
    elif tipo == "imagem":
        s.append(f'<img{ident}{escondido} src="{_e(n["url"])}" alt="{_e(n["alt"])}">')
    elif tipo == "sem_imagem":
        s.append(f"<figure{ident}{escondido}><figcaption>[sem imagem] {_e(n['alt'])}</figcaption></figure>")
    elif tipo == "campo":
        tag = "textarea" if n["linhas"] > 1 else "input"
        tipo_html = ' type="number"' if n["formato"] == "numero" else ' type="text"'
        req = " required" if n["obrigatorio"] else ""
        ro = " readonly" if n.get("somente_leitura") else ""
        val = _e(n["valor"])
        s.append(f"<label{escondido}>{_e(n['rotulo'])} "
                 + (f"<textarea name=\"{_e(n['campo'])}\"{req}{ro}>{val}</textarea>" if tag == "textarea"
                    else f"<input name=\"{_e(n['campo'])}\"{tipo_html} value=\"{val}\" placeholder=\"{_e(n['dica'])}\"{req}{ro}>")
                 + "</label>")
    elif tipo in ("escolha", "escolha_livre"):
        req = " required" if n["obrigatorio"] else ""
        forma = n.get("forma", "lista") if tipo == "escolha" else "livre"
        s.append(f"<fieldset{ident}{escondido}><legend>{_e(n['rotulo'])} <small>({forma})</small></legend>")
        if forma == "cartoes":
            for o in n["opcoes"]:
                marca = " checked" if o["valor"] == n["valor"] else ""
                nota = f" <small>{_e(o['nota'])}</small>" if o.get("nota") else ""
                ic = f"{_e(o['icone'])} " if o.get("icone") else ""
                s.append(f'<label><input type="radio" name="{_e(n["campo"])}" value="{_e(o["valor"])}"{marca}{req}> {ic}{_e(o["rotulo"])}{nota}</label>')
        else:
            lista = f' list="{_e(n["campo"])}-sugestoes"' if forma == "livre" else ""
            if forma == "livre":
                s.append(f'<input name="{_e(n["campo"])}" value="{_e(n["valor"])}"{lista}{req}>')
                s.append(f'<datalist id="{_e(n["campo"])}-sugestoes">')
                for o in n["opcoes"]:
                    s.append(f'<option value="{_e(o["valor"])}">{_e(o["rotulo"])}</option>')
                s.append("</datalist>")
            else:
                s.append(f'<select name="{_e(n["campo"])}"{req}>')
                for o in n["opcoes"]:
                    marca = " selected" if o["valor"] == n["valor"] else ""
                    s.append(f'<option value="{_e(o["valor"])}"{marca}>{_e(o["rotulo"])}</option>')
                s.append("</select>")
        s.append("</fieldset>")
    elif tipo == "arquivo":
        req = " required" if n["obrigatorio"] else ""
        s.append(f'<label{escondido}>{_e(n["rotulo"])} <input type="file" name="{_e(n["campo"])}"{req}> '
                 f'<small>aceita: {", ".join(n["aceita"]) or "qualquer"}; até {n["max_bytes"]} bytes</small></label>')
    elif tipo == "documento":
        tam = f" · {n['tamanho']} bytes" if n.get("tamanho") else ""
        s.append(f"<p{ident}{escondido}>📄 {_e(n['titulo'])} <small>({_e(n['formato'])}{tam}; lê por "
                 f"<code>{_e(n['ler']['operacao'])}</code>)</small></p>")
    elif tipo == "copiar":
        s.append(f'<p{ident}{escondido}><button type="button">{_e(n["rotulo"])}</button> <code>{_e(n["valor"])}</code></p>')
    elif tipo == "autorizar":
        s.append(f'<p{ident}{escondido}>{_e(n["motivo"])}<br><a href="{_e(n["url"])}" rel="noopener">{_e(n["rotulo"])}</a> '
                 f'<small>→ <strong>{_e(n["onde"])}</strong></small></p>')
    elif tipo == "cronometro":
        s.append(f'<p{ident}{escondido}><button type="button">{_e(n["rotulo"])}</button> <time>{n["segundos"]} s</time> '
                 f"<small>(contagem regressiva; não começa sozinha)</small></p>")
    elif tipo == "progresso":
        rot = f"{_e(n['rotulo'])} " if n.get("rotulo") else ""
        s.append(f'<p{ident}{escondido}>{rot}<progress value="{n["feito"]}" max="{n["de"]}"></progress> {n["feito"]} de {n["de"]}</p>')
    elif tipo == "grafico":
        s.append(f"<figure{ident}{escondido}><figcaption>{_e(n['titulo'])} <small>({_e(n['forma'])})</small></figcaption><table>")
        s.append("<tr><th></th>" + "".join(f"<th>{_e(sr['rotulo'])} <small>{_e(sr['cor'])}</small></th>" for sr in n["series"]) + "</tr>")
        for p in n["pontos"]:
            s.append(f"<tr><th>{_e(p['rotulo'])}</th>" + "".join(f"<td>{'' if v is None else v}</td>" for v in p["valores"]) + "</tr>")
        s.append("</table></figure>")
    elif tipo == "calendario":
        s.append(f"<section{ident}{escondido}><h3>Calendário ({_e(n['vista'])}) {_e(n['de'])}</h3><ul>")
        for ev in n["eventos"]:
            s.append(f"<li><time>{_e(ev['inicio'])}</time>{(' – ' + _e(ev['fim'])) if ev['fim'] else ''} {_e(ev['titulo'])}"
                     f"{(' <small>' + _e(ev['detalhe']) + '</small>') if ev['detalhe'] else ''}</li>")
        s.append("</ul>")
        if n.get("acoes_do_evento"):
            s.append("<p><small>ações por evento: " + ", ".join(
                f"{a.get('titulo') or '(arrastar)'}→{a.get('enviar') or a.get('mostrar')}" for a in n["acoes_do_evento"]) + "</small></p>")
        s.append("</section>")
    elif tipo == "cartao_bancario":
        for c in n["cartoes"]:
            s.append(f"<article{escondido}><h3>{_e(c['titulo'])} <small>{_e(c['tipo'])} {_e(c['bandeira'])}</small></h3>")
            s.append(f"<p>{_e(c['numero'])}</p>")
            if c["fatura"] or c["limite"]:
                s.append(f"<dl><dt>{_e(c['fatura_rotulo'] or 'fatura')}</dt><dd>{_e(c['fatura'])}</dd>"
                         f"<dt>{_e(c['limite_rotulo'] or 'limite')}</dt><dd>{_e(c['limite'])}</dd></dl>")
            s.append(f'<progress value="{c["progresso_feito"]}" max="{c["progresso_de"]}"></progress> {_e(c["progresso_texto"])}')
            if c["lancamentos"]:
                s.append("<ul>" + "".join(f"<li>{_e(l['icone'])} {_e(l['titulo'])} <small>{_e(l['subtitulo'])}</small> "
                                          f"<b>{_e(l['valor'])}</b></li>" for l in c["lancamentos"]) + "</ul>")
            s.append("</article>")
    elif tipo == "distribuicao":
        s.append(f"<figure{ident}{escondido}><figcaption>{_e(n['titulo'])}</figcaption><ul>")
        for i in n["itens"]:
            s.append(f"<li>{_e(i['rotulo'])}: {i['valor']} <small>{_e(i['texto'])} · {_e(i['tom'])}</small></li>")
        s.append("</ul></figure>")
    elif tipo == "lista_financeira":
        s.append(f"<section{ident}{escondido}><h3>{_e(n['titulo'])}</h3>")
        if n.get("busca"):
            s.append('<input type="search" placeholder="buscar">')
        s.append("<p><small>filtros: " + ", ".join(n["filtros"]) + "</small></p><ul>")
        for i in n["itens"]:
            s.append(f"<li><small>{_e(i['grupo'])}</small> {_e(i['icone'])} {_e(i['titulo'])} "
                     f"<small>{_e(i['subtitulo'])}</small> <b>{_e(i['valor'])}</b></li>")
        s.append("</ul></section>")
    elif tipo == "acoes":
        rod = " <!-- rodapé -->" if n.get("rodape") else ""
        s.append(f"<menu{ident}{escondido}>{rod}")
        for b in n["botoes"]:
            enf = f" ({b['enfase']})" if b.get("enfase") not in (None, "padrao") else ""
            if "enviar" in b:
                campos = f" <small>campos: {', '.join(b.get('campos') or []) or '—'}</small>" if "campos" in b else ""
                depois = (" <small>depois: " + ", ".join(f"{a['id']}={'mostra' if a['mostrar'] else 'esconde'}" for a in b["apos_enviar"]) + "</small>") if b.get("apos_enviar") else ""
                s.append(f'<li><button type="submit" name="operacao" value="{_e(b["enviar"])}">{_e(b["titulo"])}</button>{enf}{campos}{depois}</li>')
            else:
                alvos = ", ".join(f"{a['id']}" + ("" if a["mostrar"] is None else ("=mostra" if a["mostrar"] else "=esconde")) for a in b["alvos"])
                s.append(f'<li><button type="button">{_e(b["titulo"])}</button>{enf} <small>alterna: {alvos}</small></li>')
        s.append("</menu>")
    else:
        s.append(f"<!-- tipo de saída sem casca: {_e(tipo)} -->")


def casca(tela: dict, titulo: str = "cartão") -> str:
    """O cartão reconstruído como HTML nu. ⛔ Nenhum `<style>` — o feio é
    intencional: a hierarquia se prova antes da primeira cor."""
    s: list[str] = [
        "<!doctype html>", '<html lang="pt-BR"><head><meta charset="utf-8">',
        f"<title>{_e(titulo)}</title></head><body>",
        f"<!-- versão {_e(tela.get('versao'))}"
        + (f" · tema {_e(tela['tema'])}" if tela.get("tema") else "")
        + (f" · navegação {_e(tela['navegacao'])}" if tela.get("navegacao") else "")
        + " -->",
        "<form>",
    ]
    for n in tela.get("corpo") or []:
        _no(n, s)
    s.append("</form></body></html>")
    return "\n".join(s)
