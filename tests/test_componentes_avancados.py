"""Contrato público dos componentes universais do SDK."""

import unittest

from okmigo_cartao import (
    Aba,
    Abas,
    Acao,
    AlvoDeVisibilidade,
    Alternancia,
    BarraDeValor,
    CampoComUnidade,
    CampoData,
    CampoDocumento,
    CampoEtiquetas,
    CampoHora,
    CampoMes,
    CampoMoeda,
    CampoTelefone,
    CampoUrl,
    CartaoClicavel,
    CelulaDeTabela,
    Confirmacao,
    ContratoDoSdkInvalido,
    Dialogo,
    EscolhaCondicional,
    EscolhaMultipla,
    EstadoDaEtapa,
    EtapaDaLinhaDoTempo,
    Etiqueta,
    Expansivel,
    FormaDaEscolhaMultipla,
    GaleriaDeImagens,
    Imagem,
    LinhaDeTabela,
    LinhaDoTempo,
    MenuDeAcoes,
    Opcao,
    Paginacao,
    RegraAoAlterar,
    SeletorDeQuantidade,
    Status,
    TabelaFlexivel,
    Tela,
    Texto,
    TomDaEtiqueta,
    validar,
)


class ComponentesAvancadosTest(unittest.TestCase):
    def test_acoes_contextuais_confirmacao_e_cartao_clicavel(self):
        tela = Tela(
            "Ativo",
            (
                CartaoClicavel(
                    (Texto("SANB11"),),
                    Acao.consultar("Abrir ativo", "detalhar_ativo"),
                    campos=(),
                    menu=MenuDeAcoes(
                        (
                            Acao.escrever(
                                "Remover",
                                "remover_favorito",
                                confirmacao=Confirmacao(
                                    "Remover favorito?",
                                    "O ativo sairá da sua lista.",
                                    "Remover",
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )

        normalizada = tela.conferir(
            leituras={"detalhar_ativo"}, escrituras={"remover_favorito"}
        )
        cartao = normalizada["corpo"][1]
        self.assertEqual(cartao["ao_tocar"]["consultar"], "detalhar_ativo")
        menu = cartao["itens"][1]
        self.assertTrue(menu["menu"])
        self.assertEqual(menu["rotulo"], "Mais opções")
        self.assertEqual(menu["botoes"][0]["confirmacao"]["confirmar"], "Remover")

    def test_componentes_de_leitura_sao_reconstruidos(self):
        tela = Tela(
            "Pedido",
            (
                Etiqueta("Novo", TomDaEtiqueta.INFORMATIVO),
                Status("Pago", TomDaEtiqueta.POSITIVO),
                GaleriaDeImagens((Imagem("/foto.jpg", "Prato servido"),)),
                LinhaDoTempo(
                    (
                        EtapaDaLinhaDoTempo(
                            "Recebido", "12:30", EstadoDaEtapa.CONCLUIDA
                        ),
                        EtapaDaLinhaDoTempo("Preparando", estado=EstadoDaEtapa.ATUAL),
                    )
                ),
                BarraDeValor("Meta", 7, 10, "7 de 10", TomDaEtiqueta.POSITIVO),
            ),
        )

        tipos = [no["tipo"] for no in tela.conferir()["corpo"]]
        self.assertEqual(
            tipos,
            ["texto", "etiqueta", "etiqueta", "galeria", "linha_do_tempo", "barra_valor"],
        )

    def test_abas_expansivel_e_dialogo_usam_apenas_visibilidade_local(self):
        tela = Tela(
            "Preferências",
            (
                Abas(
                    (
                        Aba("geral", "Geral", (Texto("Conteúdo geral"),)),
                        Aba("alertas", "Alertas", (Texto("Conteúdo de alertas"),)),
                    )
                ),
                Expansivel("detalhes", "Ver detalhes", (Texto("Detalhes"),)),
                Dialogo("confirmar", "Confirmação", (Texto("Revise os dados"),)),
            ),
        )

        corpo = tela.conferir()["corpo"]
        self.assertTrue(corpo[1]["itens"][0]["segmentado"])
        self.assertTrue(corpo[2]["itens"][0]["expansivel"])
        self.assertTrue(corpo[3]["sobreposto"])

    def test_tabela_flexivel_preserva_cabecalho_e_consulta(self):
        tabela = TabelaFlexivel(
            (2, 1),
            (
                LinhaDeTabela(
                    (CelulaDeTabela((Texto("Ativo"),)), CelulaDeTabela((Texto("Preço"),)))
                ),
                LinhaDeTabela(
                    (CelulaDeTabela((Texto("PETR4"),)), CelulaDeTabela((Texto("R$ 35"),))),
                    Acao.consultar("Abrir PETR4", "detalhar_ativo"),
                ),
            ),
        )
        normalizada = Tela("Tabela", (tabela,)).conferir(
            leituras={"detalhar_ativo"}
        )
        self.assertEqual(normalizada["corpo"][1]["tipo"], "tabela")
        self.assertEqual(
            normalizada["corpo"][1]["linhas"][1]["acao"]["consultar"],
            "detalhar_ativo",
        )

    def test_escolhas_semanticas_quantidade_e_alternancia(self):
        tela = Tela(
            "Formulário",
            (
                EscolhaMultipla(
                    "interesses",
                    "interesses",
                    "Interesses",
                    (Opcao("Ações", "acoes"), Opcao("FIIs", "fiis")),
                    ("acoes", "fiis"),
                    FormaDaEscolhaMultipla.CARTOES,
                ),
                EscolhaCondicional(
                    "tipo",
                    "tipo",
                    "Tipo",
                    (Opcao("Pessoa física", "pf"), Opcao("Empresa", "pj")),
                    (RegraAoAlterar("pj", (AlvoDeVisibilidade("cnpj", True),)),),
                ),
                CampoData("data", "data", "Data"),
                CampoHora("hora", "hora", "Hora"),
                CampoMes("mes", "mes", "Mês"),
                CampoMoeda("valor", "valor", "Valor"),
                CampoDocumento("cpf", "cpf", "CPF"),
                CampoTelefone("telefone", "telefone", "Telefone"),
                CampoUrl("site", "site", "Site"),
                CampoEtiquetas("tags", "tags", "Tags"),
                CampoComUnidade("peso", "peso", "Peso", unidade="kg"),
                SeletorDeQuantidade("qtd", "quantidade", "Quantidade", passo=2),
                Alternancia("avisos", "avisos", "Receber avisos", ligada=True),
            ),
        )

        corpo = tela.conferir()["corpo"][1:]
        self.assertTrue(corpo[0]["multipla"])
        self.assertEqual(corpo[0]["valor"], "acoes,fiis")
        self.assertEqual(corpo[1]["ao_alterar"][0]["alvos"][0]["id"], "cnpj")
        self.assertEqual(
            [no["formato"] for no in corpo[2:11]],
            ["data", "hora", "mes", "moeda", "documento", "telefone", "url", "etiquetas", "unidade"],
        )
        self.assertEqual(corpo[11]["controle"], "quantidade")
        self.assertEqual(corpo[11]["passo"], 2.0)
        self.assertEqual(corpo[12]["controle"], "alternancia")

    def test_paginacao_so_consulta_e_leva_cursor_escopado(self):
        paginacao = Paginacao("pagina-2", proxima=Acao.consultar("Próxima", "listar"))
        normalizada = Tela("Lista", (paginacao,)).conferir(leituras={"listar"})
        caixa = normalizada["corpo"][1]
        self.assertEqual(caixa["itens"][1]["botoes"][0]["campos"], ["paginacao_cursor"])

    def test_guardas_recusam_escrita_disfarcada_e_operacao_fora_do_contrato(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            CartaoClicavel((Texto("Item"),), Acao.escrever("Apagar", "apagar"))
        with self.assertRaises(ContratoDoSdkInvalido):
            Paginacao("x", proxima=Acao.escrever("Salvar", "salvar"))
        with self.assertRaises(ContratoDoSdkInvalido):
            MenuDeAcoes((Texto("não é ação"),))

        bruto = Tela(
            "Menu",
            (MenuDeAcoes((Acao.escrever("Apagar", "apagar"),)),),
        ).compilar()
        tela, erro = validar(bruto, escrituras={"outra"})
        self.assertIsNone(tela)
        self.assertIn("não é uma operação de escrita", erro or "")


if __name__ == "__main__":
    unittest.main()
