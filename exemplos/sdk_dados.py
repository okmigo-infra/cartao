"""Aplicativo pequeno cujas telas são MOLDES — só existem com dados.

O `sdk_catalogo.py` mostra os componentes; este mostra o que acontece
quando a tela depende da lista que o serviço devolve: tabela que repete por
linha, sublista (`de=`), filtro (`quando=`), texto e imagem vindos do dado,
e uma rota interna com parâmetro. É o exemplo que a suíte usa para provar os
extremos (lista vazia, 250 linhas, textos de 1.200 caracteres):

    python -m okmigo_cartao preview exemplos/sdk_dados.py:APLICATIVO \\
        --dados exemplos/sdk_dados.dados.json
"""

from okmigo_cartao import (
    Acao,
    Acoes,
    Aplicativo,
    Coluna,
    Condicao,
    Fonte,
    Imagem,
    Painel,
    ParametroDaRota,
    PapelDoTexto,
    Repetir,
    Rota,
    Superficie,
    Tabela,
    Tela,
    Tema,
    Texto,
)

LISTA = Tela(
    "Tarefas",
    (
        Texto("{resumo_do_dia}", PapelDoTexto.AUXILIAR),
        Tabela(
            (
                Coluna("Tarefa", (Texto("{nome}"),), 3),
                Coluna("Prazo", (Texto("{prazo}", PapelDoTexto.AUXILIAR),), 1),
            ),
            ao_tocar=Acao.consultar("Ver", "ver_tarefa", dados={"id": "{id}"}),
            vazio="Nenhuma tarefa por aqui.",
        ),
        Texto("Em atraso", PapelDoTexto.SECAO),
        Repetir(
            Painel((
                Texto("{nome}", negrito=True),
                Texto("{motivo}", PapelDoTexto.AUXILIAR),
                Acoes((Acao.navegar("Abrir", "tarefa", parametros={"id": "{id}"}),)),
            )),
            quando=Condicao("estado", ("atrasada",)),
        ),
        Texto("Etiquetas", PapelDoTexto.SECAO),
        Repetir(Texto("{rotulo} · {quantas}", PapelDoTexto.AUXILIAR), de="etiquetas"),
    ),
    tema=Tema.OPERACAO,
)

DETALHE = Tela(
    "Tarefa",
    (
        Texto("{nome}", PapelDoTexto.TITULO),
        Imagem("{foto}", "{foto_descricao}"),
        Texto("{descricao}"),
        Repetir(Texto("{quando} — {texto}", PapelDoTexto.AUXILIAR), de="historico"),
    ),
    tema=Tema.OPERACAO,
)

APLICATIVO = Aplicativo(
    slug="tarefas-exemplo",
    endpoint="https://example.invalid/mcp/",
    para_tipo="amigo",
    descricao="Lista de tarefas de exemplo",
    descricao_humana="Exemplo de telas dirigidas por dados",
    nome_visivel="Tarefas",
    versao="1.0.0",
    conversa=(),
    superficies=(
        Superficie("lista", "Tarefas", "Tarefas", "inicio", "as tarefas do dia",
                   Fonte("listar_tarefas", "tarefas"), LISTA),
        Superficie("detalhe", "Tarefa", "Tarefa", "perfil", "uma tarefa",
                   Fonte("ver_tarefa"), DETALHE),
    ),
    rotas=(Rota("tarefa", "detalhe", (ParametroDaRota("id"),)),),
)
