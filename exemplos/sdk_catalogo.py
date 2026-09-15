"""Aplicativo pequeno que exercita o catálogo tipado do SDK.

Abra com:
    python -m okmigo_cartao preview exemplos/sdk_catalogo.py:APLICATIVO
"""

from okmigo_cartao import (
    Acao,
    Aba,
    Abas,
    Acoes,
    AlvoDeVisibilidade,
    AoTocarODia,
    Alternancia,
    Aplicativo,
    Arquivo,
    Calendario,
    BarraDeValor,
    CampoComUnidade,
    CampoData,
    CampoMoeda,
    CampoTelefone,
    CartaoClicavel,
    CelulaDeTabela,
    Confirmacao,
    CampoNumero,
    CampoTexto,
    CartaoFinanceiro,
    CartoesFinanceiros,
    Copiar,
    Distribuicao,
    Documento,
    Dialogo,
    EnfaseDaAcao,
    EnviarEAvancar,
    Escolha,
    EscolhaMultipla,
    EstadoVazio,
    Evento,
    EtapaDaLinhaDoTempo,
    Etiqueta,
    Expansivel,
    Fonte,
    FormatoDeArquivo,
    FormaDaEscolha,
    Formulario,
    GradeDeMetricas,
    GaleriaDeImagens,
    Imagem,
    ItemDeDistribuicao,
    LancamentoFinanceiro,
    ListaFinanceira,
    LinhaDeTabela,
    LinhaDoTempo,
    Metrica,
    MenuDeAcoes,
    Navegacao,
    Opcao,
    Progresso,
    SeletorDeQuantidade,
    Secao,
    SemanticaFinanceira,
    Superficie,
    Status,
    TabelaFlexivel,
    Tela,
    Tema,
    Texto,
    TipoDeEvento,
    TomFinanceiro,
    TomDaEtiqueta,
    VistaDoCalendario,
)


INICIO = Tela(
    "Visão geral",
    (
        GradeDeMetricas(
            (
                Metrica("Em andamento", "8", "2 precisam de atenção"),
                Metrica("Concluídos hoje", "14", "↗ 3 desde ontem"),
                Metrica("Tempo médio", "18 min"),
            )
        ),
        Progresso(3, 5, "Configuração da conta"),
        Copiar("Copiar código de convite", "DEMO-2026"),
        EstadoVazio(
            "Nenhum alerta agora",
            "Quando algo precisar da sua decisão, aparecerá aqui.",
        ),
    ),
    tema=Tema.OPERACAO,
    navegacao=Navegacao.INFERIOR,
)


FORMULARIO = Tela(
    "Novo cadastro",
    (
        Formulario(
            "Dados principais",
            campos=(
                CampoTexto(
                    "nome_cadastro",
                    "nome",
                    "Nome",
                    placeholder="Como a pessoa prefere ser chamada",
                    obrigatorio=True,
                ),
                CampoNumero(
                    "valor_cadastro",
                    "valor",
                    "Valor",
                    minimo=0,
                ),
                Escolha(
                    "prioridade_cadastro",
                    "prioridade",
                    "Prioridade",
                    (
                        Opcao("Normal", "normal", "Segue a fila", "○"),
                        Opcao("Alta", "alta", "Precisa de atenção", "!"),
                    ),
                    FormaDaEscolha.CARTOES,
                    obrigatoria=True,
                ),
                Arquivo(
                    "anexo_cadastro",
                    "anexo",
                    "Anexo opcional",
                    (FormatoDeArquivo.PDF, FormatoDeArquivo.IMAGEM),
                ),
            ),
            acoes=(
                Acao.escrever(
                    "Salvar cadastro",
                    "salvar_cadastro",
                    enfase=EnfaseDaAcao.PRIMARIA,
                ),
            ),
            explicacao="Revise os dados antes de salvar.",
            rodape=True,
        ),
    ),
    tema=Tema.JORNADA,
    navegacao=Navegacao.INFERIOR,
)


AGENDA = Tela(
    "Agenda",
    (
        Calendario(
            (
                Evento(
                    "2026-09-14T10:00:00-03:00",
                    "Reunião de acompanhamento",
                    "2026-09-14T10:45:00-03:00",
                    "Sala 2",
                    "evento-1",
                    TipoDeEvento.COMPROMISSO,
                ),
                Evento(
                    "2026-09-15T14:00:00-03:00",
                    "Atendimento",
                    detalhe="Primeira visita",
                    id="evento-2",
                    tipo=TipoDeEvento.ATENDIMENTO,
                ),
            ),
            VistaDoCalendario.SEMANA,
            ao_tocar_o_dia=AoTocarODia("novo_evento", "data"),
        ),
        Secao(
            (
                Formulario(
                    "Novo evento",
                    campos=(
                        CampoTexto("data_evento", "data", "Data", somente_leitura=True),
                        CampoTexto("titulo_evento", "titulo", "Título", obrigatorio=True),
                    ),
                    acoes=(
                        EnviarEAvancar(
                            "Criar evento",
                            "criar_evento",
                            (AlvoDeVisibilidade("novo_evento", False),),
                        ),
                    ),
                ),
            ),
            id="novo_evento",
            visivel=False,
            sobreposta=True,
        ),
    ),
    tema=Tema.JORNADA,
    navegacao=Navegacao.INFERIOR,
)


LANCAMENTO = LancamentoFinanceiro(
    "Mercado Vila Nova",
    "−R$ 286,40",
    "Alimentação · conta principal",
    "🛒",
    SemanticaFinanceira.NEGATIVO,
    grupo="14 SET, 2026",
    tipo="saidas",
)

