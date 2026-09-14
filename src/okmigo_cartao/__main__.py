"""Linha de comando: dá um cartão (e, se for molde, os dados), mostra o que o
crivo deixa passar, o que ele comeu, e como a tela fica pelada.

    python -m okmigo_cartao cartao.json
    python -m okmigo_cartao molde.json --dados dados.json --escrituras salvar,apagar
    python -m okmigo_cartao cartao.json --html saida.html --dominio exemplo.com
    python -m okmigo_cartao okmigo/manifesto.json --superficie extrato --dados dados.json

Com o MANIFESTO inteiro, `--superficie` escolhe o cartão e as `operacoes`
declaradas viram as escrituras/leituras que o crivo confere — que é o teste
que interessa: um botão que nomeia operação fora do contrato recusa a tela.

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
from .manifesto import e_manifesto, escolher, operacoes, superficies


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if argumentos and argumentos[0] == "preview":
        from .preview import main_preview

        return main_preview(argumentos[1:])

    p = argparse.ArgumentParser(prog="okmigo-cartao", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cartao", type=Path, help="um cartão, um molde, ou o MANIFESTO inteiro (JSON)")
    p.add_argument("--superficie", help="com um manifesto: qual superfície validar (as operações dele viram escrituras/leituras)")
    p.add_argument("--dados", type=Path, help="JSON com {resumo, linhas} ou uma lista, para expandir o molde")
    p.add_argument("--escrituras", default=None, help="operações de escrita declaradas, separadas por vírgula")
    p.add_argument("--leituras", default=None, help="operações de leitura declaradas, separadas por vírgula")
    p.add_argument("--dominio", action="append", default=[], help="um domínio do produto (repetível); imagens só passam se forem dele")
    p.add_argument("--base-de-imagens", default="", help="prefixo que torna /img/... absoluto")
    p.add_argument("--html", type=Path, help="escreve a casca (HTML sem CSS) neste arquivo")
    p.add_argument("--json", action="store_true", help="imprime o cartão reconstruído em JSON")
    p.add_argument("--quieto", action="store_true", help="só o veredito e os avisos")
    a = p.parse_args(argumentos)

    bruto = json.loads(a.cartao.read_text(encoding="utf-8"))
    esc_do_manifesto = lei_do_manifesto = None
    if e_manifesto(bruto):
        # Um MANIFESTO: escolhe a superfície e tira o contrato das operações.
        if not a.superficie:
            print("é um manifesto — diga qual superfície com --superficie. Há: "
                  + ", ".join(superficies(bruto)))
            return 2
        try:
            cartao_da = escolher(bruto, a.superficie)
        except KeyError as e:
            print(f"✗ {e.args[0]}")
            return 2
        esc_do_manifesto, lei_do_manifesto = operacoes(bruto)
        cabecalho = f"manifesto {bruto.get('slug', '?')} {bruto.get('versao', '')} · superfície «{a.superficie}»"
        if not esc_do_manifesto and not lei_do_manifesto:
            # Manifesto sem `operacoes`: o contrato vem da sondagem do serviço,
            # que não está aqui. Não conferir é honesto; recusar tudo, não.
            esc_do_manifesto = lei_do_manifesto = None
            if a.escrituras is None and a.leituras is None:
                print(cabecalho + " · ⚠️ sem `operacoes` no manifesto e sem --escrituras/--leituras: "
                      "botões NÃO conferidos — passe o que o seu servidor MCP expõe")
            else:
                print(cabecalho + " · contrato vindo das bandeiras")
        else:
            print(cabecalho + f" · {len(esc_do_manifesto)} escrita(s), {len(lei_do_manifesto)} leitura(s) declaradas")
        bruto = cartao_da
    if a.dados:
        d = json.loads(a.dados.read_text(encoding="utf-8"))
        if isinstance(d, list):
            resumo, linhas = {}, d
        else:
            resumo, linhas = (d.get("resumo") or {}), (d.get("linhas") or [])
        bruto = expandir(bruto, resumo, linhas)

    # As bandeiras vencem o manifesto; sem nenhuma das duas fontes, não confere.
    esc = frozenset(x.strip() for x in a.escrituras.split(",") if x.strip()) if a.escrituras is not None else esc_do_manifesto
    lei = frozenset(x.strip() for x in a.leituras.split(",") if x.strip()) if a.leituras is not None else lei_do_manifesto
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
