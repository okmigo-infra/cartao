"""Contrato público da família de LEITURA DE DADOS.

⛔ Os casos que importam aqui são os NEGATIVOS. Um teste que só monta o
componente feliz e confere que o JSON saiu prova que o SDK compila — não prova
que o crivo recusa o ranking sem critério, a tendência sem alternativa textual
ou o comparador cujos valores não casam com os itens. É recusar que é a
função dessas travas, e teste que passa no cenário quebrado não é teste.
"""

import unittest

from okmigo_cartao import (
    Acao,
    Agenda,
    CabecalhoDeDetalhe,
    Comparador,
    ContratoDoSdkInvalido,
    CriterioComparado,
    EstadoDaInformacao,
    EstadoDoCompromisso,
    EstadoDoDado,
    Etiqueta,
    ItemComparado,
    ItemDaAgenda,
    ItemDeRanking,
    MenuDeAcoes,
    Minigrafico,
    Ranking,
    Tela,
    Texto,
    TomDaEtiqueta,
    validar,
)


def _corpo(tela, tipo=None):
    """O elemento reconstruído, já passado pelo crivo.

    ⚠️ `Tela` injeta o próprio cabeçalho no corpo, então `corpo[0]` é o TÍTULO
    — procurar pelo índice fazia o teste medir o cabeçalho e reprovar com uma
    mensagem que não tinha nada a ver com o componente.
    """
    reconstruida, erro = validar(
        tela.compilar(),
        escrituras={"favoritar"},
        leituras={"detalhar_ativo", "listar_ranking", "recarregar"},
    )
    assert erro is None, erro
    corpo = reconstruida["corpo"]
    if tipo is None:
        return next(no for no in corpo if no["tipo"] != "texto")
    return next(no for no in corpo if no["tipo"] == tipo)


class MinigraficoTest(unittest.TestCase):
    def test_tendencia_chega_com_alternativa_textual(self):
        tela = Tela(
            "Ativo",
            (Minigrafico((10, 11, 9, 12), "subiu 20% em quatro pregões"),),
        )
        no = _corpo(tela)
        self.assertEqual(no["tipo"], "minigrafico")
        self.assertEqual(no["valores"], [10.0, 11.0, 9.0, 12.0])
        self.assertEqual(no["alternativa"], "subiu 20% em quatro pregões")

    def test_sem_alternativa_o_sdk_recusa_antes_do_crivo(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            Minigrafico((1, 2, 3), "   ")

    def test_um_ponto_so_nao_e_tendencia(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            Minigrafico((7,), "um ponto")

    def test_crivo_derruba_tendencia_sem_alternativa_montada_a_mao(self):
        # O serviço que monta o JSON sem o SDK não escapa da regra.
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {"type": "okmigoMinigrafico", "valores": [1, 2, 3]},
                {"type": "TextBlock", "text": "resto da tela"},
            ],
        }
        reconstruida, erro = validar(tela)
        self.assertIsNone(erro)
        self.assertEqual(len(reconstruida["corpo"]), 1)
        self.assertEqual(reconstruida["corpo"][0]["tipo"], "texto")

    def test_valor_nao_numerico_vira_buraco_e_nao_desloca(self):
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "okmigoMinigrafico",
                    "valores": [1, "abacaxi", "1.234,50"],
                    "alternativa": "dois pontos válidos",
                }
            ],
        }
        reconstruida, _ = validar(tela)
        self.assertEqual(reconstruida["corpo"][0]["valores"], [1.0, 1234.5])


