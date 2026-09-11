"""O manifesto de um serviço: várias superfícies, cada uma com um cartão, e as
operações declaradas — que são exatamente as `escrituras` e `leituras` que o
crivo confere. Ler daqui evita o erro mais fácil de cometer ao testar: validar
o cartão sem o contrato, e ver passar um botão que o produto vai recusar.
"""

from __future__ import annotations

from typing import Any


def e_manifesto(bruto: Any) -> bool:
    return isinstance(bruto, dict) and isinstance(bruto.get("superficies"), list)


def superficies(manifesto: dict) -> list[str]:
    return [str(s.get("nome") or "?") for s in manifesto.get("superficies") or [] if isinstance(s, dict)]


def operacoes(manifesto: dict) -> tuple[frozenset[str], frozenset[str]]:
    """`(escrituras, leituras)` a partir de `operacoes[{nome, efeitos}]`.
    `efeitos == "escrita"` é escrita; tudo o mais é leitura — é a mesma
    divisão que o produto faz ao congelar o contrato na instalação."""
    esc, lei = set(), set()
    for o in manifesto.get("operacoes") or []:
        if not isinstance(o, dict) or not o.get("nome"):
            continue
        (esc if o.get("efeitos") == "escrita" else lei).add(str(o["nome"]))
    return frozenset(esc), frozenset(lei)


def escolher(manifesto: dict, nome: str) -> dict:
    """O cartão da superfície `nome`. Levanta `KeyError` com a lista, para a
    mensagem de erro já dizer o que existe."""
    for s in manifesto.get("superficies") or []:
        if isinstance(s, dict) and s.get("nome") == nome:
            c = s.get("cartao")
            if not isinstance(c, dict):
                raise KeyError(f"a superfície '{nome}' não tem `cartao`")
            return c
    raise KeyError(f"superfície '{nome}' não existe; há: {', '.join(superficies(manifesto)) or 'nenhuma'}")
