"""O catálogo Python compila só para o vocabulário fechado do crivo."""

import unittest

from okmigo_cartao import (
    Acao,
    AcaoDoEvento,
    Acoes,
    Alternar,
    AlvoDeVisibilidade,
    AoTocarODia,
    Arquivo,
    Calendario,
    CampoNumero,
    CampoTexto,
    CartaoFinanceiro,
    CartoesFinanceiros,
    ComAlternativa,
    Condicao,
    ContratoDoSdkInvalido,
    Copiar,
    Cronometro,
    Distribuicao,
    Documento,
    EnfaseDaAcao,
    EnviarEAvancar,
    Escolha,
    EstadoVazio,
    Evento,
    Fato,
    Ficha,
    FormatoDeArquivo,
    FormaDaEscolha,
    Formulario,
    GestoDoEvento,
    GradeDeMetricas,
    ItemDeDistribuicao,
    LancamentoFinanceiro,
    ListaFinanceira,
    Metrica,
    Opcao,
    Progresso,
    Repetir,
    Secao,
    SemanticaFinanceira,
    Tela,
    TipoDeEvento,
    TomDaSecao,
    TomFinanceiro,
    VistaDoCalendario,
    expandir,
    validar,
)


class ComponentesDoSdkTest(unittest.TestCase):
    def test_formulario_tipado_chega_ao_crivo_com_campos_escopados(self):
        tela = Tela(
            "Perfil",
            (
                Formulario(
                    "Dados básicos",
                    campos=(
                        CampoTexto(
                            "nome_perfil",
                            "nome",
                            "Nome",
                            obrigatorio=True,
                            maximo_de_caracteres=80,
                        ),
                        CampoNumero(
                            "peso_perfil",
                            "peso",
                            "Peso (kg)",
                            minimo=20,
                            maximo=400,
                        ),
                        Escolha(
                            "objetivo_perfil",
                            "objetivo",
                            "Objetivo",
                            (
                                Opcao("Ganhar força", "forca", "Treinos progressivos", "💪"),
                                Opcao(
                                    "Ter disposição",
                                    "disposicao",
                                    "Rotina sustentável",
                                    "⚡",
                                ),
                            ),
                            FormaDaEscolha.CARTOES,
                            obrigatoria=True,
                        ),
                        Arquivo(
                            "laudo_perfil",
                            "laudo",
                            "Laudo opcional",
                            (FormatoDeArquivo.PDF, FormatoDeArquivo.IMAGEM),
                        ),
                    ),
                    acoes=(
                        Acao.escrever(
                            "Salvar",
                            "salvar_perfil",
                            enfase=EnfaseDaAcao.PRIMARIA,
                        ),
                    ),
                    explicacao="Você poderá corrigir estes dados depois.",
                ),
            ),
        )

        normalizada = tela.conferir(escrituras={"salvar_perfil"})
        formulario = normalizada["corpo"][1]
        self.assertEqual(formulario["tipo"], "caixa")
        self.assertEqual(
            formulario["itens"][-1]["botoes"][0]["campos"],
            ["nome_perfil", "peso_perfil", "objetivo_perfil", "laudo_perfil"],
        )
        self.assertEqual(formulario["itens"][5]["tipo"], "arquivo")

    def test_estados_transicoes_e_fallback_nao_abrem_nova_fronteira(self):
        tela = Tela(
            "Etapas",
            (
                Secao(
                    (
                        CampoTexto("nome_etapa", "nome", "Nome"),
                        Acoes(
                            (
                                EnviarEAvancar(
                                    "Continuar",
                                    "salvar_etapa",
                                    (
                                        AlvoDeVisibilidade("etapa_um", False),
                                        AlvoDeVisibilidade("etapa_dois", True),
                                    ),
                                ),
                            )
                        ),
                    ),
                    id="etapa_um",
                    tom=TomDaSecao.ACENTO,
                ),
                Secao(
                    (Progresso(2, 2, "Etapas concluídas"),),
                    id="etapa_dois",
                    visivel=False,
                ),
                Acoes(
                    (
                        Alternar(
                            "Rever primeira etapa",
                            (
                                AlvoDeVisibilidade("etapa_um", True),
                                AlvoDeVisibilidade("etapa_dois", False),
                            ),
                            EnfaseDaAcao.SECUNDARIA,
                        ),
                    )
                ),
                ComAlternativa(
                    Copiar("Copiar código", "ABC-123"),
                    EstadoVazio("Código indisponível", "Tente novamente."),
                ),
                Cronometro("Descanso", 60),
            ),
        )

        normalizada = tela.conferir(escrituras={"salvar_etapa"})
        primeira = normalizada["corpo"][1]
        self.assertEqual(primeira["id"], "etapa_um")
        self.assertEqual(
            primeira["itens"][-1]["botoes"][0]["apos_enviar"],
            [
                {"id": "etapa_um", "mostrar": False},
                {"id": "etapa_dois", "mostrar": True},
            ],
        )
        self.assertEqual(normalizada["corpo"][2]["itens"][0]["tipo"], "progresso")
        self.assertEqual(normalizada["corpo"][4]["tipo"], "copiar")
        self.assertEqual(normalizada["corpo"][5]["tipo"], "cronometro")

    def test_calendario_tipado_preserva_leitura_e_escrita_declaradas(self):
        calendario = Calendario(
            eventos=(
                Evento(
                    "2026-09-14T10:00:00-03:00",
                    "Avaliação",
                    id="evt-1",
                    tipo=TipoDeEvento.ATENDIMENTO,
                ),
            ),
            vista=VistaDoCalendario.SEMANA,
            ao_tocar_o_dia=AoTocarODia("novo_atendimento", "data"),
            acoes_do_evento=(
                AcaoDoEvento(
                    TipoDeEvento.ATENDIMENTO,
                    {"atendimento_id": "id"},
                    titulo="Editar",
                    mostrar="editar_atendimento",
                ),
                AcaoDoEvento(
                    TipoDeEvento.ATENDIMENTO,
                    {"atendimento_id": "id", "inicio": "novo_inicio"},
                    gesto=GestoDoEvento.ARRASTAR,
                    enviar="remarcar_atendimento",
                ),
            ),
        )

        normalizada = Tela("Agenda", (calendario,)).conferir(
            escrituras={"remarcar_atendimento"}
        )
        saida = normalizada["corpo"][1]
        self.assertEqual(saida["tipo"], "calendario")
        self.assertEqual(saida["vista"], "semana")
        self.assertEqual(saida["ao_tocar_o_dia"]["preencher"], {"data": "data"})
        self.assertTrue(saida["acoes_do_evento"][1]["arrasta"])

    def test_documentos_e_componentes_financeiros_passam_pelo_crivo(self):
        lancamento = LancamentoFinanceiro(
            "Mercado",
            "−R$ 286,40",
            "Alimentação · Nubank",
            "🛒",
            SemanticaFinanceira.NEGATIVO,
            id="lan-1",
            grupo="14 SET, 2026",
            tipo="saidas",
        )
        tela = Tela(
            "Financeiro",
            (
                CartoesFinanceiros(
                    (
                        CartaoFinanceiro(
                            "Ultravioleta",
                            numero="•••• 4821",
                            tom=TomFinanceiro.VIOLETA,
                            fatura="R$ 3.240,18",
                            progresso_feito=42,
                            lancamentos=(lancamento,),
                        ),
                    )
                ),
                Distribuicao(
                    "Por categoria",
                    (ItemDeDistribuicao("Alimentação", 38, "38%", TomFinanceiro.LARANJA),),
                ),
                ListaFinanceira(
                    "Últimas transações",
                    (lancamento,),
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
        )

        normalizada = tela.conferir(leituras={"baixar_extrato"})
        self.assertEqual(
            [item["tipo"] for item in normalizada["corpo"][1:]],
            ["cartao_bancario", "distribuicao", "lista_financeira", "documento"],
        )
        self.assertTrue(normalizada["corpo"][3]["busca"])

    def test_composicoes_e_repeticao_expandem_antes_do_crivo(self):
        tela = Tela(
            "Operação",
            (
                GradeDeMetricas(
                    (Metrica("Abertos", "{abertos}"), Metrica("Hoje", "{hoje}"))
                ),
                Repetir(
                    Ficha(
                        "{titulo}",
                        "{detalhe}",
                        fatos=(Fato("Status", "{status}"),),
                    ),
                    quando=Condicao("status", ("aberto",)),
                ),
            ),
        )
        expandida = expandir(
            tela.compilar(),
            {"abertos": 1, "hoje": 3},
            [
                {"titulo": "Chamado 1", "detalhe": "Cliente A", "status": "aberto"},
                {"titulo": "Chamado 2", "detalhe": "Cliente B", "status": "fechado"},
            ],
        )
        normalizada, erro = validar(expandida)

        self.assertIsNone(erro)
        self.assertIsNotNone(normalizada)
        self.assertEqual(normalizada["corpo"][1]["grade"], True)
        self.assertEqual(normalizada["corpo"][2]["itens"][0]["texto"], "Chamado 1")
        self.assertEqual(len(normalizada["corpo"]), 3)

    def test_guardas_falham_na_autoria(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            CampoNumero("peso", "peso", "Peso", minimo=200, maximo=20)
        with self.assertRaises(ContratoDoSdkInvalido):
            Escolha("objetivo", "objetivo", "Objetivo")
        with self.assertRaises(ContratoDoSdkInvalido):
            EnviarEAvancar(
                "Salvar",
                "salvar",
                (AlvoDeVisibilidade("proxima"),),
            )
        with self.assertRaises(ContratoDoSdkInvalido):
            AcaoDoEvento(
                TipoDeEvento.COMPROMISSO,
                {"id": "senha"},
                titulo="Abrir",
                mostrar="formulario",
            )


if __name__ == "__main__":
    unittest.main()
