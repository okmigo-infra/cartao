"""O `__all__` não encolhe sem a versão dizer que encolheu.

⛔⛔ Por que isto existe: quem consome o cartão está pinado num SHA ANTIGO e vai,
um dia, receber a PR que troca o pino — e essa PR é aprovada pelo CI DELE, que
regenera o manifesto e compara. Só que um nome que sumiu do `__all__` não
chega nesse passo: quebra antes, no `import`, e a esteira inteira do consumidor
para com `ImportError`. São dez repositórios; o autor da renomeação está aqui,
sozinho, sem nenhum deles à vista.

⚠️ Este é o modo de falha inverso do que já aconteceu em 15/09: naquele dia os
oito apps passaram a importar `materializar_manifesto`, `CatalogoPublico`,
`TelaResumida`, `MarcaHorario` e `OperacaoParametrizada` — nomes que o SHA
pinado NÃO tinha. Mergear qualquer app antes do cartão daria `ImportError` em
todos. Acrescentar nome e tirar nome falham pelo mesmo lugar; este passo cobre
o lado que está deste repo.

⭐ A regra: tirar nome é mudança que QUEBRA, e em `0.x` o slot de quebra é o
MENOR (`0.6.x → 0.7.0`); de `1.0` em diante, o MAIOR. Encolher com bump de
correção (`0.6.0 → 0.6.1`) é recusado — não porque tirar seja proibido, mas
porque o consumidor precisa conseguir LER no número que vai doer.

⭐ E o número não basta: o nome tem de ter AVISADO antes. Só sai do `__all__`
o nome que a base já declarava em `depreciacao.DEPRECIACOES`, e só a partir da
versão `sai_em` que aquela declaração prometeu — é a janela que deixa o
consumidor ver o `DeprecationWarning` na suíte dele antes do `ImportError`.

Uso:  python3 scripts/contrato_so_cresce.py [<commit-base>]
"""

import ast
import os
import re
import subprocess
import sys

FONTE = "src/okmigo_cartao/__init__.py"
DEPRECIACOES = "src/okmigo_cartao/depreciacao.py"


def rodar(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def nomes(texto: str) -> set[str] | None:
    """Os nomes de `__all__`, lidos pela ÁRVORE SINTÁTICA.

    ⛔ Nem `import` (a base é outro commit — importá-la significaria executá-la)
    nem regex (uma lista de 200 linhas com comentário no meio faz regex mentir
    calado). `ast` lê o que o Python leria, sem rodar nada."""
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return None
    for no in arvore.body:
        alvos = no.targets if isinstance(no, ast.Assign) else (
            [no.target] if isinstance(no, ast.AnnAssign) else [])
        for a in alvos:
            if isinstance(a, ast.Name) and a.id == "__all__":
                try:
                    return set(ast.literal_eval(no.value))
                except ValueError:
                    return None
    return None


def depreciacoes(texto: str | None) -> dict[str, str] | None:
    """`{nome: sai_em}` de `DEPRECIACOES`, lido pela árvore sintática (a base
    é outro commit: importá-la seria executá-la). Arquivo ausente = nenhuma
    depreciação; arquivo ilegível = `None`, que é recusa, nunca aprovação."""
    if texto is None:
        return {}
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return None
    for no in arvore.body:
        alvos = no.targets if isinstance(no, ast.Assign) else (
            [no.target] if isinstance(no, ast.AnnAssign) else [])
        if not any(isinstance(a, ast.Name) and a.id == "DEPRECIACOES" for a in alvos):
            continue
        if not isinstance(no.value, (ast.Tuple, ast.List)):
            return None
        saida = {}
        for item in no.value.elts:
            if not isinstance(item, ast.Call):
                return None
            campos = dict(zip(("nome", "desde", "sai_em", "alvo"), item.args, strict=False))
            campos.update({k.arg: k.value for k in item.keywords if k.arg})
            try:
                saida[ast.literal_eval(campos["nome"])] = ast.literal_eval(campos["sai_em"])
            except (KeyError, ValueError):
                return None
        return saida
    return {}


def como_tupla(v: str) -> tuple:
    return tuple(int(m.group()) if (m := re.match(r"^\d+", p)) else -1 for p in v.split("."))


def versao_de(texto: str) -> str | None:
    m = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.M)
    return m.group(1) if m else None