class RankingTest(unittest.TestCase):
    def _ranking(self, **extra):
        return Ranking(
            "Maiores altas",
            "variação percentual do dia",
            (
                ItemDeRanking(
                    "PETR4",
                    "R$ 38,20",
                    apoio="Petrobras PN",
                    variacao="↑ +2,41%",
                    tom=TomDaEtiqueta.POSITIVO,
                    id="PETR4",
                    ao_tocar=Acao.consultar("Abrir", "detalhar_ativo"),
                ),
                ItemDeRanking("VALE3", "R$ 54,10", variacao="↑ +1,02%"),
            ),
            base="fechamento de 19/09/2026",
            universo="B3 · 2.323 ativos elegíveis",
            **extra,
        )

    def test_posicao_e_do_ranking_nao_do_item(self):
        no = _corpo(Tela("Rankings", (self._ranking(),)))
        self.assertEqual([i["posicao"] for i in no["itens"]], [1, 2])

    def test_criterio_base_e_universo_atravessam_o_crivo(self):
        no = _corpo(Tela("Rankings", (self._ranking(),)))
        self.assertEqual(no["criterio"], "variação percentual do dia")
        self.assertEqual(no["base"], "fechamento de 19/09/2026")
        self.assertEqual(no["universo"], "B3 · 2.323 ativos elegíveis")

    def test_variacao_viaja_como_TEXTO_e_o_tom_e_redundante(self):
        # A regra de acessibilidade: quem não vê a cor lê a seta e o sinal.
        no = _corpo(Tela("Rankings", (self._ranking(),)))
        self.assertEqual(no["itens"][0]["variacao"], "↑ +2,41%")
        self.assertEqual(no["itens"][0]["tom"], "positivo")

    def test_sem_criterio_o_sdk_recusa(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            Ranking("Maiores altas", "", (ItemDeRanking("PETR4", "R$ 1"),))

    def test_crivo_derruba_ranking_sem_criterio_montado_a_mao(self):
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "okmigoRanking",
                    "titulo": "Maiores altas",
                    "itens": [{"rotulo": "PETR4", "valor": "R$ 38,20"}],
                    "fallback": {"type": "TextBlock", "text": "ranking indisponível"},
                }
            ],
        }
        reconstruida, erro = validar(tela)
        self.assertIsNone(erro)
        # Caiu — e o autor tinha declarado o que aparece no lugar.
        self.assertEqual(reconstruida["corpo"][0]["tipo"], "texto")
        self.assertEqual(reconstruida["corpo"][0]["texto"], "ranking indisponível")

    def test_item_sem_valor_some_e_a_numeracao_nao_pula(self):
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "okmigoRanking",
                    "titulo": "Maiores altas",
                    "criterio": "variação do dia",
                    "itens": [
                        {"rotulo": "PETR4", "valor": "R$ 38,20"},
                        {"rotulo": "SEM VALOR"},
                        {"rotulo": "VALE3", "valor": "R$ 54,10"},
                    ],
                }
            ],
        }
        reconstruida, _ = validar(tela)
        itens = reconstruida["corpo"][0]["itens"]
        self.assertEqual([i["rotulo"] for i in itens], ["PETR4", "VALE3"])
        self.assertEqual([i["posicao"] for i in itens], [1, 2])

    def test_item_nao_aceita_gesto_de_escrita(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            ItemDeRanking("PETR4", "R$ 1", ao_tocar=Acao.escrever("Favoritar", "favoritar"))

    def test_operacao_de_leitura_nao_declarada_recusa_a_tela_inteira(self):
        tela = Tela(
            "Rankings",
            (
                Ranking(
                    "Maiores altas",
                    "variação do dia",
                    (
                        ItemDeRanking(
                            "PETR4",
                            "R$ 1",
                            ao_tocar=Acao.consultar("Abrir", "operacao_fantasma"),
                        ),
                    ),
                ),
            ),
        )
        _, erro = validar(tela.compilar(), leituras={"detalhar_ativo"})
        self.assertIn("operacao_fantasma", erro)

    def test_fallback_do_ranking_e_a_mesma_lista_em_fatos(self):
        compilado = self._ranking().compilar()
        fatos = compilado["fallback"]["facts"]
        self.assertEqual(fatos[0]["title"], "1. PETR4")
        self.assertEqual(fatos[0]["value"], "R$ 38,20 · ↑ +2,41%")


class CabecalhoDeDetalheTest(unittest.TestCase):
    def test_favorito_e_escrita_conferida_como_qualquer_botao(self):
        tela = Tela(
            "SANB11",
            (
                CabecalhoDeDetalhe(
                    "SANB11",
                    valor="R$ 27,35",
                    subtitulo="Santander Brasil UNT",
                    variacao="↓ -0,80%",
                    tom=TomDaEtiqueta.NEGATIVO,
                    base="fechamento de 19/09",
                    etiquetas=(Etiqueta("Unit"), Etiqueta("Bancos")),
                    destacar=Acao.escrever("Favoritar", "favoritar"),
                    menu=MenuDeAcoes((Acao.consultar("Comparar", "detalhar_ativo"),)),
                ),
            ),
        )
        no = _corpo(tela)
        self.assertEqual(no["tipo"], "cabecalho_de_detalhe")
        self.assertEqual(no["destacar"]["enviar"], "favoritar")
        self.assertEqual(len(no["etiquetas"]), 2)
        self.assertEqual(no["menu"]["tipo"], "acoes")

    def test_favoritar_em_operacao_nao_declarada_recusa_a_tela(self):
        tela = Tela(
            "SANB11",
            (CabecalhoDeDetalhe("SANB11", destacar=Acao.escrever("Favoritar", "fantasma")),),
        )
        _, erro = validar(tela.compilar(), escrituras={"favoritar"})
        self.assertIn("fantasma", erro)

    def test_mais_de_quatro_etiquetas_o_sdk_recusa(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            CabecalhoDeDetalhe("X", etiquetas=tuple(Etiqueta(f"e{i}") for i in range(5)))


class EstadoDoDadoTest(unittest.TestCase):
    def test_desatualizado_nao_e_vazio(self):
        no = _corpo(
            Tela(
                "Hoje",
                (
                    EstadoDoDado(
                        EstadoDaInformacao.DESATUALIZADO,
                        "Cotações de ontem",
                        "A sincronização das 18h não rodou.",
                        base="fechamento de 19/09",
                        acao=Acao.consultar("Tentar de novo", "recarregar"),
                    ),
                ),
            )
        )
        self.assertEqual(no["situacao"], "desatualizado")
        self.assertEqual(no["base"], "fechamento de 19/09")
        self.assertEqual(no["acao"]["consultar"], "recarregar")

    def test_situacao_desconhecida_vira_parcial_e_nao_erro(self):
        # Inventar gravidade que o serviço não declarou assusta quem lê.
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "okmigoEstadoDoDado",
                    "situacao": "catastrofe",
                    "titulo": "Algo aconteceu",
                }
            ],
        }
        reconstruida, _ = validar(tela)
        self.assertEqual(reconstruida["corpo"][0]["situacao"], "parcial")

    def test_os_oito_estados_atravessam(self):
        for situacao in EstadoDaInformacao:
            with self.subTest(situacao=situacao):
                no = _corpo(Tela("x", (EstadoDoDado(situacao, "titulo"),)))
                self.assertEqual(no["situacao"], situacao.value)


