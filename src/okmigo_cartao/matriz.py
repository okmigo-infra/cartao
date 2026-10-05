"""A MATRIZ DO CONTRATO: tudo o que um manifesto registrado obriga a provar.

    python -m okmigo_cartao matriz okmigo/manifesto.json [outro.json …] \\
        [--formato md|json] [--saida arquivo]
    python -m okmigo_cartao matriz okmigo/manifesto.json --conferir preenchida.json

É a peça comum «gerador da matriz» do `PADRAO-QA.md` (§3.2 e §12, no repo do
okmigo): uma linha por

  a. superfície × estado (§4.2: vazio, típico, cheio, texto longo, erro, sem
     permissão, carregando);
  b. TIPO de elemento usado × superfície — o cartão é percorrido inteiro,
     dentro dos moldes `_repetir_lista`, dos `fallback` e da variante
     `okmigoDesktop`, porque é ali que mora o que a tela desenha de verdade;
  c. ação × superfície (`Action.Submit`/`Execute`/`ToggleVisibility`/…, as
     ações do evento do calendário, o toque no dia, o autocompletar e os
     formulários sobrepostos), uma por alvo distinto;
  d. rota declarada e grupo da navegação agrupada;
  e. operação da `conversa` (e, com `operacoes` declaradas, cada operação que
     fica FORA da conversa);
  f. ferramenta do `agente`, mais uma linha para os `exemplos` e uma para o
     `orcamento`;
  g. declaração presente (`eventos`, `avisa_antes`, … `versao`).

Cada linha diz em que canal se prova (`web`, `android`, `ios`, `conversa`):
«—» quando o canal não se aplica, vazio quando se aplica e falta preencher.
`resultado` e `evidencia` nascem vazios. O ciclo preenche; `--conferir`
reprova a matriz com canal aplicável vazio, com `resultado` vazio (ou que não
diga «passou»), ou que não cubra o manifesto de HOJE.

⛔⛔ **Chave de topo que o gerador não conhece REPROVA.** A lista é fechada de
propósito: uma declaração nova que o gerador ignorasse em silêncio sumiria da
matriz, e o ciclo aprovaria um app sem nunca ter provado o que ela promete. O
gesto é acrescentar a chave à tabela §3.1 do `PADRAO-QA.md` E a este arquivo,
no mesmo PR em que ela nasce.

Puro: sem rede, só biblioteca padrão. Lê o manifesto como o okmigo o recebe.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .manifesto import e_manifesto

#: Os estados de cada tela — `PADRAO-QA.md` §4.2, na ordem de lá.
ESTADOS: dict[str, str] = {
    "vazio": "conta nova, nada cadastrado — tem de dizer que está vazio, não parecer quebrado",
    "tipico": "o cenário do roteiro",
    "cheio": "volume acima do que cabe (muitas linhas, muitos eventos, nomes longos)",
    "texto_longo": "nomes e descrições no teto que o contrato permite",
    "erro": "o serviço fora ou devolvendo erro — a tela diz algo legível, sem exceção crua",
    "sem_permissao": "a conta errada abrindo a tela — não vê dado de ninguém",
    "carregando": "rede lenta — sem piscar outra tela",
}

CANAIS = ("web", "android", "ios", "conversa")
COLUNAS = ("id", "slug", "categoria", "alvo", "o_que_provar", *CANAIS, "resultado", "evidencia")
#: A célula do canal que não se aplica. Qualquer outra coisa é «se aplica».
NAO_SE_APLICA = "—"
#: A ordem das categorias na matriz — a mesma da §3.2.
CATEGORIAS = ("superficie", "elemento", "acao", "rota", "navegacao", "conversa",
              "operacao", "agente", "declaracao")
FORMATO = "okmigo-matriz/1"

# Os canais da §3.1, por nome. «emulador» é Android E iOS, sempre (§4.3).
_TELA = ("web", "android", "ios")
_EMULADOR = ("android", "ios")
_PUSH = ("android", "ios")  # §6.3: o aviso se prova CHEGANDO num aparelho
_CONVERSA = ("conversa",)
_WEB = ("web",)
_WEB_CONVERSA = ("web", "conversa")
_TODOS = CANAIS
_CONTRATO: tuple[str, ...] = ()  # prova-se no teste do app e na trilha, não num canal

#: ⛔ As chaves de topo que o gerador CONHECE. Fora desta lista, reprova.
#: Valor: a declaração que gera linha (canais, o que provar), ou `None` para a
#: chave estrutural, que já vira linhas por outro caminho ou não promete nada
#: que se veja (`slug`, `endpoint`, `forma`, `descricao`, `tipo`).
#:
#: As frases são as da tabela §3.1 do `PADRAO-QA.md`. ⚠️ Seis chaves não estão
#: lá em 05/10/2026 — `vitrine_url` (o sohautos a declara), `busca`,
#: `em_breve` e `grupo` (o SDK deste pacote as emite), `propoe_na_vitrine` e
#: `marca` (documentadas no okmigo) —, e a frase delas foi tirada do registro
#: do okmigo; a linha correspondente da §3.1 tem de ser acrescentada lá.
DECLARACOES: dict[str, tuple[tuple[str, ...], str] | None] = {
    # estruturais
    "slug": None,
    "endpoint": None,
    "forma": None,
    "descricao": None,
    "tipo": None,
    "superficies": None,
    "rotas": None,
    "navegacao": None,
    "conversa": None,
    "operacoes": None,
    "agente": None,
    # declarações (§3.1)
    "eventos": (_TODOS, "o que o serviço devolve aparece na agenda da pessoa; remarcar "
                        "atualiza; sumir cancela (conversa + tela da Agenda)"),
    "avisa_antes": (_PUSH, "o aviso antes da hora chega num aparelho (§6.3)"),
    "relata_mudancas": (_PUSH, "aprovar, remarcar e cancelar chegam a quem marcou"),
    "marca_horario": (_CONVERSA, "pedir horário pelo @ do negócio funciona do lado do "
                                 "cliente, e a dona recebe (conversa dos dois lados)"),
    "convite": (_WEB_CONVERSA, "o convite chega, o aceite liga as duas contas, sem convite não instala"),
    "so_por_convite": (_WEB_CONVERSA, "o convite chega, o aceite liga as duas contas, sem convite não instala"),
    "aceita_contato": (_WEB_CONVERSA, "o convite chega, o aceite liga as duas contas, sem convite não instala"),
    "para_tipo": (_WEB, "o app aparece e instala só para o tipo declarado (amigo, socio); "
                        "fora dele, não aparece"),
    "publico": (_WEB, "o app aparece e instala só para o tipo declarado (amigo, socio); "
                      "fora dele, não aparece"),
    "recebe_documento": (_CONVERSA, "o documento passa pelo filtro de privacidade; sem a "
                                    "declaração, é barrado"),
    "quer_a_marca": (_TODOS, "o nome e a marca que a pessoa lê são os declarados, na vitrine, "
                             "na tela e na conversa"),
    "nome_visivel": (_TODOS, "o nome e a marca que a pessoa lê são os declarados, na vitrine, "
                             "na tela e na conversa"),
    "descricao_humana": (_TODOS, "o nome e a marca que a pessoa lê são os declarados, na "
                                 "vitrine, na tela e na conversa"),
    "historico_de_navegacao": (_EMULADOR, "reabrir o app volta ao estado declarado, e só a ele"),
    "estados_restauraveis": (_EMULADOR, "reabrir o app volta ao estado declarado, e só a ele"),
    "credencial_sondagem": (_CONTRATO, "a sondagem do okmigo responde com a credencial declarada"),
    "tenant_sondagem": (_CONTRATO, "a sondagem do okmigo responde com a credencial declarada"),
    "versao": (_CONTRATO, "o registrado é o do serviço (§2.2)"),
    # ⚠️ fora da §3.1 em 05/10/2026 — ver o comentário acima
    "marca": (_TODOS, "o nome e a marca que a pessoa lê são os declarados, na vitrine, na "
                      "tela e na conversa"),
    "vitrine_url": (_WEB, "a vitrine abre na origem declarada, e o retorno dela ao okmigo só "
                          "aceita essa origem"),
    "propoe_na_vitrine": (_WEB, "o que o serviço propõe chega ao sócio como proposta para "
                                "refinar, nunca direto na página"),
    "busca": (_TELA, "a busca do aplicativo acha e abre só as rotas declaradas"),
    "em_breve": (_WEB, "o app aparece como «em breve» e a instalação é recusada; convite "
                       "aceito continua instalando"),
    "grupo": (_CONVERSA, "cada capacidade de grupo age só dentro da matriz de permissões "
                         "(docs/GRUPOS.md do cartao)"),
}
CHAVES_CONHECIDAS = frozenset(DECLARACOES)

#: As declarações que são LISTA de entradas com alvo próprio viram uma linha
#: por entrada; a chave diz de onde sai o alvo.
_POR_ENTRADA = {"estados_restauraveis": "superficie", "recebe_documento": "operacao"}

_O_QUE_PROVAR = {
    "superficie": "cada superfície abre, em cada estado (§4.2), nos três canais",
    "elemento": "desenha sem perder nó; o crivo pinado não o descartou "
                "(okmigo_cartao.validar + relatorio()); os campos que o serviço emite "
                "chegam à tela",
    "acao": "cada ação executa a operação certa, com os campos certos, e a tela reflete o "
            "resultado",
    "acao_escrita": "cada ação executa a operação certa, com os campos certos, e a tela "
                    "reflete o resultado; ação de escrita pede o gesto que o contrato manda",
    "acao_navegar": "cada rota abre; voltar volta",
    "acao_alternar": "o toque mostra e esconde os elementos-alvo, sem chamar o serviço",
    "rota": "cada rota abre; voltar volta",
    "navegacao": "a navegação agrupada mostra os grupos declarados; trocar de aba não pisca "
                 "outra tela",
    "conversa": "cada operação tem os casos da §5.2",
    "operacao": "o hub a chama pelo nome; a conversa NÃO a oferece (contrato do app + trilha)",
    "agente:ferramenta": "a ferramenta do agente é LEITURA no servidor",
    "agente:exemplos": "os exemplos (respondido, precisa_esclarecer, acao_proposta, "
                       "indisponivel) aparecem",
    "agente:orcamento": "o orçamento (chamadas, tokens, segundos) é respeitado",
}

#: Filhos estruturais de tabela e colunas: vivem e morrem com o pai, como no
#: `relatorio()` — não são «tipo usado» por si.
_ESTRUTURAIS = frozenset({"TableRow", "TableCell", "Column", "AdaptiveCard"})


class ChaveDesconhecida(ValueError):
    """Chave de topo do manifesto fora de `CHAVES_CONHECIDAS`."""


class ManifestoInvalido(ValueError):
    """O que foi dado não é um manifesto (sem `slug` ou sem `superficies`)."""


# ── o gerador ───────────────────────────────────────────────────────────────

def _linha(slug: str, id_: str, categoria: str, alvo: str, o_que_provar: str,
           canais: Iterable[str]) -> dict[str, str]:
    aplicaveis = set(canais)
    linha = {"id": id_, "slug": slug, "categoria": categoria, "alvo": alvo,
             "o_que_provar": o_que_provar}
    for c in CANAIS:
        linha[c] = "" if c in aplicaveis else NAO_SE_APLICA
    linha["resultado"] = ""
    linha["evidencia"] = ""
    return linha


def _texto(v: Any) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def _alvos_de_alternar(acao: dict) -> str:
    """Os alvos de um `ToggleVisibility`, em ordem fixa: `+id` mostra, `-id`
    esconde, `id` alterna às cegas. A ORDEM em que o autor os escreveu não
    muda o gesto — e mudaria o `id` da linha, que tem de ser estável."""
    alvos = set()
    for t in acao.get("targetElements") or []:
        if isinstance(t, str) and _texto(t):
            alvos.add(_texto(t))
        elif isinstance(t, dict) and _texto(t.get("elementId")):
            sinal = {True: "+", False: "-"}.get(t.get("isVisible"), "")
            alvos.add(sinal + _texto(t["elementId"]))
    return ",".join(sorted(alvos, key=lambda a: (a.lstrip("+-"), a)))


def _acao(no: dict) -> tuple[str, str, str] | None:
    """`(gesto, alvo, chave de frase)` de um `Action.*`, ou `None` quando ele
    não nomeia alvo nenhum — e por isso o crivo o descartaria."""
    tipo = no.get("type")
    dados = no.get("data") if isinstance(no.get("data"), dict) else {}
    if tipo == "Action.Submit":
        op = _texto(dados.get("operacao"))
        return ("enviar", op, "acao_escrita") if op else None
    if tipo == "Action.Execute":
        nav = dados.get("okmigoNavegar")
        if isinstance(nav, dict) and _texto(nav.get("rota")):
            return "navegar", _texto(nav["rota"]), "acao_navegar"
        op = _texto(dados.get("operacao"))
        return ("consultar", op, "acao") if op else None
    if tipo == "Action.ToggleVisibility":
        alvos = _alvos_de_alternar(no)
        return ("alternar", alvos, "acao_alternar") if alvos else None
    # Os outros (`ShowCard`, `OpenUrl`…) o crivo recusa ou descarta; a linha
    # existe para o ciclo PROVAR que a tela não os oferece.
    titulo = _texto(no.get("title"))
    gesto = str(tipo).split(".", 1)[1].lower() if "." in str(tipo) else str(tipo)
    return gesto, titulo or "?", "acao"


def _percorrer(cartao: Any) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Os tipos de elemento e as ações de UM cartão, na ordem em que aparecem,
    sem repetição. Percorre TUDO — `body`, `items`, `columns`, `rows`,
    `cells`, `actions`, `fallback`, `selectAction`, `okmigoDesktop` e os
    moldes `_repetir_lista` —, porque um elemento que só existe dentro de um
    molde é o que mais some sem ninguém ver (o crivo descarta a tabela que
    ficou só com cabeçalho)."""
    tipos: list[str] = []
    acoes: list[tuple[str, str, str]] = []

    def acao(a: tuple[str, str, str] | None) -> None:
        if a and a not in acoes:
            acoes.append(a)

    def visitar(no: Any, chave_do_pai: str) -> None:
        if isinstance(no, list):
            for filho in no:
                visitar(filho, chave_do_pai)
            return
        if not isinstance(no, dict):
            return
        tipo = no.get("type")
        if isinstance(tipo, str) and tipo.startswith("Action."):
            # O `okmigoAposEnviar` é a transição DO botão que grava, não um
            # gesto da pessoa: a linha do `enviar` já o cobre.
            if chave_do_pai != "okmigoAposEnviar":
                acao(_acao(no))
        elif isinstance(tipo, str) and tipo and tipo not in _ESTRUTURAIS:
            if tipo not in tipos:
                tipos.append(tipo)
            if no.get("okmigoSobreposto") is True:
                acao(("sobreposto", _texto(no.get("id")) or "?", "acao"))
            if tipo == "okmigoDocumento" and isinstance(no.get("ler"), dict):
                op = _texto(no["ler"].get("operacao"))
                if op:
                    acao(("consultar", op, "acao"))
            if _texto(no.get("okmigoBuscar")):
                acao(("autocompletar", _texto(no["okmigoBuscar"]), "acao"))
            if tipo == "okmigoCalendario":
                _do_calendario(no, acao)
        for chave, valor in no.items():
            if isinstance(valor, (dict, list)):
                visitar(valor, chave)

    visitar(cartao, "")
    return tipos, acoes


