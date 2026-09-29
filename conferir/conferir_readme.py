#!/usr/bin/env python3
"""O README não pode contradizer o que o próprio repo declara (OMINFRA-832).

Uso:
    python3 conferir/conferir_readme.py            # confere; sai 1 se houver deriva
    python3 conferir/conferir_readme.py --listar   # os valores que o repo declara

Barato e sem rede: lê arquivos do repo (e, se o ``readme.json`` pedir, roda o
gerador de manifesto, que também não fala com ninguém). Só usa a biblioteca
padrão. ⭐ O MESMO arquivo é copiado em cada repo; o que muda de um para o
outro é só o ``conferir/readme.json``.

Três cheques:

1. **Marcadores.** Um valor no README entre marcadores é comparado com o que
   o repo declara::

       manifesto <!-- conferir: versao_manifesto -->`0.23.0`<!-- /conferir -->

   O conteúdo pode ocupar várias linhas (uma tabela inteira, por exemplo).
   Número por extenso («seis», «DOZE») vale como o algarismo.
   Chave desconhecida REPROVA — marcador com erro de digitação que passasse
   calado seria o defeito que este script existe para pegar.

   Chaves que vêm sozinhas de cada manifesto (``slug`` = o do manifesto; com
   um manifesto só, a forma sem ``:<slug>`` também vale):

   * ``versao_manifesto:<slug>``   — o ``versao``;
   * ``telas:<slug>``              — quantas ``superficies``;
   * ``conversa:<slug>``           — quantas operações na ``conversa``;
   * ``nome_visivel:<slug>``       — o ``nome_visivel``;
   * ``para_tipo:<slug>``          — o ``para_tipo``;
   * ``slugs``                     — o CONJUNTO dos slugs.

   ``manifestos`` é uma lista de globs de JSON, ou ``{"comando": [...]}``
   para o repo que não versiona o manifesto e o GERA (o ``python3`` do
   comando vira o interpretador que roda este script).

   As outras são declaradas no ``readme.json`` (``valores``), com uma fonte:

   * ``{"json": arq, "campo": "a.b"}`` / ``{"json": arq, "contar": "a.b"}``;
   * ``{"regex": padrão, "em": [globs]}``   — o grupo 1 do 1º acerto;
   * ``{"contar_regex": padrão, "em": [globs]}``;
   * ``{"contar_arquivos": [globs]}``;
   * ``{"nomes_regex": padrão, "em": [globs]}`` — CONJUNTO do grupo 1;
   * ``{"arquivos": [globs]}`` — CONJUNTO dos nomes de arquivo (no README,
     cada `` `nome.ext` `` entre crases);
   * ``{"comando": [...]}`` — a saída do comando (sem rede; roda na raiz);
   * ``{"rotas": [globs]}`` — CONJUNTO ``MÉTODO /caminho`` dos decoradores
     FastAPI (``@router.get("/x")``, com o ``prefix`` do ``APIRouter`` do
     mesmo arquivo) e das ``Route("/x", …, methods=[…])`` do Starlette;
     ``{param}`` vira ``{}``, e casa com qualquer segmento do README
     (``/v1/assets/PETR4``). ``"incluir"`` soma rotas que não nascem de
     decorador (o ``/docs`` do FastAPI, o ``/mcp`` montado).

   Com ``"tamanho": true``, a chave vale o TAMANHO do conjunto (quantas
   rotas, quantos nomes). Conjunto se compara igual; com
   ``"modo": "subconjunto"`` basta que o que o README cita exista no código
   (para o README que só RESUME).

2. **Datas no retrato.** Na seção do retrato (título que casa com
   ``retrato`` no ``readme.json``; padrão «Retrato»), toda linha de tabela,
   item de lista ou parágrafo que diga «no ar», «não existe» ou «bloqueado»
   tem de trazer uma data ``dd/mm``. Exceção: ``<!-- sem-data: motivo -->``
   na própria linha, ou um trecho listado em ``sem_data`` no ``readme.json``.

3. **Links relativos.** Todo ``[texto](caminho)`` do README que não é URL
   tem de apontar para um arquivo ou pasta que existe no repo. O link que sai
   do repo (``../calendar/…``) não se confere daqui e é pulado.

Antes dos três, o script prova a si mesmo (``_provar``): um README quebrado de
cada jeito tem de reprovar, e o certo tem de passar. Se não, sai 2.

O ``readme.json`` também aceita ``readme`` (padrão ``README.md``) e
``exigir_retrato`` (padrão ``true``: README sem seção de retrato reprova).
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = Path(__file__).resolve().parent / "readme.json"

MARCADOR = re.compile(
    r"<!--\s*conferir:\s*(?P<chave>[\w:.\-]+)\s*-->(?P<conteudo>.*?)<!--\s*/conferir\s*-->",
    re.DOTALL,
)
PALAVRAS = re.compile(r"\bno ar\b|\bn[ãa]o exist\w*|\bbloquead[oa]s?\b", re.IGNORECASE)
DATA = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
SEM_DATA = re.compile(r"<!--\s*sem-data\b")
METODOS = "GET|POST|PUT|PATCH|DELETE"
ROTA_NO_TEXTO = re.compile(
    rf"(?P<m>\b(?:{METODOS})(?:/(?:{METODOS}))*)\b[`\s|]*(?P<p>/[^\s`|)?]*)"
)
DECORADOR = re.compile(rf"@(\w+)\.({METODOS.lower()})\(\s*[\"']([^\"']*)[\"']")
PREFIXO = re.compile(
    r"(\w+)\s*=\s*APIRouter\([^)]*?prefix\s*=\s*[\"']([^\"']*)[\"']", re.DOTALL
)
ROTA_STARLETTE = re.compile(
    r"Route\(\s*[\"']([^\"']+)[\"'][^)]*?methods\s*=\s*\[([^\]]*)\]", re.DOTALL
)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


# «em seis superfícies», «os DOZE consumidores»: o número por extenso vale.
_EXTENSO = (
    "zero,um uma,dois duas,três tres,quatro,cinco,seis,sete,oito,nove,dez,onze,"
    "doze,treze,catorze quatorze,quinze,dezesseis,dezessete,dezoito,dezenove,vinte"
)
POR_EXTENSO = {p: n for n, ps in enumerate(_EXTENSO.split(",")) for p in ps.split()}


class Deriva(Exception):
    pass


# ── as fontes ─────────────────────────────────────────────────────────────────


def _arquivos(globs) -> list[Path]:
    if isinstance(globs, str):
        globs = [globs]
    achados: list[Path] = []
    for g in globs:
        for nome in sorted(glob.glob(str(RAIZ / g), recursive=True)):
            p = Path(nome)
            if p.is_file() and p not in achados:
                achados.append(p)
    if not achados:
        raise Deriva(f"a fonte {globs} não casa com arquivo nenhum")
    return achados


def _campo(dado, caminho: str):
    for parte in caminho.split("."):
        dado = dado[parte]
    return dado


def _normalizar_rota(metodo: str, caminho: str) -> str:
    caminho = re.sub(r"\{[^}]*\}", "{}", caminho.split("?")[0]).rstrip("/") or "/"
    return f"{metodo.upper()} {caminho}"


def _casa(a: str, b: str) -> bool:
    """`GET /v1/assets/PETR4` casa com `GET /v1/assets/{}` (e vice-versa)."""
    ma, _, pa = a.partition(" ")
    mb, _, pb = b.partition(" ")
    sa, sb = pa.split("/"), pb.split("/")
    return (
        ma == mb
        and len(sa) == len(sb)
        and all(x == y or "{}" in (x, y) for x, y in zip(sa, sb, strict=True))
    )


def _rotas_do_codigo(globs) -> set[str]:
    rotas: set[str] = set()
    for arq in _arquivos(globs):
        texto = arq.read_text(encoding="utf-8")
        prefixos = dict(PREFIXO.findall(texto))
        for objeto, metodo, caminho in DECORADOR.findall(texto):
            rotas.add(_normalizar_rota(metodo, prefixos.get(objeto, "") + caminho))
        for caminho, metodos in ROTA_STARLETTE.findall(texto):
            for metodo in re.findall(r"[A-Z]+", metodos):
                rotas.add(_normalizar_rota(metodo, caminho))
    return rotas


def _fonte(spec: dict):
    if "json" in spec:
        dado = json.loads((RAIZ / spec["json"]).read_text(encoding="utf-8"))
        if "contar" in spec:
            return len(_campo(dado, spec["contar"]))
        return _campo(dado, spec["campo"])
    if "regex" in spec:
        for arq in _arquivos(spec["em"]):
            m = re.search(spec["regex"], arq.read_text(encoding="utf-8"), re.MULTILINE)
            if m:
                return m.group(1)
        raise Deriva(f"o padrão {spec['regex']!r} não casa em {spec['em']}")
    if "contar_regex" in spec:
        return sum(
            len(
                re.findall(
                    spec["contar_regex"], a.read_text(encoding="utf-8"), re.MULTILINE
                )
            )
            for a in _arquivos(spec["em"])
        )
    if "contar_arquivos" in spec:
        return len(_arquivos(spec["contar_arquivos"]))
    if "nomes_regex" in spec:
        return {
            n
            for a in _arquivos(spec["em"])
            for n in re.findall(
                spec["nomes_regex"], a.read_text(encoding="utf-8"), re.MULTILINE
            )
        }
    if "rotas" in spec:
        return _rotas_do_codigo(spec["rotas"]) | set(spec.get("incluir", []))
    if "arquivos" in spec:
        return {a.name for a in _arquivos(spec["arquivos"])}
    if "comando" in spec:
        comando = [sys.executable if c == "python3" else c for c in spec["comando"]]
        return subprocess.run(
            comando, cwd=RAIZ, check=True, capture_output=True, text=True
        ).stdout.strip()
    raise Deriva(f"fonte sem tipo conhecido: {spec}")


def _manifestos(cfg: dict) -> list[dict]:
    fonte = cfg.get("manifestos")
    if not fonte:
        return []
    if isinstance(fonte, dict) and "comando" in fonte:
        comando = [sys.executable if c == "python3" else c for c in fonte["comando"]]
        saida = subprocess.run(
            comando, cwd=RAIZ, check=True, capture_output=True, text=True
        ).stdout
        dado = json.loads(saida)
        lista = list(dado.values()) if isinstance(dado, dict) else dado
        # o corpo de registro da ponte leva o manifesto dentro de `extras`
        return [
            {**m.get("extras", {}), **{k: v for k, v in m.items() if k != "extras"}}
            for m in lista
        ]
    return [json.loads(a.read_text(encoding="utf-8")) for a in _arquivos(fonte)]


def valores(cfg: dict) -> dict[str, dict]:
    """chave → {"valor": …, "modo": "igual"|"subconjunto"}."""
    saida: dict[str, dict] = {}
    manifestos = _manifestos(cfg)
    for m in manifestos:
        s = m["slug"]
        derivados = {
            "versao_manifesto": m.get("versao"),
            "telas": len(m["superficies"]) if "superficies" in m else None,
            "conversa": len(m["conversa"]) if "conversa" in m else None,
            "nome_visivel": m.get("nome_visivel"),
            "para_tipo": m.get("para_tipo"),
        }
        for chave, valor in derivados.items():
            if valor is None:
                continue
            saida[f"{chave}:{s}"] = {"valor": valor}
            if len(manifestos) == 1:
                saida[chave] = {"valor": valor}
    if manifestos:
        saida["slugs"] = {"valor": {m["slug"] for m in manifestos}}
    for chave, spec in cfg.get("valores", {}).items():
        valor = _fonte(spec)
        if spec.get("tamanho") and isinstance(valor, set):
            valor = len(valor)
        saida[chave] = {"valor": valor, "modo": spec.get("modo", "igual")}
    return saida


# ── o README ──────────────────────────────────────────────────────────────────


def _limpo(texto: str) -> str:
    texto = re.sub(r"[`*«»]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _conjunto_do_texto(chave: str, spec: dict, texto: str) -> set[str]:
    if "rotas" in spec:
        rotas = set()
        for m in ROTA_NO_TEXTO.finditer(texto):
            for metodo in m.group("m").split("/"):
                rotas.add(_normalizar_rota(metodo, m.group("p")))
        return rotas
    if "arquivos" in spec:
        return {
            Path(c).name
            for c in re.findall(
                r"`([\w./-]+\.(?:py|md|sql|json|ya?ml|sh|toml|txt|m?js|ts|dart))`",
                texto,
            )
        }
    linhas = [ln.strip() for ln in texto.strip().splitlines()]
    tabela = [ln for ln in linhas if ln.startswith("|")]
    if tabela:
        nomes = set()
        for ln in tabela:
            celula = ln.strip("|").split("|")[0].strip()
            if not celula or set(celula) <= set("-: ") or "`" not in celula:
                continue  # separador ou cabeçalho: nome de verdade vem entre crases
            nomes.add(_limpo(celula))
        return nomes
    crases = re.findall(r"`([^`]+)`", texto)
    if crases:
        return {c.strip() for c in crases}
    return {p.strip() for p in re.split(r",|·|;|\se\s", _limpo(texto)) if p.strip()}


def conferir_marcadores(texto: str, cfg: dict, declarados: dict) -> list[str]:
    erros = []
    specs = cfg.get("valores", {})
    for m in MARCADOR.finditer(texto):
        linha = texto.count("\n", 0, m.start()) + 1
        chave, conteudo = m.group("chave"), m.group("conteudo")
        if chave not in declarados:
            erros.append(f"linha {linha}: chave `{chave}` que o repo não declara")
            continue
        esperado = declarados[chave]["valor"]
        if isinstance(esperado, set):
            no_readme = _conjunto_do_texto(chave, specs.get(chave, {}), conteudo)
            if "rotas" in specs.get(chave, {}):
                falta_no_codigo = sorted(
                    r for r in no_readme if not any(_casa(r, c) for c in esperado)
                )
                falta_no_readme = sorted(
                    c for c in esperado if not any(_casa(r, c) for r in no_readme)
                )
            else:
                falta_no_codigo = sorted(no_readme - esperado)
                falta_no_readme = sorted(esperado - no_readme)
            if declarados[chave].get("modo") == "subconjunto":
                falta_no_readme = []
            if falta_no_codigo or falta_no_readme:
                partes = []
                if falta_no_codigo:
                    partes.append(
                        f"o README cita e o repo não tem: {', '.join(falta_no_codigo)}"
                    )
                if falta_no_readme:
                    partes.append(
                        f"o repo tem e o README não cita: {', '.join(falta_no_readme)}"
                    )
                erros.append(f"linha {linha}: `{chave}` — " + "; ".join(partes))
        elif _limpo(conteudo) != str(esperado) and not (
            str(esperado).isdigit()
            and POR_EXTENSO.get(_limpo(conteudo).lower()) == int(esperado)
        ):
            erros.append(
                f"linha {linha}: `{chave}` — o README diz {_limpo(conteudo)!r}, "
                f"o repo declara {str(esperado)!r}"
            )
    return erros


def _secoes_do_retrato(linhas: list[str], padrao: str) -> list[tuple[int, int]]:
    secoes, dentro, nivel, inicio = [], False, 0, 0
    titulo = re.compile(r"^(#{1,6})\s+(.*)")
    em_codigo = False
    for i, ln in enumerate(linhas):
        if ln.lstrip().startswith("```"):
            em_codigo = not em_codigo
        m = None if em_codigo else titulo.match(ln)
        if not m:
            continue
        n = len(m.group(1))
        if dentro and n <= nivel:
            secoes.append((inicio, i))
            dentro = False
        if not dentro and re.search(padrao, m.group(2), re.IGNORECASE):
            dentro, nivel, inicio = True, n, i + 1
    if dentro:
        secoes.append((inicio, len(linhas)))
    return secoes


def _unidades(linhas: list[str], inicio: int, fim: int):
    """Linha de tabela, item de lista (com continuação) ou parágrafo."""
    atual: list[str] = []
    comeco = inicio
    em_codigo = False
    item = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
    for i in range(inicio, fim):
        ln = linhas[i]
        if ln.lstrip().startswith("```"):
            em_codigo = not em_codigo
            continue
        if em_codigo:
            continue
        novo = (
            not ln.strip()
            or ln.lstrip().startswith("|")
            or item.match(ln)
            or ln.startswith("#")
        )
        if novo and atual:
            yield comeco, " ".join(atual)
            atual = []
        if not ln.strip() or ln.startswith("#"):
            continue
        if ln.lstrip().startswith("|"):
            yield i, ln
            continue
        if not atual:
            comeco = i
        atual.append(ln.strip())
    if atual:
        yield comeco, " ".join(atual)


def conferir_datas(texto: str, cfg: dict) -> list[str]:
    linhas = texto.splitlines()
    excecoes = cfg.get("sem_data", [])
    erros = []
    secoes = _secoes_do_retrato(linhas, cfg.get("retrato", r"^Retrato"))
    if not secoes and cfg.get("exigir_retrato", True):
        return [f"nenhuma seção de retrato casa com {cfg.get('retrato', '^Retrato')!r}"]
    for inicio, fim in secoes:
        for i, unidade in _unidades(linhas, inicio, fim):
            achado = PALAVRAS.search(unidade)
            if not achado or DATA.search(unidade) or SEM_DATA.search(unidade):
                continue
            if any(e in unidade for e in excecoes):
                continue
            erros.append(
                f"linha {i + 1}: «{achado.group(0)}» sem data dd/mm no retrato: "
                f"{unidade[:110]}…"
            )
    return erros


def conferir_links(texto: str, arquivo: Path) -> list[str]:
    erros = []
    em_codigo = False
    for n, ln in enumerate(texto.splitlines(), 1):
        if ln.lstrip().startswith("```"):
            em_codigo = not em_codigo
        if em_codigo:
            continue
        for alvo in LINK.findall(ln):
            if re.match(r"^[a-z][a-z0-9+.-]*:", alvo, re.IGNORECASE) or alvo.startswith(
                "#"
            ):
                continue
            caminho = alvo.split("#")[0]
            if not caminho:
                continue
            destino = (arquivo.parent / caminho).resolve()
            if RAIZ.resolve() not in (destino, *destino.parents):
                continue  # fora do repo (outro repo do workspace): não se confere daqui
            if not destino.exists():
                erros.append(
                    f"linha {n}: link para `{caminho}`, que não existe no repo"
                )
    return erros


def _provar() -> list[str]:
    """O cheque reprova o README quebrado? Roda a cada execução, antes do real:
    cheque que passa no cenário quebrado não é cheque."""
    cfg = {"valores": {"n": {"contar_arquivos": ["x"]}}}
    dec = {
        "versao_manifesto": {"valor": "1.2.0"},
        "n": {"valor": 3},
        "slugs": {"valor": {"a", "a-b"}},
        "rotas": {"valor": {"GET /x", "POST /x"}, "modo": "subconjunto"},
    }
    cfg["valores"]["rotas"] = {"rotas": ["x"]}
    dec["rotas"]["valor"] = {"GET /x", "POST /x", "GET /x/{}"}

    def m(chave, conteudo):
        return f"<!-- conferir: {chave} -->{conteudo}<!-- /conferir -->"

    casos = [  # (README, cheque, deve reprovar?)
        (m("versao_manifesto", "`1.2.0`"), "marcador", False),
        (m("versao_manifesto", "**1.1.0**"), "marcador", True),
        (m("n", "3"), "marcador", False),
        (m("n", "4"), "marcador", True),
        (m("n", "TRÊS"), "marcador", False),
        (m("n", "quatro"), "marcador", True),
        (m("inventada", "1"), "marcador", True),
        (m("slugs", "`a` e `a-b`"), "marcador", False),
        (m("slugs", "`a`"), "marcador", True),
        (m("rotas", "\n| `GET/POST` | `/x` |\n"), "marcador", False),
        (m("rotas", "\n| `GET` | `/y/{id}` |\n"), "marcador", True),
        (m("rotas", "- `GET /x/PETR4`"), "marcador", False),
        ("## Retrato\n\n| a | no ar desde 15/09 |\n", "datas", False),
        ("## Retrato\n\n| a | no ar |\n", "datas", True),
        ("## Retrato\n\n- o fiscal não existe,\n  medido em 28/09\n", "datas", False),
        ("## Retrato\n\nbloqueado pelo risco\n", "datas", True),
        ("## Retrato\n\nbloqueado <!-- sem-data: é regra -->\n", "datas", False),
        ("## Retrato\n\n## Outra\n\nno ar\n", "datas", False),
        ("[x](nao-existe-832.md)", "links", True),
        ("[x](https://example.com) [y](#ancora)", "links", False),
    ]
    falhas = []
    for texto, cheque, deve in casos:
        if cheque == "marcador":
            erros = conferir_marcadores(texto, cfg, dec)
        elif cheque == "datas":
            erros = conferir_datas(texto, {})
        else:
            erros = conferir_links(texto, RAIZ / "README.md")
        if bool(erros) != deve:
            falhas.append(
                f"{cheque}: {'passou' if deve else 'reprovou'} {texto!r} {erros}"
            )
    return falhas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--listar", action="store_true", help="mostra os valores declarados e sai"
    )
    args = ap.parse_args()
    falhas = _provar()
    if falhas:
        print("✗ o próprio cheque não reprova o README quebrado:", file=sys.stderr)
        for f in falhas:
            print(f"    {f}", file=sys.stderr)
        return 2
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    try:
        declarados = valores(cfg)
    except (
        Deriva,
        KeyError,
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as e:
        print(f"✗ não consegui ler o que o repo declara: {e!r}", file=sys.stderr)
        return 1
    if args.listar:
        for chave, v in sorted(declarados.items()):
            valor = v["valor"]
            print(f"{chave:40} {sorted(valor) if isinstance(valor, set) else valor}")
        return 0
    nome = cfg.get("readme", "README.md")
    arquivo = RAIZ / nome
    texto = arquivo.read_text(encoding="utf-8")
    erros = (
        conferir_marcadores(texto, cfg, declarados)
        + conferir_datas(texto, cfg)
        + conferir_links(texto, arquivo)
    )
    marcados = len(MARCADOR.findall(texto))
    if erros:
        print(f"✗ {nome}: {len(erros)} deriva(s) ({marcados} valor(es) marcado(s))")
        for e in erros:
            print(f"    {e}")
        return 1
    print(
        f"✓ {nome}: {marcados} valor(es) marcado(s) conferido(s), "
        "retrato datado, links vivos"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
