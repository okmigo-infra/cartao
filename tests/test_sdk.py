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
    CampoOculto,
    Coluna,
    ContratoDoSdkInvalido,
    EnfaseDaAcao,
    Fato,
    Fatos,
    Fonte,
    FormaDoGrafico,
    Grafico,
    Navegacao,
    Opcao,
    Ponto,
    Serie,
    Superficie,
    Tabela,
    Tela,
    Tema,
    Texto,
    TipoDeAcao,
)


class SdkTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
