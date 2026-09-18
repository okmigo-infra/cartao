"""Se o conteúdo do manifesto mudou, a `versao` dele tem de ter mudado junto.

⛔ **Por que isto existe:** a tela do consumidor CONGELA na instalação, e quem a
atualiza é o registro olhando a `versao`. Mudar o desenho sem mexer no número
produz um manifesto novo que o okmigo trata como o MESMO — e a tela velha fica
no ar, sem erro em lugar nenhum.

⛔⛔ **Não confunda com `scripts/versao_subiu.py` deste repositório.** Aquele
confere se o CRIVO mudou sem a versão do PACOTE subir, e existe porque o SHA
pinado é imutável mas não tem nome. São duas checagens diferentes que, por sete
dias, compartilharam o nome do arquivo em oito repos — e eu supus que fossem a
mesma coisa até diffar as duas (OMINFRA-576).

Uso:
    okmigo-versao-do-manifesto <commit-base> <manifesto.json> [outro.json ...]
    python3 -m okmigo_cartao.esteira.versao_do_manifesto <commit-base> <alvos...>

⭐ Migrado de oito cópias byte a byte idênticas em 18/09. Foi o primeiro dos
três a vir justamente por isso: oito iguais não têm debate sobre qual é a
canônica.
"""

from __future__ import annotations

import json
import subprocess
import sys


def sem_versao(d: dict) -> dict:
    """Tudo menos a `versao`.

    ⛔ Comparar COM ela faria o passo se aprovar sozinho: trocar só o número
    contaria como «o conteúdo mudou», e a condição que se quer provar é
    exatamente a outra.
    """
    return {k: v for k, v in d.items() if k != "versao"}


def conferir(base: str, alvos: list[str]) -> tuple[list, list, list]:
    """`(falhas, iguais, novos)` — a decisão, sem imprimir nada.

    ⭐ Separado do `main` de propósito: é o que permite testar a REGRA sem
    capturar saída nem inspecionar código de saída. As oito cópias de origem
    não tinham teste nenhum, e a razão era esta — tudo vivia dentro do `main`.
    """
    falhas: list[tuple[str, object]] = []
    iguais: list[str] = []
    novos: list[str] = []

    for alvo in alvos:
        # ⚠️ `check=False` explícito: a AUSÊNCIA do arquivo na base é caso normal
        # (manifesto novo), não erro — quem decide é o `returncode` abaixo.
        r = subprocess.run(
            ["git", "show", f"{base}:{alvo}"],
            capture_output=True, text=True, check=False,
        )
        if r.returncode != 0:
            novos.append(alvo)
            continue
        antes = json.loads(r.stdout)
        with open(alvo, encoding="utf-8") as f:
            agora = json.load(f)
        if sem_versao(antes) == sem_versao(agora):
            iguais.append(alvo)
        elif antes.get("versao") == agora.get("versao"):
            falhas.append((alvo, agora.get("versao")))

    return falhas, iguais, novos


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print("uso: okmigo-versao-do-manifesto <commit-base> <manifesto.json> ...",
              file=sys.stderr)
        return 2
    base, alvos = args[0], args[1:]
    falhas, iguais, novos = conferir(base, alvos)

    for alvo in novos:
        print(f"  · {alvo}: novo, sem base de comparação")
    for alvo in iguais:
        print(f"  · {alvo}: conteúdo inalterado")

    if falhas:
        print(file=sys.stderr)
        for alvo, versao in falhas:
            print(f"✗ {alvo}: o conteúdo mudou e a `versao` continua {versao}.",
                  file=sys.stderr)
        print("  A tela do consumidor congela na instalação: sem número novo, o",
              file=sys.stderr)
        print("  registro não tem como saber que há o que reaprovar.", file=sys.stderr)
        return 1

    print("  ✅ toda mudança de manifesto veio com versão nova")
    return 0


if __name__ == "__main__":
    sys.exit(main())