def slot_de_quebra(antes: str, agora: str) -> bool:
    """Em `0.x` o MENOR é o slot de quebra; de `1.0` em diante, o MAIOR."""
    def t(v):
        return [int(m.group()) if (m := re.match(r"^\d+", p)) else -1 for p in v.split(".")] + [0, 0]
    a, b = t(antes), t(agora)
    return (b[1] > a[1] or b[0] > a[0]) if a[0] == 0 else b[0] > a[0]


def base_padrao() -> str | None:
    alvo = os.environ.get("GITHUB_BASE_REF")
    if alvo:
        rodar("git", "fetch", "--no-tags", "--depth=50", "origin", alvo)
        r = rodar("git", "rev-parse", f"origin/{alvo}")
        if r.returncode == 0:
            return r.stdout.strip()
    r = rodar("git", "rev-parse", "HEAD~1")
    return r.stdout.strip() if r.returncode == 0 else None


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else base_padrao()
    if not base:
        print("✗ sem base de comparação — o passo não pode provar nada.", file=sys.stderr)
        return 1

    r = rodar("git", "show", f"{base}:{FONTE}")
    if r.returncode != 0:
        print(f"  · {FONTE} não existe na base — nada a comparar")
        return 0
    antes = nomes(r.stdout)
    with open(FONTE, encoding="utf-8") as f:
        agora = nomes(f.read())

    # ⛔ `None` é «não consegui ler», e não «está vazio». Aprovar aqui seria o
    # check se desligando sozinho no dia em que o arquivo mudar de forma.
    if antes is None or agora is None:
        qual = "na base" if antes is None else "na árvore"
        print(f"✗ não consegui ler o `__all__` {qual} de {FONTE}.", file=sys.stderr)
        return 1

    sumiram = sorted(antes - agora)
    nasceram = sorted(agora - antes)
    if nasceram:
        print(f"  · {len(nasceram)} nome(s) novo(s): {', '.join(nasceram)}")
    if not sumiram:
        print(f"  ✅ o contrato só cresceu ({len(agora)} nomes)")
        return 0

    vb = versao_de(rodar("git", "show", f"{base}:pyproject.toml").stdout) or "0.0.0"
    with open("pyproject.toml", encoding="utf-8") as f:
        va = versao_de(f.read()) or "0.0.0"

    r = rodar("git", "show", f"{base}:{DEPRECIACOES}")
    avisados = depreciacoes(r.stdout if r.returncode == 0 else None)
    if avisados is None:
        print(f"✗ não consegui ler `DEPRECIACOES` na base ({DEPRECIACOES}).", file=sys.stderr)
        return 1
    sem_aviso = [n for n in sumiram if n not in avisados]
    cedo = [n for n in sumiram if n in avisados and como_tupla(va) < como_tupla(avisados[n])]
    if sem_aviso or cedo:
        print(file=sys.stderr)
        print(f"✗ {len(sem_aviso) + len(cedo)} nome(s) saíram do `__all__` sem cumprir a janela:",
              file=sys.stderr)
        for n in sem_aviso:
            print(f"    · {n}: a base não o declarava depreciado", file=sys.stderr)
        for n in cedo:
            print(f"    · {n}: prometido para sair em {avisados[n]}, e a versão é {va}", file=sys.stderr)
        print("  Deprecie primeiro (src/okmigo_cartao/depreciacao.py), publique, e só", file=sys.stderr)
        print("  remova na versão `sai_em`. Um alias também serve.", file=sys.stderr)
        return 1

    if slot_de_quebra(vb, va):
        print(f"  ⚠️ {len(sumiram)} nome(s) saíram do contrato: {', '.join(sumiram)}")
        print(f"     declarado pela versão {vb} → {va}. Os consumidores que os usam")
        print("     vão quebrar no `import` ao receber o pino novo — avise-os.")
        return 0

    print(file=sys.stderr)
    print(f"✗ {len(sumiram)} nome(s) saíram do `__all__` sem a versão dizer:", file=sys.stderr)
    for n in sumiram:
        print(f"    · {n}", file=sys.stderr)
    print(f"  A versão foi {vb} → {va}, que não é o slot de quebra.", file=sys.stderr)
    print("  Dez repositórios importam daqui e param no `import`, não no teste.", file=sys.stderr)
    print(f"  Ou devolva o nome (um alias serve), ou suba o MENOR: {vb} → "
          f"{vb.split('.')[0]}.{int(vb.split('.')[1]) + 1}.0", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
