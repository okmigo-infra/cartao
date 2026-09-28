"""Como um nome SAI do contrato público: com aviso, janela e mensagem.

⛔ Quem consome este pacote está pinado num SHA antigo e só recebe a versão
nova quando alguém troca o pino. Se um nome sumisse de uma versão para a
outra, o aplicativo quebraria no `import`, sem nenhum aviso antes. Então um
nome não sai de uma vez; ele passa por três estados:

1. **Depreciado.** Continua no `__all__` e continua funcionando, mas quem o
   usa recebe um `DeprecationWarning` com a versão em que o aviso começou, a
   primeira versão que pode removê-lo e o que usar no lugar. É o que o
   consumidor lê na suíte dele, com o `-W error::DeprecationWarning` que o
   pytest já mostra, ANTES de a remoção existir.
2. **Janela.** A remoção só pode vir `JANELA_MINIMA` versões MENORES depois do
   aviso (em `0.x`, onde o menor é o slot de quebra; de `1.0` em diante, na
   versão MAIOR seguinte). `scripts/contrato_so_cresce.py` recusa a remoção
   que não cumprir a janela.
3. **Removido.** Sai do `__all__` e desta lista no mesmo commit, com a versão
   no slot de quebra.

Para depreciar um nome: tire-o do módulo `okmigo_cartao` (deixe o objeto num
submódulo), mantenha-o no `__all__`, e acrescente aqui um `Depreciacao` com
`alvo` apontando para o objeto — o `__getattr__` do pacote o entrega com o
aviso. As regras desta lista são conferidas por `tests/test_depreciacao.py`.
"""

from __future__ import annotations

import importlib
import re
import warnings
from dataclasses import dataclass
from typing import Any

#: Versões MENORES entre o primeiro aviso e a remoção. Com a cadência de hoje
#: (uma versão menor a cada poucos dias), duas dão ao consumidor pelo menos
#: uma PR de pino com o aviso visível antes da PR que quebraria.
JANELA_MINIMA = 2


def _tupla(v: str) -> tuple[int, int, int]:
    p = [int(m.group()) if (m := re.match(r"^\d+", x)) else -1 for x in v.split(".")]
    return tuple((p + [0, 0, 0])[:3])  # type: ignore[return-value]


@dataclass(frozen=True)
class Depreciacao:
    """Um nome público a caminho de sair.

    - `nome`: o nome no `__all__`;
    - `desde`: a primeira versão que avisa;
    - `sai_em`: a primeira versão que PODE removê-lo;
    - `alvo`: `"modulo:atributo"` do objeto que o nome ainda entrega;
    - `use`: o que usar no lugar (vazio se não há substituto);
    - `motivo`: uma frase, para o consumidor decidir sem abrir o código.
    """

    nome: str
    desde: str
    sai_em: str
    alvo: str
    use: str = ""
    motivo: str = ""

    def mensagem(self) -> str:
        texto = (f"okmigo_cartao.{self.nome} está depreciado desde {self.desde} "
                 f"e pode sair a partir de {self.sai_em}")
        if self.use:
            texto += f"; use {self.use}"
        return texto + (f". {self.motivo}" if self.motivo else ".")

    def resolver(self) -> Any:
        modulo, _, atributo = self.alvo.partition(":")
        return getattr(importlib.import_module(modulo), atributo)


def problema_da_janela(d: Depreciacao) -> str | None:
    """`None` se a janela é válida; senão, o que está errado."""
    a, b = _tupla(d.desde), _tupla(d.sai_em)
    if min(a + b) < 0:
        return f"{d.nome}: versão ilegível ({d.desde} → {d.sai_em})"
    if a[0] == 0 and b[0] == 0:
        if b[1] - a[1] < JANELA_MINIMA:
            return (f"{d.nome}: a janela {d.desde} → {d.sai_em} tem menos de "
                    f"{JANELA_MINIMA} versões menores")
        return None
    if b[0] <= a[0]:
        return f"{d.nome}: de 1.0 em diante só se remove na versão MAIOR seguinte"
    return None


#: A lista de hoje. Vazia: nenhum nome público está a caminho de sair.
DEPRECIACOES: tuple[Depreciacao, ...] = ()


def por_nome(nome: str) -> Depreciacao | None:
    for d in DEPRECIACOES:
        if d.nome == nome:
            return d
    return None


def entregar(nome: str) -> Any:
    """O objeto de um nome depreciado, com o aviso. `AttributeError` se o nome
    não está nesta lista — é o que o `__getattr__` do pacote precisa."""
    d = por_nome(nome)
    if d is None:
        raise AttributeError(f"module 'okmigo_cartao' has no attribute {nome!r}")
    # stacklevel=3: o aviso aponta a linha do CONSUMIDOR, não este arquivo
    # nem o `__getattr__` do pacote.
    warnings.warn(d.mensagem(), DeprecationWarning, stacklevel=3)
    return d.resolver()
