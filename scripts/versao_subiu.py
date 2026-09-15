"""Se o crivo mudou, a `version` do pacote tem de ter SUBIDO junto.

⛔⛔ Por que isto existe: os dez repositórios que consomem o cartão o pinam por
SHA num tarball do git —

    okmigo-cartao @ https://github.com/okmigo-infra/cartao/archive/<sha>.tar.gz

O SHA é imutável (é essa a virtude dele, e é por isso que NÃO se pina a `main`
nem uma tag, que se movem), mas ele não tem NOME. A única coisa que diz o que
está instalado num pod é a versão que o pacote declara, lida de dentro com
`importlib.metadata.version("okmigo-cartao")`. Publicar duas árvores diferentes
com o mesmo número faz esse gesto mentir, e não sobra nenhuma outra fonte.

⚠️ Medido em 15/09: o `pyproject.toml` dizia `0.6.0` e a tag mais nova do repo
era `v0.4.0`. Duas entregas tinham ido ao ar sem nome nenhum — e, no mesmo dia,
uma terceira mudança de 578 linhas estava pronta ainda em `0.6.0`.

⛔ O passo compara o conteúdo de `src/`, não o commit: mexer só em `README.md`,
em `docs/` ou nesta própria pasta `scripts/` NÃO exige versão nova. O que
precisa de número é o que chega no consumidor.

Uso:  python3 scripts/versao_subiu.py [<commit-base>]
"""

import os
import re
import subprocess
import sys


def rodar(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def versao_de(texto: str) -> str | None:
    m = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.M)
    return m.group(1) if m else None


def como_tupla(v: str) -> tuple:
    """`0.6.0` → `(0, 6, 0)`. Pedaço não numérico vira -1, que perde de tudo —
    assim um `0.7.0rc1` não se faz passar por maior que `0.7.0` por acidente."""
    pedacos = []
    for p in v.split("."):
        n = re.match(r"^\d+", p)
        pedacos.append(int(n.group()) if n else -1)
    return tuple(pedacos)


def base_padrao() -> str | None:
    """A base de comparação. ⛔ Num `push` para a `main` o `origin/main` JÁ é
    este commit — comparar com ele mesmo daria «nada mudou» sempre, que é a
    forma mais silenciosa de um check se aprovar sozinho."""
    alvo = os.environ.get("GITHUB_BASE_REF")          # pull_request
    if alvo:
        rodar("git", "fetch", "--no-tags", "--depth=50", "origin", alvo)
        r = rodar("git", "rev-parse", f"origin/{alvo}")
        if r.returncode == 0:
            return r.stdout.strip()
    r = rodar("git", "rev-parse", "HEAD~1")           # push na main
    return r.stdout.strip() if r.returncode == 0 else None


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else base_padrao()
    if not base:
        print("✗ sem base de comparação — o passo não pode provar nada.", file=sys.stderr)
        print("  (checkout raso? este passo precisa de `fetch-depth: 0`)", file=sys.stderr)
        return 1
    print(f"  base: {base}")

    r = rodar("git", "show", f"{base}:pyproject.toml")
    antes = versao_de(r.stdout) if r.returncode == 0 else None
    with open("pyproject.toml", encoding="utf-8") as f:
        agora = versao_de(f.read())

    if agora is None:
        print("✗ não achei `version = \"…\"` no pyproject.toml.", file=sys.stderr)
        return 1
    if antes is None:
        print(f"  · sem `version` na base; agora {agora}")
        return 0

    # ⛔⛔ Regra 1, e ela NÃO depende de `src/`: o número não anda para trás.
    # Achado montando a prova deste próprio script: um commit que mexe só no
    # `pyproject.toml` cai fora do «mudou o crivo», e por aí `0.7.0 → 0.6.5`
    # passava calado. Um número que regride é pior que um número parado —
    # parado só não informa; regredido faz o consumidor concluir o contrário
    # («estou à frente») olhando a fonte certa.
    if como_tupla(agora) < como_tupla(antes):
        print(f"✗ a versão andou PARA TRÁS: {antes} → {agora}.", file=sys.stderr)
        print("  Quem lê `importlib.metadata.version(\"okmigo-cartao\")` num pod", file=sys.stderr)
        print("  vai concluir que está à frente do que está.", file=sys.stderr)
        return 1

    # Regra 2: mexeu no que chega no consumidor? Então o número sobe.
    # ⛔ `README.md`, `docs/` e `scripts/` NÃO exigem versão nova — o que
    # precisa de nome é o que vai dentro do tarball que o pip instala.
    mudados = rodar("git", "diff", "--name-only", base, "HEAD", "--", "src/").stdout.split()
    if not mudados:
        print(f"  · `src/` inalterado — versão nova não é exigida (segue {agora})")
        return 0
    if como_tupla(agora) > como_tupla(antes):
        print(f"  ✅ `src/` mudou ({len(mudados)} arquivos) e a versão subiu {antes} → {agora}")
        return 0

    print(file=sys.stderr)
    print(f"✗ o crivo mudou e a versão continua {agora}" +
          (f" (a base já era {antes})" if antes != agora else "") + ".", file=sys.stderr)
    for m in mudados:
        print(f"    · {m}", file=sys.stderr)
    print("  Os consumidores pinam por SHA, que não tem nome: sem número novo,", file=sys.stderr)
    print("  duas árvores diferentes se apresentam igual e nem o pod distingue.", file=sys.stderr)
    print("  Suba o `version` no pyproject.toml e marque a tag junto.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