def _do_calendario(no: dict, acao) -> None:
    """As ações do calendário não são `Action.*`: são chaves próprias."""
    toque = no.get("aoTocarODia")
    if isinstance(toque, dict) and _texto(toque.get("mostrar")):
        acao(("tocar_o_dia", _texto(toque["mostrar"]), "acao"))
    for a in no.get("acoesDoEvento") or []:
        if not isinstance(a, dict):
            continue
        para = _texto(a.get("para")) or "?"
        if _texto(a.get("enviar")):
            gesto = "arrastar" if a.get("gesto") == "arrastar" else "enviar"
            acao((f"evento:{para}:{gesto}", _texto(a["enviar"]), "acao_escrita"))
        elif _texto(a.get("mostrar")):
            acao((f"evento:{para}:mostrar", _texto(a["mostrar"]), "acao"))
    nav = no.get("aoNavegarPeriodo")
    if isinstance(nav, dict) and _texto(nav.get("rota")):
        acao(("navegar", _texto(nav["rota"]), "acao_navegar"))


def chaves_desconhecidas(manifesto: dict) -> list[str]:
    return sorted(k for k in manifesto if k not in CHAVES_CONHECIDAS)


def _presente(v: Any) -> bool:
    return v not in (None, False, "", [], {})


def gerar(manifesto: dict) -> list[dict[str, str]]:
    """As linhas da matriz de UM manifesto, na ordem da §3.2.

    Levanta `ManifestoInvalido` se não for manifesto e `ChaveDesconhecida`
    se houver chave de topo fora da lista — sem gerar matriz parcial."""
    if not e_manifesto(manifesto) or not _texto(manifesto.get("slug")):
        raise ManifestoInvalido("não é um manifesto: falta `slug` ou a lista `superficies`")
    slug = _texto(manifesto["slug"])
    novas = chaves_desconhecidas(manifesto)
    if novas:
        raise ChaveDesconhecida(
            f"{slug}: chave de topo desconhecida "
            + ", ".join(f"`{k}`" for k in novas)
            + " — acrescente a chave à tabela §3.1 do PADRAO-QA e ao gerador "
            "(okmigo_cartao/matriz.py, DECLARACOES)"
        )
    por_categoria: dict[str, list[dict[str, str]]] = {c: [] for c in CATEGORIAS}

    def por(categoria: str, id_: str, alvo: str, frase: str, canais: Iterable[str]) -> None:
        por_categoria[categoria].append(_linha(slug, id_, categoria, alvo, frase, canais))

    # a, b, c — superfícies
    for s in manifesto["superficies"]:
        if not isinstance(s, dict):
            continue
        nome = _texto(s.get("nome")) or "?"
        for estado, como in ESTADOS.items():
            por("superficie", f"superficie:{nome}:{estado}", f"{nome} · {estado}",
                f"{_O_QUE_PROVAR['superficie']} — {estado}: {como}", _TELA)
        tipos, acoes = _percorrer(s.get("cartao"))
        for tipo in sorted(tipos):
            por("elemento", f"elemento:{nome}:{tipo}", f"{nome} · {tipo}",
                _O_QUE_PROVAR["elemento"], _TELA)
        for gesto, alvo, frase in sorted(acoes):
            por("acao", f"acao:{nome}:{gesto}:{alvo}", f"{nome} · {gesto} {alvo}",
                _O_QUE_PROVAR[frase], _TELA)

    # d — rotas e a navegação agrupada
    for r in manifesto.get("rotas") or []:
        if isinstance(r, dict) and _texto(r.get("nome")):
            destino = _texto(r.get("superficie"))
            por("rota", f"rota:{_texto(r['nome'])}",
                _texto(r["nome"]) + (f" → {destino}" if destino else ""),
                _O_QUE_PROVAR["rota"], _TELA)
    navegacao = manifesto.get("navegacao")
    if isinstance(navegacao, dict):
        for g in navegacao.get("grupos") or []:
            if isinstance(g, dict) and _texto(g.get("nome")):
                telas = ", ".join(_texto(x) for x in g.get("superficies") or [])
                por("navegacao", f"navegacao:{_texto(g['nome'])}",
                    f"{_texto(g.get('rotulo')) or _texto(g['nome'])} ({telas})",
                    _O_QUE_PROVAR["navegacao"], _TELA)

    # e — a conversa, e o que fica fora dela
    conversa = [_texto(x) for x in manifesto.get("conversa") or [] if _texto(x)]
    declaradas = [_texto(o.get("nome")) for o in manifesto.get("operacoes") or []
                  if isinstance(o, dict) and _texto(o.get("nome"))]
    if not conversa and declaradas:
        # Sem a lista `conversa`, toda operação declarada entra no catálogo do
        # modelo — é o que o registro do okmigo faz.
        conversa = declaradas
    for op in dict.fromkeys(conversa):
        por("conversa", f"conversa:{op}", op, _O_QUE_PROVAR["conversa"], _CONVERSA)
    for op in dict.fromkeys(declaradas):
        if op not in conversa:
            por("operacao", f"operacao:{op}", op, _O_QUE_PROVAR["operacao"], _CONTRATO)

    # f — o agente
    agente = manifesto.get("agente")
    if isinstance(agente, dict):
        for f in agente.get("ferramentas") or []:
            nome_f = _texto(f.get("nome") if isinstance(f, dict) else f)
            if nome_f:
                por("agente", f"agente:ferramenta:{nome_f}", nome_f,
                    _O_QUE_PROVAR["agente:ferramenta"], _CONVERSA)
        if _presente(agente.get("exemplos")):
            n = len(agente["exemplos"]) if isinstance(agente["exemplos"], list) else 1
            por("agente", "agente:exemplos", f"{n} exemplo(s)",
                _O_QUE_PROVAR["agente:exemplos"], _CONVERSA)
        if _presente(agente.get("orcamento")):
            o = agente["orcamento"]
            alvo = (", ".join(f"{k}={o[k]}" for k in sorted(o)) if isinstance(o, dict)
                    else _texto(o))
            por("agente", "agente:orcamento", alvo, _O_QUE_PROVAR["agente:orcamento"],
                _CONVERSA)

    # g — as declarações presentes, na ordem da tabela
    for chave, regra in DECLARACOES.items():
        if regra is None or not _presente(manifesto.get(chave)):
            continue
        canais, frase = regra
        valor = manifesto[chave]
        if chave in _POR_ENTRADA and isinstance(valor, list):
            campo = _POR_ENTRADA[chave]
            for entrada in valor:
                alvo = _texto(entrada.get(campo)) if isinstance(entrada, dict) else ""
                if alvo:
                    por("declaracao", f"declaracao:{chave}:{alvo}", f"{chave} · {alvo}",
                        frase, canais)
            continue
        por("declaracao", f"declaracao:{chave}", chave, frase, canais)

    linhas = [l for c in CATEGORIAS for l in por_categoria[c]]
    # ⛔ O `id` é a chave do `--conferir`: repetido, uma linha preenchida
    # cobriria a outra sem ninguém ver.
    vistos: set[str] = set()
    for l in linhas:
        if l["id"] in vistos:
            raise ManifestoInvalido(f"{slug}: id repetido na matriz: {l['id']}")
        vistos.add(l["id"])
    return linhas