FINANCEIRO = Tela(
    "Finanças",
    (
        CartoesFinanceiros(
            (
                CartaoFinanceiro(
                    "Cartão principal",
                    numero="•••• 4821",
                    tom=TomFinanceiro.VIOLETA,
                    fatura_rotulo="Fatura atual",
                    fatura="R$ 3.240,18",
                    limite_rotulo="Limite disponível",
                    limite="R$ 4.459,82",
                    progresso_texto="42% do limite usado",
                    progresso_feito=42,
                    lancamentos=(LANCAMENTO,),
                ),
            )
        ),
        Distribuicao(
            "Gastos por categoria",
            (
                ItemDeDistribuicao(
                    "Alimentação",
                    38,
                    "38%",
                    TomFinanceiro.LARANJA,
                ),
                ItemDeDistribuicao("Transporte", 22, "22%", TomFinanceiro.AZUL),
            ),
        ),
        ListaFinanceira(
            "Últimas transações",
            (LANCAMENTO,),
            busca=True,
            filtros=("todas", "entradas", "saidas"),
        ),
        Documento(
            "Extrato de setembro",
            "extrato-setembro.pdf",
            "application/pdf",
            "baixar_extrato",
            {"conta_id": "principal", "mes": 9},
            128 * 1024,
        ),
    ),
    tema=Tema.FINANCEIRO,
    navegacao=Navegacao.INFERIOR,
)


UNIVERSAIS = Tela(
    "Componentes universais",
    (
        Abas(
            (
                Aba(
                    "resumo",
                    "Resumo",
                    (
                        Etiqueta("Novo", TomDaEtiqueta.INFORMATIVO),
                        Status("Operação normal", TomDaEtiqueta.POSITIVO),
                        BarraDeValor("Limite usado", 42, 100, "42%"),
                    ),
                ),
                Aba(
                    "andamento",
                    "Andamento",
                    (
                        LinhaDoTempo(
                            (
                                EtapaDaLinhaDoTempo("Pedido recebido", "09:12"),
                                EtapaDaLinhaDoTempo("Em preparação", "agora"),
                                EtapaDaLinhaDoTempo("Entrega"),
                            )
                        ),
                    ),
                ),
            )
        ),
        CartaoClicavel(
            (Texto("PETR4 · Petrobras", negrito=True), Texto("R$ 35,20")),
            Acao.consultar("Abrir detalhes de PETR4", "detalhar_item"),
            menu=MenuDeAcoes(
                (
                    Acao.escrever(
                        "Remover dos favoritos",
                        "remover_item",
                        enfase=EnfaseDaAcao.DESTRUTIVA,
                        confirmacao=Confirmacao(
                            "Remover favorito?",
                            "Você poderá adicioná-lo novamente depois.",
                            "Remover",
                        ),
                    ),
                )
            ),
        ),
        Expansivel(
            "campos_avancados",
            "Testar campos avançados",
            (
                CampoData("data_demo", "data", "Data"),
                CampoMoeda("valor_demo", "valor", "Valor"),
                CampoTelefone("telefone_demo", "telefone", "Telefone"),
                CampoComUnidade("peso_demo", "peso", "Peso", unidade="kg"),
                SeletorDeQuantidade("quantidade_demo", "quantidade", "Quantidade"),
                Alternancia("notificacoes_demo", "notificacoes", "Receber notificações"),
                EscolhaMultipla(
                    "interesses_demo",
                    "interesses",
                    "Interesses",
                    (Opcao("Ações", "acoes"), Opcao("FIIs", "fiis"), Opcao("Renda fixa", "renda_fixa")),
                ),
            ),
        ),
        GaleriaDeImagens(
            (
                Imagem("https://example.invalid/foto-1.jpg", "Primeiro exemplo"),
                Imagem("https://example.invalid/foto-2.jpg", "Segundo exemplo"),
            ),
            "Imagens do item",
        ),
        TabelaFlexivel(
            (2, 1),
            (
                LinhaDeTabela((CelulaDeTabela((Texto("Item"),)), CelulaDeTabela((Texto("Valor"),)))),
                LinhaDeTabela((CelulaDeTabela((Texto("Plano"),)), CelulaDeTabela((Texto("R$ 49"),)))),
            ),
        ),
        Dialogo("dialogo_demo", "Revisar", (Texto("Conteúdo sobreposto e responsivo."),)),
    ),
    tema=Tema.OPERACAO,
    navegacao=Navegacao.INFERIOR,
)


def _superficie(nome: str, titulo: str, icone: str, tela: Tela) -> Superficie:
    return Superficie(
        nome,
        titulo,
        titulo,
        icone,
        f"exemplo de {titulo.lower()}",
        Fonte(f"dados_{nome}"),
        tela,
    )


APLICATIVO = Aplicativo(
    slug="catalogo-sdk",
    endpoint="https://example.invalid/mcp/",
    para_tipo="amigo",
    descricao="Catálogo de componentes seguros",
    descricao_humana="Exemplos do SDK Python do OkMigo Cartão",
    nome_visivel="Catálogo SDK",
    versao="1.0.0",
    conversa=(),
    superficies=(
        _superficie("inicio", "Início", "inicio", INICIO),
        _superficie("formulario", "Formulário", "perfil", FORMULARIO),
        _superficie("agenda", "Agenda", "agenda", AGENDA),
        _superficie("financeiro", "Financeiro", "financeiro", FINANCEIRO),
        _superficie("universais", "Universais", "mais", UNIVERSAIS),
    ),
)
