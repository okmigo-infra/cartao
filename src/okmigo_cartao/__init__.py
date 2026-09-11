"""okmigo-cartao — o crivo do cartão declarado.

    from okmigo_cartao import validar, Config

    tela, erro = validar(cartao, escrituras={"salvar"}, config=Config(dominios=("exemplo.com",)))

`tela` é o cartão RECONSTRUÍDO no vocabulário do produto (nunca o original
repassado) ou `None`; `erro` diz por que a tela inteira foi recusada. O que o
crivo não entende SOME em silêncio — e é para ver o que sumiu que existe o
`relatorio()` e a linha de comando (`python -m okmigo_cartao`).
"""
from .crivo import (
    Config, validar, MAX_NOS, ENFASES,
    TAMANHOS, PESOS, ESPACOS, ESTILOS, LARGURAS, ALINHAMENTOS, VISTAS,
    DADOS_DO_DIA, DADOS_DO_EVENTO, EVENTOS_PARA, ALTURAS_IMG, ALTURAS_CAIXA,
    FORMATOS_DE_ARQUIVO, FORMATOS_DE_DOCUMENTO,
)
from .casca import casca, expandir, relatorio

__all__ = [
    "Config", "validar", "casca", "expandir", "relatorio", "MAX_NOS", "ENFASES",
    "TAMANHOS", "PESOS", "ESPACOS", "ESTILOS", "LARGURAS", "ALINHAMENTOS", "VISTAS",
    "DADOS_DO_DIA", "DADOS_DO_EVENTO", "EVENTOS_PARA", "ALTURAS_IMG", "ALTURAS_CAIXA",
    "FORMATOS_DE_ARQUIVO", "FORMATOS_DE_DOCUMENTO",
]