def gerar_de_varios(manifestos: Iterable[dict]) -> dict[str, Any]:
    """O documento da matriz (o que `--formato json` escreve)."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        versao = version("okmigo-cartao")
    except PackageNotFoundError:  # pragma: no cover — rodando de src/ sem instalar
        versao = "?"
    lista = list(manifestos)
    linhas: list[dict[str, str]] = []
    for m in lista:
        linhas.extend(gerar(m))
    return {
        "formato": FORMATO,
        "gerado_por": f"okmigo-cartao {versao}",
        "manifestos": [{"slug": _texto(m.get("slug")), "versao": _texto(m.get("versao"))}
                       for m in lista],
        "colunas": list(COLUNAS),
        "linhas": linhas,
    }


def contagem(linhas: Iterable[dict[str, str]]) -> dict[str, int]:
    """Linhas por categoria, na ordem das categorias (só as que aparecem)."""
    n: dict[str, int] = {}
    for l in linhas:
        n[l["categoria"]] = n.get(l["categoria"], 0) + 1
    return {c: n[c] for c in CATEGORIAS if c in n}


# ── Markdown ────────────────────────────────────────────────────────────────

def _celula(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def em_markdown(documento: dict[str, Any]) -> str:
    s = ["# Matriz do contrato", "",
         f"Gerada por `{documento['gerado_por']}` ({documento['formato']}). "
         "Preencha cada canal que não está «—» e o `resultado`; confira com "
         "`python -m okmigo_cartao matriz <manifesto> --conferir <matriz.json>`.", ""]
    for m in documento["manifestos"]:
        linhas = [l for l in documento["linhas"] if l["slug"] == m["slug"]]
        resumo = ", ".join(f"{c} {n}" for c, n in contagem(linhas).items())
        s += [f"## {m['slug']} {m['versao']}".rstrip(), "",
              f"{len(linhas)} linhas — {resumo}.", "",
              "| " + " | ".join(COLUNAS) + " |",
              "|" + "---|" * len(COLUNAS)]
        for l in linhas:
            s.append("| " + " | ".join(_celula(l.get(c, "")) for c in COLUNAS) + " |")
        s.append("")
    return "\n".join(s)


# ── a conferência da matriz preenchida ──────────────────────────────────────

def _diz(v: Any, prefixo: str) -> bool:
    return str(v or "").strip().lower().startswith(prefixo)


def conferir(manifestos: Iterable[dict], preenchida: dict[str, Any]) -> tuple[list[str], list[str]]:
    """`(problemas, avisos)`. Matriz aprovada = `problemas` vazio.

    A régua é a matriz REGERADA do manifesto de hoje, não a que veio no
    arquivo: um canal que hoje se aplica e o arquivo marcou «—» está vazio."""
    esperadas = gerar_de_varios(manifestos)["linhas"]
    linhas = preenchida.get("linhas") if isinstance(preenchida, dict) else None
    if not isinstance(linhas, list):
        return ["a matriz preenchida não tem a lista `linhas` (é o JSON de --formato json?)"], []
    feitas: dict[tuple[str, str], dict] = {}
    for l in linhas:
        if isinstance(l, dict):
            feitas[(_texto(l.get("slug")), _texto(l.get("id")))] = l
    problemas: list[str] = []
    for e in esperadas:
        chave = (e["slug"], e["id"])
        onde = f"{e['slug']} {e['id']}"
        f = feitas.pop(chave, None)
        if f is None:
            problemas.append(f"{onde}: linha nova no manifesto, sem par na matriz preenchida "
                             "— regenere a matriz e prove a linha")
            continue
        for c in CANAIS:
            if e[c] == NAO_SE_APLICA:
                continue
            valor = str(f.get(c) or "").strip()
            if not valor or valor == NAO_SE_APLICA:
                problemas.append(f"{onde}: canal `{c}` vazio")
            elif _diz(valor, "falhou"):
                problemas.append(f"{onde}: canal `{c}` falhou")
        resultado = str(f.get("resultado") or "").strip()
        if not resultado:
            problemas.append(f"{onde}: `resultado` vazio")
        elif _diz(resultado, "falhou"):
            problemas.append(f"{onde}: `resultado` falhou")
        elif not _diz(resultado, "passou"):
            problemas.append(f"{onde}: `resultado` não diz «passou» nem «falhou»: {resultado!r}")
    avisos = [f"{s} {i}: linha que o manifesto de hoje não tem mais (ignorada)"
              for s, i in sorted(feitas)]
    return problemas, avisos


# ── a linha de comando ──────────────────────────────────────────────────────

def _ler_json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))


def main_matriz(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="okmigo-cartao matriz",
        description="Gera a matriz do contrato (PADRAO-QA §3.2) de um ou mais manifestos, "
                    "ou confere uma matriz preenchida.",
    )
    p.add_argument("manifestos", nargs="+", type=Path, help="o manifesto registrado (JSON)")
    p.add_argument("--formato", choices=("md", "json"), default="md",
                   help="md (padrão) para ler, json para preencher e conferir")
    p.add_argument("--saida", type=Path, help="escreve neste arquivo em vez da saída padrão")
    p.add_argument("--conferir", type=Path, metavar="MATRIZ_PREENCHIDA_JSON",
                   help="reprova se falta canal, resultado, ou linha do manifesto de hoje")
    a = p.parse_args(argv)

    manifestos = []
    try:
        for caminho in a.manifestos:
            m = _ler_json(caminho)
            if not isinstance(m, dict):
                raise ManifestoInvalido("não é um manifesto: o topo não é um objeto")
            gerar(m)  # reprova chave desconhecida ANTES de escrever qualquer coisa
            manifestos.append(m)
    except (ChaveDesconhecida, ManifestoInvalido) as e:
        print(f"✗ {caminho}: {e}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as e:
        print(f"✗ {caminho}: {e}", file=sys.stderr)
        return 2

    if a.conferir:
        try:
            preenchida = _ler_json(a.conferir)
        except (OSError, json.JSONDecodeError) as e:
            print(f"✗ {a.conferir}: {e}", file=sys.stderr)
            return 2
        problemas, avisos = conferir(manifestos, preenchida)
        for linha in avisos:
            print(f"  ℹ️ {linha}")
        if problemas:
            print(f"✗ matriz REPROVADA — {len(problemas)} pendência(s):")
            for linha in problemas:
                print(f"  ✗ {linha}")
            return 1
        print("✓ matriz completa: toda linha do manifesto de hoje tem canal e resultado")
        return 0

    documento = gerar_de_varios(manifestos)
    texto = (json.dumps(documento, ensure_ascii=False, indent=2) + "\n"
             if a.formato == "json" else em_markdown(documento))
    if a.saida:
        a.saida.write_text(texto, encoding="utf-8")
        resumo = "; ".join(
            f"{m['slug']} {sum(1 for l in documento['linhas'] if l['slug'] == m['slug'])}"
            for m in documento["manifestos"])
        print(f"✓ {len(documento['linhas'])} linha(s) em {a.saida} ({resumo})")
    else:
        sys.stdout.write(texto)
    return 0
