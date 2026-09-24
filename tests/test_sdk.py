"""O piloto do SDK: ergonomia, compilacao e guardas antes do crivo."""

import unittest

from okmigo_cartao import validar
from okmigo_cartao.sdk import (
    Acao,
    Acoes,
    Aplicativo,
    AplicativoDoContrato,
    Autorizar,
    Busca,
    BuscaDoAplicativo,
    CatalogoPublico,
    CampoOculto,
    Coluna,
    ConsultaDaFonte,
    ContatoAceito,
    ContratoDoSdkInvalido,
    Convite,
    EnfaseDaAcao,
    Fato,
    Fatos,
    Fonte,
    FormaDoGrafico,
    Grafico,
    GrupoDeNavegacao,
    HistoricoDeNavegacao,
    ICONES_DE_TELA,
    Navegacao,
    NavegacaoAgrupada,
    EstadoRestauravel,
    Opcao,
    OperacaoParametrizada,
    ParametroDaRota,
    PersistenciaDoEstado,
    Ponto,
    Serie,
    Rota,
    Superficie,
    Tabela,
    Tela,
    Tema,
    Texto,
    TipoDeAcao,
    TipoDeResultadoDaBusca,
)
from okmigo_cartao.componentes_de_navegacao import (
    CabecalhoDaTela,
    EtapaDoFluxo,
    Fluxo,
    MestreDetalhe,
)