class ComparadorTest(unittest.TestCase):
    def _comparador(self):
        return Comparador(
            "PETR4 × VALE3",
            (ItemComparado("PETR4", "Petrobras"), ItemComparado("VALE3", "Vale")),
            (
                CriterioComparado("P/L", ("8,20x", "5,10x"), "preço sobre lucro", melhor=1),
                CriterioComparado("Dividend yield", ("14,2%", ""), "12 meses"),
            ),
            base="fechamento de 19/09",
            nota="Comparação informativa; não é recomendação.",
        )

    def test_comparacao_atravessa_com_criterio_e_melhor(self):
        no = _corpo(Tela("Comparar", (self._comparador(),)))
        self.assertEqual(no["tipo"], "comparador")
        self.assertEqual(no["criterios"][0]["melhor"], 1)
        self.assertEqual(no["nota"], "Comparação informativa; não é recomendação.")

    def test_valor_ausente_vira_vazio_e_nao_encurta_a_linha(self):
        no = _corpo(Tela("Comparar", (self._comparador(),)))
        self.assertEqual(no["criterios"][1]["valores"], ["14,2%", ""])

    def test_criterio_com_menos_valores_que_itens_o_sdk_recusa(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            Comparador(
                "x",
                (ItemComparado("A"), ItemComparado("B")),
                (CriterioComparado("P/L", ("8,2x",)),),
            )

    def test_um_item_so_nao_e_comparacao(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            Comparador("x", (ItemComparado("A"),), (CriterioComparado("P/L", ("1",)),))

    def test_melhor_apontando_para_valor_ausente_e_descartado(self):
        # Eleger como "melhor" a coluna que está vazia é marcar o buraco.
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "okmigoComparador",
                    "titulo": "A × B",
                    "itens": [{"rotulo": "A"}, {"rotulo": "B"}],
                    "criterios": [{"rotulo": "P/L", "valores": ["8,2x", ""], "melhor": 1}],
                }
            ],
        }
        reconstruida, _ = validar(tela)
        self.assertNotIn("melhor", reconstruida["corpo"][0]["criterios"][0])

    def test_valores_a_mais_sao_prensados_no_numero_de_itens(self):
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "okmigoComparador",
                    "titulo": "A × B",
                    "itens": [{"rotulo": "A"}, {"rotulo": "B"}],
                    "criterios": [{"rotulo": "P/L", "valores": ["1", "2", "3", "4"]}],
                }
            ],
        }
        reconstruida, _ = validar(tela)
        self.assertEqual(reconstruida["corpo"][0]["criterios"][0]["valores"], ["1", "2"])


