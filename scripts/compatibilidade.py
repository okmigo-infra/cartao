"""A versão nova do crivo aceita e expande os cartões de hoje IGUAL à anterior?

⛔⛔ Por que isto existe: os consumidores pinam o cartão por SHA e só recebem a
versão nova quando alguém abre a PR que troca o pino. Até aqui, a única prova
de que a versão nova não estragava nada era o CI DELES, depois da tag — cada
um descobrindo sozinho, e só se o cartão dele por acaso tocasse no que mudou.
Este passo faz a pergunta ANTES da tag, aqui, com os mesmos cartões:

    python3 scripts/compatibilidade.py                   # corpus público × última tag
    python3 scripts/compatibilidade.py --base v0.20.0    # contra outra versão
    python3 scripts/compatibilidade.py --consumidores ../ # os cartões REAIS (local)

Cada versão roda num processo próprio, com o `src/` dela no `PYTHONPATH`; os
dois recebem os MESMOS cartões e os MESMOS dados. Para cada superfície há
cinco cenários, porque validar o molde cru não prova a expansão:

- `cru`           — o molde sem dados (o que se vê validando sem expandir);
- `vazio`         — o resumo preenchido e toda lista vazia (o estado «sem nada»);
- `tipico`        — três linhas de dados com a forma que o molde pede;
- `muitas_linhas` — 250 linhas e 60 itens por sublista (acima dos tetos de
                    200 linhas de tabela e 50 itens de `_de`);
- `textos_longos` — três linhas com textos de 1.200 caracteres e números nos
                    extremos (zero, negativo, 10¹², 0,01).

⚠️ Os dois extremos são SEPARADOS de propósito: 250 linhas × 1.200 caracteres
num molde grande expande para gigabytes antes de o crivo contar o primeiro nó
(medido: um molde de 47 KB chegou a 3,5 GB), e o que se mediria é a memória da
máquina, não o crivo.

Os dados são SINTÉTICOS e saem da forma do próprio molde (`{campo}`,
`_repetir_lista`, `_de`, `_quando`), então funcionam para qualquer cartão sem
que ninguém escreva fixture.

O que conta como quebra (e exige o slot de quebra da versão — em `0.x`, o
MENOR; de `1.0` em diante, o MAIOR):

- um cartão que passava e agora é RECUSADO;
- um nó a menos, ou um tipo a menos, na tela reconstruída (o crivo passou a
  COMER alguma coisa — o modo de falha desta plataforma, que nunca dá erro);
- um texto acessível a menos (`alt` de imagem, `rotulo` de campo, `titulo`
  de botão);
- um aplicativo Python que compilava e agora levanta exceção.

E o que exige versão MENOR mesmo sem quebrar: o SDK compilar o mesmo
aplicativo num JSON diferente. O CI de cada consumidor confere que o manifesto
é o que o gerador produz, então a PR de pino chegaria VERMELHA lá.

O resto (a saída mudou sem perder nada; um cartão recusado passou a entrar)
é relatado e cabe em qualquer número.

⚠️ `--consumidores` lê `origin/main` de cada repo vizinho por `git archive`,
sem tocar a árvore de trabalho, e NUNCA escreve nada daquilo no disco deste
repo — o relatório só dá contagens. `--anonimizar` é o único caminho para um
cartão real entrar aqui, e ele troca todo texto, nome de campo, operação, rota
e endereço por pseudônimo, guardando só a FORMA (ver `anonimizar()`).
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "tests" / "compat" / "corpus"
EXEMPLOS = RAIZ / "exemplos"

CENARIOS = ("cru", "vazio", "tipico", "muitas_linhas", "textos_longos")

#: A configuração com que o corpus é conferido. Os domínios são reservados
#: (`.exemplo` não resolve), e o anonimizador aponta para eles as imagens
#: «nossas» e «de terceiro» dos cartões reais.
DOMINIO_NOSSO = "produto.exemplo"
DOMINIO_TERCEIRO = "terceiro.exemplo"

# ── Os dados sintéticos, tirados da forma do molde ─────────────────────────

_CAMPO = re.compile(r"\{([a-zA-Z0-9_.]+)\}")
_PREFIXO = re.compile(r"^(url|data|hora|num|txt)\d+$")
_CATEGORIAS = (
    # Texto que DESCREVE uma coisa vem antes da coisa: `foto_descricao` é o
    # `alt` da foto, não o endereço dela.
    ("txt", re.compile(r"descricao|legenda|alt|titulo|nome|rotulo|texto|explicacao")),
    ("url", re.compile(r"url|foto|imagem|img|logo|avatar|capa|miniatura")),
    ("hora", re.compile(r"hora|horario")),
    ("data", re.compile(r"(^|_)(data|dia|vencimento|prazo|inicio|fim|ate|desde)($|_)")),
    ("num", re.compile(
        r"valor|total|saldo|preco|quantidade|qtd|percent|progresso|pontos|"
        r"contagem|numero|nota|media|meta|atual|maximo|minimo|peso|altas|quedas")),
)


def categoria(nome: str) -> str:
    """O que um campo parece guardar. O anonimizador ESCREVE a categoria no
    pseudônimo (`num3`, `url7`) e aqui ela é lida de volta — assim o cartão
    anonimizado recebe dados da mesma natureza que o real, e a fidelidade da
    forma se confere (mesmos nós, mesmos tipos)."""
    folha = nome.rsplit(".", 1)[-1].lower()
    m = _PREFIXO.match(folha)
    if m:
        return m.group(1)
    for cat, rx in _CATEGORIAS:
        if rx.search(folha):
            return cat
    return "txt"


class Forma:
    """O que um molde pede de dados: campos soltos, a lista da superfície,
    as sublistas (`_de`) e os filtros (`_quando`)."""

    def __init__(self) -> None:
        self.campos: set[str] = set()
        self.linhas: Forma | None = None
        self.listas: dict[str, Forma] = {}
        self.quando: dict[str, list[str]] = {}


def forma_de(molde: Any, forma: Forma | None = None, *, no_topo: bool = True) -> Forma:
    forma = forma or Forma()
    if isinstance(molde, str):
        forma.campos.update(_CAMPO.findall(molde))
    elif isinstance(molde, list):
        for x in molde:
            forma_de(x, forma, no_topo=no_topo)
    elif isinstance(molde, dict):
        if "_repetir_lista" in molde:
            de = molde.get("_de")
            if isinstance(de, str):
                sub = forma.listas.setdefault(de, Forma())
            elif no_topo:
                sub = forma.linhas = forma.linhas or Forma()
            else:
                # Dentro de um item repetido a lista da superfície chega VAZIA
                # (é a regra do `expandir`): nada a gerar.
                return forma
            quando = molde.get("_quando")
            if isinstance(quando, dict) and isinstance(quando.get("campo"), str) \
                    and isinstance(quando.get("em"), list):
                sub.quando.setdefault(quando["campo"], [])
                sub.quando[quando["campo"]] += [str(v) for v in quando["em"]]
            forma_de(molde["_repetir_lista"], sub, no_topo=False)
            return forma
        for v in molde.values():
            forma_de(v, forma, no_topo=no_topo)
    return forma


_LONGO = ("Texto sintético longo para medir o teto do crivo " * 30)[:1200]
_NUMEROS_EXTREMOS = (0, -987654321.25, 1_000_000_000_000, 0.01)


def _valor(nome: str, i: int, extremo: bool) -> Any:
    cat = categoria(nome)
    if cat == "url":
        return f"/img/sintetica-{i}.png"
    if cat == "data":
        return f"2026-01-{i % 28 + 1:02d}"
    if cat == "hora":
        return f"{8 + i % 10:02d}:30"
    if cat == "num":
        return _NUMEROS_EXTREMOS[i % 4] if extremo else round(1234.5 * (i + 1), 2)
    return f"{_LONGO} {i}" if extremo else f"Texto {i + 1}"


def _por(caminho: str, valor: Any, alvo: dict) -> None:
    partes = caminho.split(".")
    for p in partes[:-1]:
        alvo = alvo.setdefault(p, {}) if isinstance(alvo.get(p, {}), dict) else {}
    alvo.setdefault(partes[-1], valor)


def _item(forma: Forma, i: int, extremo: bool, n_sub: int) -> dict:
    item: dict = {}
    for campo, valores in forma.quando.items():
        # Alterna entre os valores que o filtro aceita e um que ele recusa,
        # para o `_quando` ter o que peneirar.
        opcoes = [*dict.fromkeys(valores), "fora_do_filtro"]
        item[campo] = opcoes[i % len(opcoes)]
    for campo in sorted(forma.campos):
        _por(campo, _valor(campo, i, extremo), item)
    for chave, sub in sorted(forma.listas.items()):
        item[chave] = [_item(sub, j, extremo, 0) for j in range(n_sub)]
    return item


def dados_sinteticos(molde: Any, cenario: str, n: int | None = None) -> tuple[dict, list[dict]]:
    """`(resumo, linhas)` para um cenário. Determinístico: os dois lados da
    comparação recebem exatamente os mesmos bytes."""
    forma = forma_de(molde)
    extremo = cenario == "textos_longos"
    n_linhas = n if n is not None else {"vazio": 0, "tipico": 3, "muitas_linhas": 250,
                                        "textos_longos": 3}[cenario]
    n_sub = {"vazio": 0, "tipico": 3, "muitas_linhas": 60, "textos_longos": 3}[cenario]
    resumo = _item(forma, 0, extremo, n_sub)
    linhas = [_item(forma.linhas, i, extremo, n_sub) for i in range(n_linhas)] \
        if forma.linhas else []
    return resumo, linhas


# ── O que se mede numa tela reconstruída ───────────────────────────────────

def medir(tela: Any) -> dict:
    """Nós, tipos e textos acessíveis — de forma genérica, sem conhecer o
    vocabulário, para servir igual a qualquer versão do crivo."""
    tipos: dict[str, int] = {}
    a11y = {"alt": 0, "rotulo": 0, "titulo": 0}

    def andar(x: Any) -> None:
        if isinstance(x, dict):
            t = x.get("tipo")
            if isinstance(t, str):
                tipos[t] = tipos.get(t, 0) + 1
            for chave in a11y:
                if isinstance(x.get(chave), str) and x[chave].strip():
                    a11y[chave] += 1
            for v in x.values():
                andar(v)
        elif isinstance(x, list):
            for v in x:
                andar(v)

    andar(tela)
    return {"nos": sum(tipos.values()), "tipos": tipos, "a11y": a11y}


def _canonico(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(x: Any) -> str:
    return hashlib.sha256(_canonico(x).encode()).hexdigest()[:16]


def inferir_operacoes(cartao: Any) -> tuple[frozenset[str], frozenset[str]]:
    """O contrato mínimo que o cartão nomeia — a mesma regra do
    `preview.inferir_operacoes`, copiada aqui porque este arquivo roda também
    contra versões antigas, onde ela pode não existir."""
    esc: set[str] = set()
    lei: set[str] = set()

    def andar(v: Any) -> None:
        if isinstance(v, list):
            for x in v:
                andar(x)
            return
        if not isinstance(v, dict):
            return
        tipo, dados = v.get("type"), v.get("data")
        op = dados.get("operacao") if isinstance(dados, dict) else None
        if isinstance(op, str) and op:
            (esc if tipo == "Action.Submit" else lei if tipo == "Action.Execute" else set()).add(op)
        for chave, alvo in (("okmigoBuscar", lei), ("enviar", esc), ("consultar", lei)):
            if isinstance(v.get(chave), str) and v[chave]:
                alvo.add(v[chave])
        if tipo == "okmigoDocumento" and isinstance(v.get("ler"), dict):
            if isinstance(v["ler"].get("operacao"), str):
                lei.add(v["ler"]["operacao"])
        for x in v.values():
            andar(x)

    andar(cartao)
    return frozenset(esc), frozenset(lei)


def rotas_de(manifesto: dict) -> dict[str, dict] | None:
    if not isinstance(manifesto.get("rotas"), list):
        return None
    saida: dict[str, dict] = {}
    for r in manifesto["rotas"]:
        if isinstance(r, dict) and isinstance(r.get("nome"), str):
            saida[r["nome"]] = {
                str(p.get("nome")): {"tipo": str(p.get("tipo") or "texto"),
                                     "obrigatorio": p.get("obrigatorio") is not False}
                for p in r.get("parametros") or [] if isinstance(p, dict) and p.get("nome")
            }
    return saida


# ── O colhedor: roda DENTRO de uma versão ──────────────────────────────────

def _carregar_modulo(caminho: Path):
    for p in (caminho.parent, caminho.parent.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    nome = f"_compat_{abs(hash(str(caminho)))}"
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def manifestos_de_um_modulo(caminho: Path) -> dict[str, dict]:
    """Todo objeto do módulo que compila para um manifesto (`Aplicativo` e
    afins), pelo nome da variável. Dicionários prontos também contam."""
    from okmigo_cartao.manifesto import e_manifesto

    modulo = _carregar_modulo(caminho)
    saida: dict[str, dict] = {}
    for nome, obj in sorted(vars(modulo).items()):
        if nome.startswith("_") or isinstance(obj, type):
            continue
        compilado = None
        if hasattr(obj, "compilar") and callable(obj.compilar):
            compilado = obj.compilar()
        # Um mesmo aplicativo costuma ter dois nomes (`APLICATIVO` e
        # `APLICATIVO_X`); conta uma vez só.
        if e_manifesto(compilado) and _hash(compilado) not in {_hash(m) for m in saida.values()}:
            saida[nome] = compilado
    return saida


def conferir_superficies(manifesto: dict, dados_reais: dict | None, cenarios, teto: bool) -> dict:
    import okmigo_cartao as c

    cfg = c.Config(dominios=(DOMINIO_NOSSO,), base_de_imagens=f"https://{DOMINIO_NOSSO}")
    rotas = rotas_de(manifesto)
    todos = [s["cartao"] for s in manifesto["superficies"] if isinstance(s, dict)
             and isinstance(s.get("cartao"), dict)]
    esc, lei = inferir_operacoes(todos)

    def validar(bruto):
        try:
            return c.validar(bruto, esc, lei, config=cfg, rotas=rotas)
        except TypeError:  # versão sem `rotas`
            return c.validar(bruto, esc, lei, config=cfg)

    saida: dict[str, dict] = {}
    for sup in manifesto["superficies"]:
        if not isinstance(sup, dict) or not isinstance(sup.get("cartao"), dict):
            continue
        molde = sup["cartao"]
        res: dict[str, dict] = {}
        lotes = []
        for cen in cenarios:
            if cen == "cru":
                lotes.append((cen, molde))
            else:
                r, l = dados_sinteticos(molde, cen)
                lotes.append((cen, c.expandir(molde, r, l)))
        for nome_dado, d in sorted((dados_reais or {}).get(sup.get("nome"), {}).items()):
            lotes.append((f"exemplo:{nome_dado}",
                          c.expandir(molde, d.get("resumo") or {}, d.get("linhas") or [])))
        for cen, bruto in lotes:
            try:
                tela, erro = validar(bruto)
            except Exception as e:  # uma exceção É o achado
                tela, erro = None, f"EXCEÇÃO {type(e).__name__}: {e}"
            res[cen] = {"erro": erro, "hash": _hash(tela), **medir(tela)}
        if teto and forma_de(molde).linhas is not None:
            res["_teto"] = _teto_de_linhas(molde, validar, c.expandir)
            for nome_dado, d in sorted((dados_reais or {}).get(sup.get("nome"), {}).items()):
                if d.get("linhas"):
                    res[f"_teto:{nome_dado}"] = _teto_de_linhas(
                        molde, validar, c.expandir, d.get("resumo") or {}, d["linhas"])
        saida[str(sup.get("nome"))] = res
    return saida


def _teto_de_linhas(molde, validar, expandir, resumo=None, exemplo=None) -> int:
    """Quantas linhas a tela aguenta antes de o crivo recusá-la INTEIRA — com
    linhas sintéticas, ou repetindo as linhas de um exemplo do consumidor."""
    def passa(n):
        if exemplo:
            r, l = resumo, [copy.deepcopy(exemplo[i % len(exemplo)]) for i in range(n)]
        else:
            r, l = dados_sinteticos(molde, "tipico", n)
        return validar(expandir(molde, r, l))[1] is None
    if not passa(1):
        return 0
    # Sobe dobrando: um molde grande estoura em poucas linhas, e começar por
    # 2.048 custaria a memória que o cenário `muitas_linhas` evita.
    baixo, alto = 1, 2
    while passa(alto):
        baixo, alto = alto, alto * 2
        if alto > 4096:
            return baixo
    while alto - baixo > 1:
        meio = (baixo + alto) // 2
        baixo, alto = (meio, alto) if passa(meio) else (baixo, meio)
    return baixo


def colher(pedido: dict) -> dict:
    """Roda os casos do pedido na versão que o `PYTHONPATH` trouxe."""
    import okmigo_cartao as c

    esperado = pedido.get("src")
    origem = str(Path(c.__file__).resolve())
    if esperado and not origem.startswith(str(Path(esperado).resolve())):
        # ⛔ Sem isto, um `pip install -e .` no mesmo venv faria as DUAS
        # corridas usarem a árvore nova, e a comparação se aprovaria sozinha.
        raise SystemExit(f"✗ importei o okmigo_cartao de {origem}, e não de {esperado}")
    saida: dict[str, Any] = {"origem": origem, "casos": {}}
    for caso in pedido["casos"]:
        r: dict[str, Any] = {}
        try:
            if caso["tipo"] == "modulo":
                manifestos = manifestos_de_um_modulo(Path(caso["caminho"]))
            else:
                manifestos = {"manifesto": json.loads(Path(caso["caminho"]).read_text(encoding="utf-8"))}
        except Exception as e:  # o erro de carga É o achado
            saida["casos"][caso["id"]] = {"erro_de_carga": f"{type(e).__name__}: {e}"}
            continue
        for nome, m in manifestos.items():
            r[nome] = {
                "compilado": _hash(m) if caso["tipo"] == "modulo" else None,
                "superficies": conferir_superficies(
                    m, caso.get("dados"), pedido.get("cenarios", CENARIOS), pedido.get("teto", False)),
            }
        saida["casos"][caso["id"]] = {"manifestos": r}
    return saida


# ── A comparação ───────────────────────────────────────────────────────────

QUEBRA, REGENERAR, FORMA, NOVO = "quebra", "regenerar", "forma", "novo_aceito"


def comparar(base: dict, novo: dict) -> list[tuple[str, str, str]]:
    """`[(classe, onde, o_que)]` — só as diferenças."""
    achados: list[tuple[str, str, str]] = []
    for cid, cb in base["casos"].items():
        cn = novo["casos"].get(cid, {"erro_de_carga": "caso ausente na versão nova"})
        if "erro_de_carga" in cb:
            continue  # a base não carregava: exemplo novo, nada a comparar
        if "erro_de_carga" in cn:
            achados.append((QUEBRA, cid, f"não carrega mais: {cn['erro_de_carga']}"))
            continue
        for mn, mb in cb["manifestos"].items():
            mm = cn["manifestos"].get(mn)
            if mm is None:
                achados.append((QUEBRA, f"{cid}:{mn}", "o aplicativo sumiu"))
                continue
            if mb["compilado"] != mm["compilado"]:
                achados.append((REGENERAR, f"{cid}:{mn}", "o SDK compila outro JSON"))
            for sn, sb in mb["superficies"].items():
                sm = mm["superficies"].get(sn)
                if sm is None:
                    achados.append((QUEBRA, f"{cid}:{mn}:{sn}", "a superfície sumiu"))
                    continue
                for cen, rb in sb.items():
                    if cen.startswith("_"):
                        continue
                    rn = sm.get(cen)
                    onde = f"{cid}:{mn}:{sn}:{cen}"
                    if rn is None:
                        achados.append((QUEBRA, onde, "cenário sumiu"))
                    elif rb["hash"] == rn["hash"]:
                        continue
                    elif rb["erro"] is None and rn["erro"] is not None:
                        achados.append((QUEBRA, onde, f"passava e agora é recusada: {rn['erro']}"))
                    elif rb["erro"] is not None and rn["erro"] is None:
                        achados.append((NOVO, onde, f"era recusada ({rb['erro']}) e agora passa"))
                    elif rb["erro"] is not None:
                        continue  # recusada nos dois; o motivo pode ter mudado
                    else:
                        achados.append(_diferenca(onde, rb, rn))
    return achados


def _diferenca(onde: str, rb: dict, rn: dict) -> tuple[str, str, str]:
    perdas = []
    if rn["nos"] < rb["nos"]:
        perdas.append(f"nós {rb['nos']} → {rn['nos']}")
    for t, n in sorted(rb["tipos"].items()):
        if rn["tipos"].get(t, 0) < n:
            perdas.append(f"`{t}` {n} → {rn['tipos'].get(t, 0)}")
    for k, n in sorted(rb["a11y"].items()):
        if rn["a11y"].get(k, 0) < n:
            perdas.append(f"texto acessível `{k}` {n} → {rn['a11y'].get(k, 0)}")
    if perdas:
        return (QUEBRA, onde, "o crivo passou a comer: " + "; ".join(perdas))
    return (FORMA, onde, "a saída mudou sem perder nó, tipo nem texto acessível")


# ── SemVer: o número tem de dizer o que dói ────────────────────────────────

def _tupla(v: str) -> tuple[int, int, int]:
    p = [int(m.group()) if (m := re.match(r"^\d+", x)) else -1 for x in v.split(".")]
    return tuple((p + [0, 0, 0])[:3])


def salto(antes: str, agora: str) -> str:
    """`nenhum` · `correcao` · `menor` · `maior` — o que a versão andou."""
    a, b = _tupla(antes), _tupla(agora)
    if b <= a:
        return "nenhum"
    if b[0] > a[0]:
        return "maior"
    return "menor" if b[1] > a[1] else "correcao"


def exigido(classes: set[str], versao_base: str) -> str:
    """O menor salto que a pior classe achada pede."""
    em_zero = _tupla(versao_base)[0] == 0
    if QUEBRA in classes:
        return "menor" if em_zero else "maior"
    if REGENERAR in classes:
        return "menor"
    if classes:
        return "correcao"
    return "nenhum"


_ORDEM = ("nenhum", "correcao", "menor", "maior")


def basta(feito: str, pedido: str) -> bool:
    return _ORDEM.index(feito) >= _ORDEM.index(pedido)


# ── O orquestrador ─────────────────────────────────────────────────────────

def _git(*args: str, cwd: Path = RAIZ) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def base_padrao() -> str:
    """A tag mais nova que é ANCESTRAL de HEAD e não aponta para HEAD — é o
    que os consumidores têm (ou vão ter) quando a PR de pino chegar. Na
    esteira de publicação, a tag de HEAD é a que está nascendo."""
    aqui = _git("rev-parse", "HEAD")
    for tag in _git("tag", "--merged", "HEAD", "--sort=-v:refname", "--list", "v*").split():
        if _git("rev-list", "-n1", tag) != aqui:
            return tag
    raise SystemExit("✗ nenhuma tag ancestral de HEAD — sem base, não há o que comparar "
                     "(checkout raso? a esteira precisa de `fetch-depth: 0`)")


def versao_de(pyproject: str) -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    return m.group(1) if m else "0.0.0"


def extrair(ref: str, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / "base.tar"
    _git("archive", "--format=tar", "-o", str(arquivo), ref, "src", "pyproject.toml")
    with tarfile.open(arquivo) as t:
        _extrair_tudo(t, destino)
    return destino


def _extrair_tudo(t: tarfile.TarFile, destino: Path) -> None:
    try:
        t.extractall(destino, filter="data")
    except TypeError:  # Python sem o `filter` (anterior a 3.11.4)
        t.extractall(destino)  # o tar é o `git archive` deste repo


def rodar_versao(src: Path, pedido: dict) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({**pedido, "src": str(src)}, f)
    env = {**os.environ, "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, __file__, "--colher", f.name], env=env,
                       cwd=tempfile.gettempdir(), capture_output=True, text=True, check=False)
    os.unlink(f.name)
    if r.returncode != 0:
        raise SystemExit(f"✗ o colhedor falhou em {src}:\n{r.stderr[-3000:]}")
    return json.loads(r.stdout)


def casos_publicos() -> list[dict]:
    casos = [{"id": f"corpus/{p.stem}", "tipo": "json", "caminho": str(p)}
             for p in sorted(CORPUS.glob("*.json"))]
    casos += [{"id": f"exemplos/{p.stem}", "tipo": "modulo", "caminho": str(p)}
              for p in sorted(EXEMPLOS.glob("*.py"))]
    return casos


def _dados_de_exemplo(pasta: Path, superficies: set[str]) -> dict:
    """Os `examples/*.dados.json` que o consumidor já mantém para o preview:
    `{resumo, linhas}` casados pelo nome do arquivo, ou o mapa por superfície."""
    saida: dict[str, dict] = {}
    for p in sorted(pasta.glob("examples/*.json")) + sorted(pasta.glob("exemplos/*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        if "resumo" in d or "linhas" in d:
            nome = p.name.split(".")[0]
            if nome in superficies:
                saida.setdefault(nome, {})[p.name] = d
            continue
        mapa = d.get("superficies", d)
        if isinstance(mapa, dict):
            for nome, v in mapa.items():
                if nome in superficies and isinstance(v, dict):
                    saida.setdefault(nome, {})[p.name] = v
    return saida


def casos_dos_consumidores(raiz: Path, destino: Path) -> list[dict]:
    """Os cartões REAIS dos repositórios vizinhos, lidos de `origin/main`."""
    casos = []
    for repo in sorted(p for p in raiz.iterdir() if (p / ".git").is_dir()):
        try:
            arquivos = _git("ls-tree", "-r", "--name-only", "origin/main", "okmigo", cwd=repo).split()
        except RuntimeError:
            continue
        if not arquivos or repo.resolve() == RAIZ:
            continue
        alvo = destino / repo.name
        alvo.mkdir(parents=True)
        tar = alvo / "okmigo.tar"
        _git("archive", "--format=tar", "-o", str(tar), "origin/main", "okmigo", cwd=repo)
        with tarfile.open(tar) as t:
            _extrair_tudo(t, alvo)
        pasta = alvo / "okmigo"
        nomes: set[str] = set()
        jsons = [p for p in sorted(pasta.glob("*.json")) if _e_manifesto_em(p, nomes)]
        dados = _dados_de_exemplo(pasta, nomes)
        for p in sorted(pasta.glob("aplicativo_sdk_*.py")):
            casos.append({"id": f"{repo.name}/{p.stem}", "tipo": "modulo", "caminho": str(p), "dados": dados})
        for p in jsons:
            casos.append({"id": f"{repo.name}/{p.name}", "tipo": "json", "caminho": str(p), "dados": dados})
    return casos


def _e_manifesto_em(p: Path, nomes: set[str]) -> bool:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    ok = isinstance(d, dict) and isinstance(d.get("superficies"), list) \
        and any(isinstance(s, dict) and isinstance(s.get("cartao"), dict) for s in d["superficies"])
    if ok:
        nomes.update(str(s.get("nome")) for s in d["superficies"] if isinstance(s, dict))
    return ok


def resumo_de(colheita: dict) -> dict:
    """Contagens por cenário: quantas superfícies, aceitas, recusadas, nós."""
    tot: dict[str, dict] = {}
    for caso in colheita["casos"].values():
        for m in (caso.get("manifestos") or {}).values():
            for sup in m["superficies"].values():
                for cen, r in sup.items():
                    if cen.startswith("_"):
                        continue
                    chave = "exemplo" if cen.startswith("exemplo:") else cen
                    t = tot.setdefault(chave, {"telas": 0, "aceitas": 0, "nos_max": 0})
                    t["telas"] += 1
                    t["aceitas"] += r["erro"] is None
                    t["nos_max"] = max(t["nos_max"], r["nos"])
    return tot


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--colher", help=argparse.SUPPRESS)
    ap.add_argument("--base", help="ref do git para comparar (padrão: a tag ancestral mais nova)")
    ap.add_argument("--consumidores", type=Path,
                    help="pasta com os repos consumidores ao lado (lê origin/main; só local)")
    ap.add_argument("--teto", action="store_true", help="mede quantas linhas cada tela aguenta")
    ap.add_argument("--anonimizar", type=Path,
                    help="com --consumidores: escreve a FORMA anonimizada dos cartões nesta pasta")
    ap.add_argument("--json", action="store_true", help="imprime os achados em JSON")
    a = ap.parse_args(argv)

    if a.colher:
        print(json.dumps(colher(json.loads(Path(a.colher).read_text(encoding="utf-8"))), ensure_ascii=False))
        return 0

    with tempfile.TemporaryDirectory(prefix="compat-") as tmp:
        tmp = Path(tmp)
        casos = casos_publicos()
        if a.consumidores:
            casos = casos_dos_consumidores(a.consumidores.resolve(), tmp / "consumidores")
        if a.anonimizar:
            if not a.consumidores:
                raise SystemExit("✗ --anonimizar precisa de --consumidores")
            return escrever_corpus(casos, a.anonimizar)
        base_ref = a.base or base_padrao()
        base_dir = extrair(base_ref, tmp / "base")
        v_base = versao_de((base_dir / "pyproject.toml").read_text(encoding="utf-8"))
        v_novo = versao_de((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
        pedido = {"casos": casos, "cenarios": CENARIOS, "teto": a.teto}
        antes = rodar_versao(base_dir / "src", pedido)
        agora = rodar_versao(RAIZ / "src", pedido)

    achados = comparar(antes, agora)
    classes = {c for c, _, _ in achados}
    feito, pedido_salto = salto(v_base, v_novo), exigido(classes, v_base)
    if a.json:
        print(json.dumps({"base": base_ref, "versao_base": v_base, "versao": v_novo,
                          "achados": achados, "resumo": resumo_de(agora),
                          "exigido": pedido_salto, "feito": feito}, ensure_ascii=False, indent=1))
    else:
        print(f"  base {base_ref} ({v_base}) × árvore ({v_novo}) · {len(casos)} caso(s)")
        for cen, t in resumo_de(agora).items():
            print(f"  · {cen:8} {t['aceitas']}/{t['telas']} telas aceitas · até {t['nos_max']} nós")
        if a.teto:
            _imprimir_teto(agora)
        for classe in (QUEBRA, REGENERAR, NOVO, FORMA):
            do_tipo = [x for x in achados if x[0] == classe]
            if do_tipo:
                print(f"  {'✗' if classe == QUEBRA else '⚠️' if classe == REGENERAR else '·'} "
                      f"{classe}: {len(do_tipo)}")
                for _, onde, oque in do_tipo[:25]:
                    print(f"      {onde} — {oque}")
    if basta(feito, pedido_salto):
        if not achados:
            print("  ✅ a versão nova aceita e expande tudo IGUAL à base")
        else:
            print(f"  ✅ as diferenças pedem salto «{pedido_salto}», e a versão fez «{feito}»")
        return 0
    print(f"✗ as diferenças pedem salto «{pedido_salto}» ({v_base} → ?), "
          f"e a versão fez «{feito}» ({v_base} → {v_novo}).", file=sys.stderr)
    print("  Ou o crivo volta a aceitar igual, ou a versão diz no número o que dói "
          "— ver docs/COMPATIBILIDADE.md.", file=sys.stderr)
    return 1


def _imprimir_teto(colheita: dict) -> None:
    for cid, caso in sorted(colheita["casos"].items()):
        for mn, m in (caso.get("manifestos") or {}).items():
            for sn, sup in sorted(m["superficies"].items()):
                for k, v in sorted(sup.items()):
                    if k.startswith("_teto"):
                        fonte = k.partition(":")[2] or "sintético"
                        quanto = "sem teto até 4096" if v >= 4096 else f"{v} linha(s)"
                        print(f"      teto {cid}:{mn}:{sn} = {quanto} ({fonte})")


# ── O anonimizador: a FORMA de um cartão real, sem nada dele ───────────────

def vocabulario() -> set[str]:
    """Toda string CONSTANTE do código público do pacote. Se a palavra está no
    `src/` deste repo, ela já é pública — é vocabulário, não conteúdo."""
    voc: set[str] = set()
    for p in (RAIZ / "src" / "okmigo_cartao").rglob("*.py"):
        for no in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Constant) and isinstance(no.value, str) and len(no.value) <= 40:
                voc.add(no.value)
    return voc


_SO_SINAIS = re.compile(r"^[\s\W\d_]*$", re.UNICODE)
_NUMERICO = re.compile(r"^[\s\d.,:/%+\-T]*$")
_PALAVRAS = ("lorem", "ipsum", "dolor", "sit", "amet", "texto", "de", "exemplo", "sintetico", "forma")


class Anonimizador:
    """Troca por pseudônimo tudo o que não é vocabulário público.

    ⭐ A troca é CONSISTENTE: a mesma string vira sempre o mesmo pseudônimo, em
    qualquer lugar do manifesto. É o que mantém de pé as referências cruzadas —
    a operação do botão e o contrato inferido, o `id` do campo e o alvo do
    `ToggleVisibility`, a rota do `okmigoNavegar` e o catálogo de `rotas`, o
    `{campo}` do molde e o `_de` da sublista.

    ⚠️ O comprimento é preservado (com folga para o pseudônimo), porque os
    tetos de texto do crivo (40, 60, 120, 400) fazem parte da forma.
    """

    def __init__(self, voc: set[str]) -> None:
        self.voc = voc
        self.campos: dict[str, str] = {}
        self.palavras: dict[str, str] = {}
        self.urls: dict[str, str] = {}

    def campo(self, nome: str) -> str:
        if nome not in self.campos:
            partes = []
            for p in nome.split("."):
                self.campos.setdefault(p, f"{categoria(p)}{len(self.campos) + 1}")
                partes.append(self.campos[p])
            self.campos[nome] = ".".join(partes)
        return self.campos[nome]

    def _enchimento(self, n: int, semente: int) -> str:
        saida, i = [], semente
        while len(" ".join(saida)) < n:
            saida.append(_PALAVRAS[i % len(_PALAVRAS)])
            i += 3
        return " ".join(saida)[:max(n, 1)].strip() or "x"

    def palavra(self, s: str) -> str:
        if s not in self.palavras:
            k = len(self.palavras) + 1
            if re.search(r"\s", s.strip()):
                self.palavras[s] = self._enchimento(len(s), k)
            else:
                token = f"w{k}"
                self.palavras[s] = token + "x" * max(0, len(s) - len(token))
        return self.palavras[s]

    def nome(self, s: str) -> str:
        """Chave de objeto ou nome de parâmetro: fica se é vocabulário."""
        return s if s in self.voc else self.palavra(s)

    def url(self, s: str) -> str:
        if s not in self.urls:
            k = len(self.urls) + 1
            if s.startswith("/"):
                self.urls[s] = f"/img/u{k}.png"
            else:
                host = re.sub(r"^https?://", "", s).split("/")[0].lower()
                nosso = host.endswith("okmigo.com") or "r2." in host
                self.urls[s] = f"https://{DOMINIO_NOSSO if nosso else DOMINIO_TERCEIRO}/u{k}.png"
        return self.urls[s]

    def texto(self, s: str) -> str:
        if s in self.voc or _NUMERICO.match(s) or _SO_SINAIS.match(s):
            return s
        if re.match(r"^(https?://|/)", s):
            return self.url(s)
        if "{" in s:
            pedacos = re.split(r"(\{[a-zA-Z0-9_.]+\})", s)
            return "".join(
                "{" + self.campo(p[1:-1]) + "}" if _CAMPO.fullmatch(p)
                else p if _SO_SINAIS.match(p)
                else (" " if p.startswith(" ") else "") + self.palavra(p.strip()) + (" " if p.endswith(" ") else "")
                for p in pedacos
            )
        return self.palavra(s)

    def no(self, x: Any, chave: str = "") -> Any:
        if isinstance(x, dict):
            saida = {}
            for k, v in x.items():
                nk = k if k.startswith("_") else self.nome(k)
                if k == "_de" and isinstance(v, str):
                    saida[nk] = self.campo(v)
                elif k == "_quando" and isinstance(v, dict):
                    saida[nk] = {"campo": self.campo(str(v.get("campo"))),
                                 "em": [self.texto(str(e)) for e in v.get("em") or []]}
                else:
                    saida[nk] = self.no(v, k)
            return saida
        if isinstance(x, list):
            return [self.no(v, chave) for v in x]
        if isinstance(x, str):
            return x if chave == "type" else self.texto(x)
        return x


def anonimizar(manifesto: dict, anon: Anonimizador) -> dict:
    """Só o que o crivo lê: `superficies[].cartao` e o catálogo de `rotas`.
    Nome, slug, descrição, endpoint, fonte, agente — nada disso sai daqui."""
    saida: dict[str, Any] = {"superficies": []}
    for i, s in enumerate(manifesto.get("superficies") or []):
        if isinstance(s, dict) and isinstance(s.get("cartao"), dict):
            saida["superficies"].append({"nome": f"s{i + 1}", "cartao": anon.no(copy.deepcopy(s["cartao"]))})
    if isinstance(manifesto.get("rotas"), list):
        saida["rotas"] = [
            {"nome": anon.texto(str(r.get("nome"))),
             "parametros": [{"nome": anon.nome(str(p.get("nome"))),
                             "tipo": p.get("tipo", "texto"),
                             "obrigatorio": p.get("obrigatorio", True)}
                            for p in r.get("parametros") or [] if isinstance(p, dict)]}
            for r in manifesto["rotas"] if isinstance(r, dict)
        ]
    return saida


def escrever_corpus(casos: list[dict], pasta: Path) -> int:
    """Um arquivo por manifesto real, com nome neutro (`forma-NN.json`)."""
    # O colhedor carrega os módulos na versão da árvore para ter os manifestos.
    sys.path.insert(0, str(RAIZ / "src"))
    voc = vocabulario()
    pasta.mkdir(parents=True, exist_ok=True)
    vistos: set[str] = set()
    n = recusadas = 0
    for caso in casos:
        if caso["tipo"] == "modulo":
            manifestos = manifestos_de_um_modulo(Path(caso["caminho"]))
        else:
            manifestos = {"m": json.loads(Path(caso["caminho"]).read_text(encoding="utf-8"))}
        for m in manifestos.values():
            forma = anonimizar(m, Anonimizador(voc))
            h = _hash(forma)
            if h in vistos or not forma["superficies"]:
                continue
            vistos.add(h)
            infieis = fidelidade(m, forma)
            if infieis:
                # ⛔ Uma forma que não reproduz o real não prova nada sobre o
                # real — fica de fora, e o motivo aparece.
                recusadas += 1
                for x in infieis[:5]:
                    print(f"  ⚠️ {caso['id']}: forma infiel — {x}")
                continue
            n += 1
            (pasta / f"forma-{n:02d}.json").write_text(
                json.dumps(forma, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"  {n} manifesto(s) anonimizado(s) em {pasta}; {recusadas} infiel(is) ficaram de fora")
    return 0


def fidelidade(real: dict, forma: dict) -> list[str]:
    """A forma anonimizada se comporta como o real no crivo desta árvore?
    Mesma aceitação, mesmo número de nós e os mesmos tipos, superfície a
    superfície, nos cinco cenários. Devolve as divergências (sem conteúdo)."""
    reais = [s for s in real.get("superficies") or [] if isinstance(s, dict) and isinstance(s.get("cartao"), dict)]
    r = conferir_superficies({**real, "superficies": reais}, None, CENARIOS, False)
    a = conferir_superficies(forma, None, CENARIOS, False)
    saida = []
    for (_, sr), (na, sa) in zip(r.items(), a.items(), strict=True):
        for cen in CENARIOS:
            x, y = sr[cen], sa[cen]
            if (x["erro"] is None) != (y["erro"] is None) or x["nos"] != y["nos"] or x["tipos"] != y["tipos"]:
                saida.append(f"{na}:{cen} nós {x['nos']}→{y['nos']}, aceita {x['erro'] is None}→{y['erro'] is None}")
    return saida


if __name__ == "__main__":
    raise SystemExit(main())
