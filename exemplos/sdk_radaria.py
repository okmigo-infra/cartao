"""Tela piloto do RadarIA escrita sem JSON manual.

Execute com: PYTHONPATH=src python exemplos/sdk_radaria.py
"""

from __future__ import annotations

import json

from okmigo_cartao.sdk import (
    Acao,
    Acoes,
    Busca,
    CampoOculto,
    Coluna,
    EnfaseDaAcao,
    Navegacao,
    Opcao,
    Painel,
    PapelDoTexto,
    Tabela,
    Tela,
    Tema,
    Texto,
)


def tela_de_ativos() -> Tela:
    return Tela(
        titulo="Meus ativos",
        descricao="Busque qualquer ativo e escolha o que quer acompanhar.",
        tema=Tema.MERCADO,
        navegacao=Navegacao.INFERIOR,
        componentes=(
            Painel(
                itens=(
                    Busca(
                        id="ticker_busca",
                        campo="ticker",
                        rotulo="Ativo da B3",
                        placeholder="Digite SANB11, PETR4, VALE3...",
                        sugestoes_por="buscar_ativos",
                        sugestoes_iniciais=(
                            Opcao("PETR4 · Petrobras", "PETR4"),
                            Opcao("SANB11 · Santander Brasil", "SANB11"),
                            Opcao("VALE3 · Vale", "VALE3"),
                        ),
                    ),
                    Acoes(
                        (
                            Acao.consultar(
                                "Analisar ativo",
                                "detalhar_ativo",
                                enfase=EnfaseDaAcao.PRIMARIA,
                            ),
                            Acao.escrever("Acompanhar", "adicionar_acompanhado"),
                        )
                    ),
                )
            ),
            Texto("Acompanhados", PapelDoTexto.SECAO),
            Texto("{atualizado_frase}", PapelDoTexto.AUXILIAR),
            Tabela(
                colunas=(
                    Coluna(
                        "Ativo",
                        (
                            Texto("{ticker}", negrito=True),
                            Texto("{empresa}", PapelDoTexto.AUXILIAR),
                        ),
                        largura=3,
                    ),
                    Coluna("Preço", (Texto("{preco}"),), largura=2),
                    Coluna("Dia", (Texto("{variacao}"),), largura=2),
                    Coluna("Volume", (Texto("{volume}"),), largura=2),
                ),
                ao_tocar=Acao.consultar("Ver detalhes", "detalhar_ativo"),
                campos_da_linha=(
                    CampoOculto("remover_{ticker}", "ticker", "{ticker}"),
                ),
                acoes_da_linha=(
                    Acao.escrever(
                        "Remover",
                        "remover_acompanhado",
                        enfase=EnfaseDaAcao.DESTRUTIVA,
                        icone="lixeira",
                    ),
                ),
                vazio="Nenhum ativo acompanhado ainda.",
            ),
            Texto(
                "Cotações de referência, não recomendação de investimento.",
                PapelDoTexto.AUXILIAR,
            ),
        ),
    )


if __name__ == "__main__":
    tela = tela_de_ativos()
    bruto = tela.compilar()
    tela.conferir(
        leituras={"buscar_ativos", "detalhar_ativo"},
        escrituras={"adicionar_acompanhado", "remover_acompanhado"},
    )
    print(json.dumps(bruto, ensure_ascii=False, indent=2))