class AgendaTest(unittest.TestCase):
    def test_agenda_vazia_sobrevive_porque_o_vazio_e_a_resposta(self):
        no = _corpo(
            Tela(
                "Proventos",
                (Agenda("Próximos pagamentos", (), vazio="Nenhum provento anunciado."),),
            )
        )
        self.assertEqual(no["tipo"], "agenda")
        self.assertEqual(no["itens"], [])
        self.assertEqual(no["vazio"], "Nenhum provento anunciado.")

    def test_previsto_nao_vira_confirmado(self):
        no = _corpo(
            Tela(
                "Proventos",
                (
                    Agenda(
                        "Próximos",
                        (
                            ItemDaAgenda(
                                "02/10/2026",
                                "PETR4 · dividendo",
                                valor="R$ 0,72/ação",
                                estado=EstadoDoCompromisso.PREVISTO,
                            ),
                        ),
                    ),
                ),
            )
        )
        self.assertEqual(no["itens"][0]["estado"], "previsto")

    def test_item_sem_data_vira_sem_data_e_nao_some(self):
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "okmigoAgenda",
                    "titulo": "Próximos",
                    "itens": [
                        {"titulo": "HGLG11 · rendimento", "estado": "anunciado"},
                    ],
                }
            ],
        }
        reconstruida, _ = validar(tela)
        item = reconstruida["corpo"][0]["itens"][0]
        self.assertEqual(item["estado"], "sem_data")
        self.assertEqual(item["titulo"], "HGLG11 · rendimento")

    def test_estado_desconhecido_cai_em_anunciado(self):
        tela = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "okmigoAgenda",
                    "titulo": "Próximos",
                    "itens": [
                        {"titulo": "X", "data": "02/10", "estado": "garantido"},
                    ],
                }
            ],
        }
        reconstruida, _ = validar(tela)
        self.assertEqual(reconstruida["corpo"][0]["itens"][0]["estado"], "anunciado")

    def test_sem_data_declarada_o_sdk_exige_o_estado_certo(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            ItemDaAgenda("", "PETR4 · dividendo")


class CascaDaFamiliaTest(unittest.TestCase):
    def test_o_relatorio_sabe_explicar_por_que_cada_um_some(self):
        from okmigo_cartao import relatorio

        bruto = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {"type": "okmigoRanking", "titulo": "sem criterio", "itens": []},
                {"type": "TextBlock", "text": "sobra"},
            ],
        }
        tela, erro = validar(bruto)
        linhas = relatorio(bruto, tela, erro)
        self.assertTrue(any("okmigoRanking" in linha for linha in linhas), linhas)


if __name__ == "__main__":
    unittest.main()