class SdkTest(unittest.TestCase):
    def test_rotas_internas_sao_tipadas_e_nao_se_confundem_com_operacao(self):
        cabecalho = CabecalhoDaTela(
            "Clientes",
            acao_principal=Acao.navegar(
                "Abrir cliente", "cliente", parametros={"id": "{id}"}
            ),
        )
        tela = Tela("Clientes", (cabecalho,))
        app = Aplicativo(
            slug="clientes", endpoint="https://clientes.example/mcp",
            para_tipo="socio", descricao="Clientes", descricao_humana=None,
            nome_visivel="Clientes", versao="1", conversa=(),
            superficies=(
                Superficie("lista", "Lista", "Lista", "clientes", "lista", Fonte("listar"), tela),
                Superficie("detalhe", "Detalhe", "Detalhe", "perfil", "detalhe", Fonte("detalhar"), tela),
            ),
            rotas=(Rota("cliente", "detalhe", (ParametroDaRota("id"),)),),
        )

        manifesto = app.compilar()
        self.assertEqual(manifesto["rotas"][0]["superficie"], "detalhe")
        normalizada = tela.conferir(rotas={"cliente": {"id": "texto"}})
        self.assertEqual(
            normalizada["corpo"][1]["acao_principal"]["navegar"],
            {"rota": "cliente", "parametros": {"id": "{id}"}},
        )
        with self.assertRaisesRegex(ContratoDoSdkInvalido, "rota desconhecida"):
            Aplicativo(
                slug="clientes", endpoint="https://clientes.example/mcp",
                para_tipo="socio", descricao="Clientes", descricao_humana=None,
                nome_visivel="Clientes", versao="1", conversa=(),
                superficies=(Superficie("lista", "Lista", "Lista", "clientes", "lista", Fonte("listar"), tela),),
            )

    def test_parametro_da_rota_nao_pode_ter_nome_de_campo_da_plataforma(self):
        # ⛔⛔ `tenant` num parâmetro de rota é o botão escolhendo de qual
        # negócio a tela lê. Se esta guarda sair, este teste reprova.
        for reservado in (
            "credencial", "tenant", "hoje", "grupos", "grupos_nomes", "rota", "parametros",
        ):
            with self.subTest(reservado=reservado):
                with self.assertRaisesRegex(ContratoDoSdkInvalido, "reservado"):
                    ParametroDaRota(reservado)
        # E o nome vira o marcador `{rota.<nome>}` da ponte: nada de chave,
        # ponto ou hífen, que deixariam o marcador ambíguo.
        for torto in ("{id}", "cliente.id", "cliente-id", "1id", ""):
            with self.subTest(torto=torto):
                with self.assertRaises(ContratoDoSdkInvalido):
                    ParametroDaRota(torto)
        self.assertEqual(ParametroDaRota("cliente_id").nome, "cliente_id")

    def test_crivo_recusa_parametro_reservado_mesmo_sem_catalogo(self):
        cartao = {
            "type": "AdaptiveCard", "version": "1.5",
            "body": [{"type": "ActionSet", "actions": [{
                "type": "Action.Execute", "title": "Abrir",
                "data": {"okmigoNavegar": {"rota": "cliente", "parametros": {"tenant": "outro"}}},
            }]}],
        }
        tela, erro = validar(cartao)
        self.assertIsNone(tela)
        self.assertIn("reservado", erro or "")

    def test_voltar_do_cabecalho_que_grava_nao_vira_seta(self):
        cartao = {
            "type": "AdaptiveCard", "version": "1.5",
            "body": [{
                "type": "okmigoCabecalhoDaTela", "titulo": "Cliente",
                "voltar": {"type": "Action.Submit", "title": "Voltar",
                           "data": {"operacao": "apagar"}},
            }],
        }
        tela, erro = validar(cartao, frozenset({"apagar"}))
        self.assertIsNone(erro)
        self.assertNotIn("voltar", tela["corpo"][0])
        cartao["body"][0]["voltar"] = {
            "type": "Action.Execute", "title": "Voltar",
            "data": {"okmigoNavegar": {"rota": "lista", "parametros": {}}},
        }
        tela, erro = validar(cartao, frozenset({"apagar"}))
        self.assertIsNone(erro)
        self.assertEqual(tela["corpo"][0]["voltar"]["navegar"]["rota"], "lista")

    def test_manifesto_compila_busca_estado_e_historico_sem_layout_livre(self):
        tela = Tela("Início", (Texto("Conteúdo"),))
        app = Aplicativo(
            slug="erp", endpoint="https://erp.example/mcp", para_tipo="socio",
            descricao="ERP", descricao_humana=None, nome_visivel="ERP",
            versao="1", conversa=(),
            superficies=(Superficie("inicio", "Início", "Início", "inicio", "resumo", Fonte("inicio"), tela),),
            rotas=(Rota(
                "inicio", "inicio", compartilhavel=True,
                historico=True, favoritavel=True,
            ),),
            busca=BuscaDoAplicativo(
                "buscar", (TipoDeResultadoDaBusca("tela", "Tela", "inicio", "inicio"),)
            ),
            estados_restauraveis=(EstadoRestauravel(
                "inicio", persistencia=PersistenciaDoEstado.SINCRONIZADA,
                visoes_salvas=True, versao="painel-2", expira_em_horas=72,
            ),),
            historico_de_navegacao=HistoricoDeNavegacao(limite=12),
        )
        manifesto = app.compilar()
        self.assertEqual(manifesto["busca"]["operacao"], "buscar")
        self.assertTrue(manifesto["rotas"][0]["compartilhavel"])
        self.assertTrue(manifesto["rotas"][0]["historico"])
        self.assertTrue(manifesto["rotas"][0]["favoritavel"])
        self.assertTrue(manifesto["estados_restauraveis"][0]["visoes_salvas"])
        self.assertEqual(manifesto["estados_restauraveis"][0]["versao"], "painel-2")
        self.assertEqual(manifesto["estados_restauraveis"][0]["expira_em_horas"], 72)
        self.assertEqual(manifesto["historico_de_navegacao"]["limite"], 12)

    def test_mestre_detalhe_e_fluxo_atravessam_o_crivo(self):
        tela = Tela("Jornada", (
            MestreDetalhe("clientes", (Texto("Maria"),), (Texto("Detalhe da Maria"),), selecionado=True),
            Fluxo(
                "cadastro",
                (
                    EtapaDoFluxo("dados", "Dados", (Texto("Informe os dados"),)),
                    EtapaDoFluxo("revisao", "Revisão", (Texto("Confira"),)),
                ),
                "dados",
            ),
        ))
        normalizada = tela.conferir()
        self.assertEqual(normalizada["corpo"][1]["tipo"], "mestre_detalhe")
        self.assertEqual(normalizada["corpo"][2]["tipo"], "fluxo")
        self.assertEqual(normalizada["corpo"][2]["etapas"][0]["titulo"], "Dados")

    def test_navegacao_agrupada_cobre_todas_as_telas_uma_vez(self):
        tela = Tela("Tela", (Texto("Conteúdo"),))
        superficies = (
            Superficie("inicio", "Início", "Início", "inicio", "resumo", Fonte("inicio"), tela),
            Superficie("carteira", "Carteira", "Carteira", "carteira", "carteira", Fonte("carteira"), tela),
            Superficie("contas", "Contas", "Contas", "contas", "contas", Fonte("contas"), tela),
        )
        navegacao = NavegacaoAgrupada((
            GrupoDeNavegacao("inicio", "Início", "inicio", ("inicio", "carteira")),
            GrupoDeNavegacao("operacao", "Operação", "contas", ("contas",)),
        ))
        app = Aplicativo(
            slug="financeiro", endpoint="https://financeiro.example/mcp/",
            para_tipo="socio", descricao="Financeiro", descricao_humana=None,
            nome_visivel="Financeiro", versao="1.0.0", conversa=(),
            superficies=superficies, navegacao_agrupada=navegacao,
        )

        self.assertEqual(app.compilar()["navegacao"], {
            "tipo": "agrupada",
            "grupos": [
                {"nome": "inicio", "rotulo": "Início", "icone": "inicio",
                 "superficies": ["inicio", "carteira"], "inicial": "inicio"},
                {"nome": "operacao", "rotulo": "Operação", "icone": "contas",
                 "superficies": ["contas"], "inicial": "contas"},
            ],
        })

        with self.assertRaisesRegex(ContratoDoSdkInvalido, "sem grupo"):
            Aplicativo(
                slug="financeiro", endpoint="https://financeiro.example/mcp/",
                para_tipo="socio", descricao="Financeiro", descricao_humana=None,
                nome_visivel="Financeiro", versao="1.0.0", conversa=(),
                superficies=superficies,
                navegacao_agrupada=NavegacaoAgrupada((
                    GrupoDeNavegacao("inicio", "Início", "inicio", ("inicio",)),
                    GrupoDeNavegacao("operacao", "Operação", "contas", ("contas",)),
                )),
            )

    def test_navegacao_nao_entra_por_extras_nem_com_icone_que_ninguem_desenha(self):
        tela = Tela("Tela", (Texto("Conteúdo"),))
        superficies = (
            Superficie("inicio", "Início", "Início", "inicio", "resumo", Fonte("inicio"), tela),
            Superficie("contas", "Contas", "Contas", "contas", "contas", Fonte("contas"), tela),
        )
        with self.assertRaisesRegex(ContratoDoSdkInvalido, "reservados: navegacao"):
            Aplicativo(
                slug="financeiro", endpoint="https://financeiro.example/mcp/",
                para_tipo="socio", descricao="Financeiro", descricao_humana=None,
                nome_visivel="Financeiro", versao="1.0.0", conversa=(),
                superficies=superficies,
                extras={"navegacao": {"tipo": "agrupada", "grupos": [
                    {"nome": "g", "superficies": ["nao-existe"]}]}},
            )
        with self.assertRaisesRegex(ContratoDoSdkInvalido, "nao e desenhado"):
            GrupoDeNavegacao("inicio", "Início", "icone-que-ninguem-desenha", ("inicio",))
        self.assertIn("contas", ICONES_DE_TELA)

    def test_convite_declara_outros_destinos_sem_mudar_o_par_do_aceite(self):
        convite = Convite("aceitar_convite", "de", "prediomeu-morador",
                          pares=("prediomeu-admin",))
        self.assertEqual(convite.compilar(), {
            "operacao": "aceitar_convite", "parametro": "de",
            "par": "prediomeu-morador", "pares": ["prediomeu-admin"],
        })
        self.assertNotIn("pares", Convite("aceitar", "de", "morador").compilar())
        with self.assertRaises(ContratoDoSdkInvalido):
            Convite("aceitar", "de", "morador", pares=("morador",))

    def test_adaptador_leva_app_existente_ao_preview_e_aplica_intencoes(self):
        bruto = {
            "slug": "produto-legado",
            "endpoint": "http://produto/mcp",
            "versao": "1.0.0",
            "superficies": [{
                "nome": "inicio",
                "titulo": "Início",
                "rotulo": "Início",
                "icone": "inicio",
                "hint": "resumo",
                "fonte": {"resumo": {"operacao": "resumo"}},
                "cartao": {
                    "type": "AdaptiveCard",
                    "version": "1.5",
                    "body": [{"type": "TextBlock", "text": "Olá"}],
                },
            }],
        }

        app = AplicativoDoContrato(bruto, tema_padrao=Tema.OPERACAO)
        compilado = app.compilar()

        cartao = compilado["superficies"][0]["cartao"]
        self.assertEqual(cartao["okmigoTema"], "operacao-direta")
        self.assertEqual(cartao["okmigoNavegacao"], "inferior")
        self.assertNotIn("okmigoTema", bruto["superficies"][0]["cartao"])

    def test_adaptador_recusa_superficies_repetidas(self):
        manifesto = {
            "slug": "produto",
            "superficies": [
                {"nome": "inicio", "cartao": {"type": "AdaptiveCard", "body": [{}]}},
                {"nome": "inicio", "cartao": {"type": "AdaptiveCard", "body": [{}]}},
            ],
        }
        with self.assertRaises(ContratoDoSdkInvalido):
            AplicativoDoContrato(manifesto)

    def test_tela_tipado_compila_para_o_contrato_atual(self):
        tela = Tela(
            "Ativos",
            descricao="Escolha um ativo.",
            tema=Tema.MERCADO,
            navegacao=Navegacao.INFERIOR,
            componentes=(
                Busca(
                    "ticker_busca",
                    "ticker",
                    "Ativo da B3",
                    "Digite PETR4",
                    "buscar_ativos",
                    (Opcao("PETR4 · Petrobras", "PETR4"),),
                ),
            ),
        )

        bruto = tela.compilar()

        self.assertEqual(bruto["okmigoTema"], "mercado-editorial")
        self.assertEqual(bruto["okmigoNavegacao"], "inferior")
        self.assertEqual(bruto["body"][0]["size"], "extraLarge")
        self.assertEqual(bruto["body"][2]["okmigoBuscar"], "buscar_ativos")
        normalizada, erro = validar(bruto, leituras={"buscar_ativos"})
        self.assertIsNone(erro)
        self.assertEqual(normalizada["tema"], "mercado-editorial")
        self.assertEqual(
            tela.conferir(leituras={"buscar_ativos"})["navegacao"], "inferior"
        )

    def test_tabela_responsiva_tem_linha_consultavel_e_escrita_escopada(self):
        bruto = Tabela(
            colunas=(Coluna("Ativo", (Texto("{ticker}"),), largura=3),),
            ao_tocar=Acao.consultar("Ver ativo", "detalhar_ativo"),
            campos_da_linha=(CampoOculto("ticker_{ticker}", "ticker", "{ticker}"),),
            acoes_da_linha=(
                Acao.escrever(
                    "Remover",
                    "remover_ativo",
                    enfase=EnfaseDaAcao.DESTRUTIVA,
                    icone="lixeira",
                ),
            ),
        ).compilar()

        modelo = bruto["rows"][1]["_repetir_lista"]
        self.assertEqual(modelo["selectAction"]["type"], "Action.Execute")
        acao = modelo["cells"][-1]["items"][-1]["actions"][0]
        self.assertEqual(acao["type"], "Action.Submit")
        self.assertEqual(acao["okmigoIcone"], "delete")
        self.assertTrue(modelo["cells"][-1]["items"][0]["okmigoSomenteLeitura"])

    def test_sdk_recusa_erros_de_autoria_antes_do_renderer(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            Acao.consultar("Abrir", "javascript:alert(1)")
        with self.assertRaises(ContratoDoSdkInvalido):
            Busca("ticker com espaco", "ticker", "Ativo", "Digite", "buscar")
        with self.assertRaises(ContratoDoSdkInvalido):
            CampoOculto("item_{id", "item_id", "{id}")
        with self.assertRaises(ContratoDoSdkInvalido):
            Tabela(
                colunas=(Coluna("Ativo", (Texto("PETR4"),)),),
                ao_tocar=Acao("Apagar", "apagar", TipoDeAcao.ESCRITA),
            )
        with self.assertRaises(ContratoDoSdkInvalido):
            Tela(
                "Teste",
                (Acoes((Acao.consultar("Buscar", "buscar"),)),),
            ).conferir(leituras={"outra_operacao"})
        with self.assertRaises(ContratoDoSdkInvalido):
            Autorizar("Entrar", "Conectar conta", "javascript:alert(1)")

    def test_aplicativo_compila_todas_as_superficies_sem_json_manual(self):
        tela = Tela(
            "Mercado",
            componentes=(
                Fatos((Fato("Preço", "R$ 35,20"),)),
                Grafico(
                    "Preço no período",
                    (Serie("PETR4"),),
                    (Ponto("D1", (34.8,)), Ponto("D2", (35.2,))),
                    FormaDoGrafico.LINHA,
                ),
            ),
        )
        aplicativo = Aplicativo(
            slug="radaria",
            endpoint="http://radaria.internal/mcp/",
            para_tipo="amigo",
            descricao="Radar de mercado",
            descricao_humana="Acompanhe o mercado",
            nome_visivel="RadarIA",
            versao="1.0.0",
            conversa=("detalhar_ativo",),
            superficies=(
                Superficie(
                    "ativos",
                    "Ativos",
                    "Ativos",
                    "ativos",
                    "cotações e fundamentos",
                    Fonte("ativos_em_foco", "ativos"),
                    tela,
                ),
            ),
        )

        manifesto = aplicativo.compilar()

        self.assertEqual("radaria", manifesto["slug"])
        self.assertEqual(
            "ativos_em_foco", manifesto["superficies"][0]["fonte"]["resumo"]["operacao"]
        )
        self.assertEqual(
            "okmigoGrafico", manifesto["superficies"][0]["cartao"]["body"][2]["type"]
        )
        normalizada = tela.conferir()
        self.assertEqual("fatos", normalizada["corpo"][1]["tipo"])
        self.assertEqual("grafico", normalizada["corpo"][2]["tipo"])

    def test_sdk_compila_fontes_e_metadados_do_aplicativo_sem_extras(self):
        aplicativo = Aplicativo(
            slug="agenda",
            endpoint="https://agenda.example/mcp/",
            para_tipo="socio",
            descricao="Agenda compartilhada",
            descricao_humana="Organize os atendimentos",
            nome_visivel="Agenda",
            versao="2.0.0",
            conversa=("listar_horarios",),
            superficies=(
                Superficie(
                    "hoje",
                    "Hoje",
                    "Hoje",
                    "calendario",
                    "atendimentos do dia",
                    Fonte(
                        resumo=ConsultaDaFonte("resumir_agenda"),
                        lista=ConsultaDaFonte(
                            "listar_horarios",
                            caminho="horarios",
                            pedido={"periodo": "hoje"},
                        ),
                    ),
                    Tela("Hoje", componentes=(Texto("Sem horários"),)),
                ),
            ),
            eventos=OperacaoParametrizada("listar_eventos", "periodo"),
            avisa_antes=OperacaoParametrizada("avisar_evento", "evento_id"),
            convite=Convite("convidar_cliente", "cliente_id", "cliente"),
            aceita_contato=ContatoAceito("aceitar_contato", "contato_id", "nome"),
            publico=CatalogoPublico("listar_servicos", "consultar_expediente"),
        )

        manifesto = aplicativo.compilar()

        self.assertEqual(
            {
                "operacao": "listar_horarios",
                "pedido": {"periodo": "hoje"},
                "caminho": "horarios",
            },
            manifesto["superficies"][0]["fonte"]["lista"],
        )
        self.assertEqual(
            {"operacao": "listar_eventos", "parametro": "periodo"},
            manifesto["eventos"],
        )
        self.assertEqual(
            {"ofertas": "listar_servicos", "expediente": "consultar_expediente"},
            manifesto["publico"],
        )
        self.assertNotIn("extras", manifesto)


if __name__ == "__main__":
    unittest.main()


class OpcaoComImagemSdkTest(unittest.TestCase):
    """`Opcao.imagem` compila para `okmigoImagem` (OMINFRA-559)."""

    def test_a_imagem_entra_e_o_icone_continua(self):
        from okmigo_cartao.sdk import Opcao

        no = Opcao(titulo="Peito", valor="peito", nota="3 exercícios",
                   icone="💪", imagem="/img/peito").compilar()
        self.assertEqual(no["okmigoImagem"], "/img/peito")
        self.assertEqual(no["okmigoIcone"], "💪")
        self.assertEqual((no["title"], no["value"]), ("Peito", "peito"))

    def test_sem_imagem_a_chave_nao_aparece(self):
        """⚠️ Chave vazia no manifesto é chave que o crivo tem de olhar à toa."""
        from okmigo_cartao.sdk import Opcao

        self.assertNotIn("okmigoImagem", Opcao(titulo="Peito", valor="peito").compilar())
