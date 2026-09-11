"""Linha de comando: dá um cartão (e, se for molde, os dados), mostra o que o
crivo deixa passar, o que ele comeu, e como a tela fica pelada.

    python -m okmigo_cartao cartao.json
    python -m okmigo_cartao molde.json --dados dados.json --escrituras salvar,apagar
    python -m okmigo_cartao cartao.json --html saida.html --dominio exemplo.com

`--dados` é um JSON `{"resumo": {...}, "linhas": [...]}` — o objeto de topo
da superfície e a lista dela — ou só uma lista. Sem `--dados`, o cartão é
validado como está (e um molde com `_repetir_lista` perde as linhas, que é
exatamente o que acontece quando se valida o molde cru).

Sai com código 1 se a tela foi RECUSADA; 0 se passou — mesmo com avisos. Os
avisos são o motivo de esta ferramenta existir: leia-os.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .casca import casca, expandir, relatorio
from .crivo import Config, validar


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="okmigo-cartao", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cartao", type=Path, help="o cartão ou molde (JSON)")
    p.add_argument("--dados", type=Path, help="JSON com {resumo, linhas} ou uma lista, para expandir o molde")
    p.add_argument("--escrituras", default=None, help="operações de escrita declaradas, separadas por vírgula")
    p.add_argument("--leituras", default=None, help="operações de leitura declaradas, separadas por vírgula")
    p.add_argument("--dominio", action="append", default=[], help="um domínio do produto (repetível); imagens só passam se forem dele")
    p.add_argument("--base-de-imagens", default="", help="prefixo que torna /img/... absoluto")
    p.add_argument("--html", type=Path, help="escreve a casca (HTML sem CSS) neste arquivo")
    p.add_argument("--json", action="store_true", help="imprime o cartão reconstruído em JSON")
    p.add_argument("--quieto", action="store_true", help="só o veredito e os avisos")
    a = p.parse_args(argv)

    bruto = json.loads(a.cartao.read_text(encoding="utf-8"))
    if a.dados:
        d = json.loads(a.dados.read_text(encoding="utf-8"))
        if isinstance(d, list):
            resumo, linhas = {}, d
        else:
            resumo, linhas = (d.get("resumo") or {}), (d.get("linhas") or [])
        bruto = expandir(bruto, resumo, linhas)

    esc = frozenset(x.strip() for x in a.escrituras.split(",") if x.strip()) if a.escrituras is not None else None
    lei = frozenset(x.strip() for x in a.leituras.split(",") if x.strip()) if a.leituras is not None else None
    cfg = Config(dominios=tuple(a.dominio), base_de_imagens=a.base_de_imagens)

    tela, erro = validar(bruto, esc, lei, config=cfg)
    avisos = relatorio(bruto, tela, erro)

    if erro:
        print(f"✗ RECUSADO — {erro}")
    else:
        n = _contar(tela["corpo"])
        print(f"✓ passou — {n} nó(s) na tela reconstruída"
              + (f" · tema {tela['tema']}" if tela.get("tema") else "")
              + (f" · navegação {tela['navegacao']}" if tela.get("navegacao") else ""))
    for linha in avisos:
        print("  " + linha)
    if not avisos and not erro:
        print("  (nada foi comido: tudo o que entrou tem correspondente na saída)")

    if tela and a.json and not a.quieto:
        print(json.dumps(tela, ensure_ascii=False, indent=2))
    if tela and a.html:
        a.html.write_text(casca(tela, a.cartao.stem), encoding="utf-8")
        print(f"  casca escrita em {a.html}")
    return 1 if erro else 0


def _contar(corpo) -> int:
    n = 0
    for x in corpo or []:
        n += 1
        n += _contar(x.get("itens"))
        for c in x.get("colunas") or []:
            n += _contar(c.get("itens"))
        if x.get("tipo") == "tabela":  # num `campo`, `linhas` é o número de linhas de texto
            for l in x.get("linhas") or []:
                for c in l.get("celulas") or []:
                    n += _contar(c.get("itens"))
    return n


if __name__ == "__main__":
    sys.exit(main())
