"""O crivo nos extremos: listas longas, textos longos e o teto de nós.

⛔ Todos estes casos atravessam o `expandir()` antes do `validar()`, porque é
assim que um cartão chega ao produto: a tela de verdade é o molde com dados.
Validar o molde cru não diria nada sobre a linha 201 nem sobre o nó 2001.
Cada positivo tem o negativo ao lado — a fronteira exata, dos dois lados.
"""

import unittest

from okmigo_cartao import MAX_NOS, expandir, validar


def cartao(*corpo, **topo):
    return {"type": "AdaptiveCard", "version": "1.5", "body": list(corpo), **topo}


def linhas(n, **extra):
    return [{"nome": f"Item {i}", "valor": i, **extra} for i in range(n)]


class TetoDeNosTest(unittest.TestCase):
    """2000 nós é do PRODUTO: acima dele a tela INTEIRA é recusada, e não
    truncada — uma tela pela metade seria pior que uma recusa com motivo."""

    MOLDE = cartao({"_repetir_lista": {"type": "TextBlock", "text": "{nome}"}})

    def test_exatamente_no_teto_passa(self):
        tela, erro = validar(expandir(self.MOLDE, {}, linhas(MAX_NOS)))
        self.assertIsNone(erro)
        self.assertEqual(len(tela["corpo"]), MAX_NOS)

    def test_um_acima_do_teto_recusa_a_tela_inteira(self):
        tela, erro = validar(expandir(self.MOLDE, {}, linhas(MAX_NOS + 1)))
        self.assertIsNone(tela)
        self.assertIn("grande demais", erro)

    def test_o_fallback_conta_no_teto(self):
        # Um tipo desconhecido que cai no fallback custa DOIS nós: o que caiu
        # e o que entrou no lugar. Quem soma só a saída erra a conta por um.
        molde = cartao(
            {"_repetir_lista": {"type": "TextBlock", "text": "{nome}"}},
            {"type": "TipoQueNaoExiste", "fallback": {"type": "TextBlock", "text": "plano B"}},
        )
        _, erro = validar(expandir(molde, {}, linhas(MAX_NOS - 2)))
        self.assertIsNone(erro)
        _, erro = validar(expandir(molde, {}, linhas(MAX_NOS - 1)))
        self.assertIn("grande demais", erro)

    def test_a_celula_de_tabela_conta_no_teto(self):
        # Cada linha de tabela custa a célula (uma caixa) mais o conteúdo dela.
        molde = cartao({
            "type": "Table",
            "columns": [{"width": 1}],
            "rows": [
                {"type": "TableRow", "cells": [{"type": "TableCell", "items": [
                    {"type": "TextBlock", "text": "Nome"}]}]},
                {"_repetir_lista": {"type": "TableRow", "cells": [{"type": "TableCell", "items": [
                    {"type": "TextBlock", "text": "{nome}"}]}]}},
            ],
        })
        # 1 (tabela) + 2 (cabeçalho) + 2 por linha, e só as 200 primeiras linhas contam.
        tela, erro = validar(expandir(molde, {}, linhas(10)))
        self.assertIsNone(erro)
        self.assertEqual(len(tela["corpo"][0]["linhas"]), 11)


    def test_a_celula_conta_no_teto_de_verdade(self):
        # Quatro tabelas cheias (cabeçalho + 199 linhas) custam 4 × (1 + 2 × 200)
        # = 1.604 nós; o resto do teto é completado com textos soltos.
        tabela = {
            "type": "Table", "columns": [{"width": 1}],
            "rows": [{"_repetir_lista": {"type": "TableRow", "cells": [{"type": "TableCell", "items": [
                {"type": "TextBlock", "text": "{nome}"}]}]}}],
        }
        def tela_com(soltos):
            return cartao(*([tabela] * 4), *([{"type": "TextBlock", "text": "x"}] * soltos))
        _, erro = validar(expandir(tela_com(MAX_NOS - 1604), {}, linhas(200)))
        self.assertIsNone(erro)
        _, erro = validar(expandir(tela_com(MAX_NOS - 1604 + 1), {}, linhas(200)))
        self.assertIn("grande demais", erro)


class ListasLongasTest(unittest.TestCase):
    def test_tabela_para_em_200_linhas_sem_recusar(self):
        molde = cartao({
            "type": "Table",
            "columns": [{"width": 1}],
            "firstRowAsHeader": False,
            "rows": [{"_repetir_lista": {"type": "TableRow", "cells": [{"type": "TableCell", "items": [
                {"type": "TextBlock", "text": "{nome}"}]}]}}],
        })
        tela, erro = validar(expandir(molde, {}, linhas(250)))
        self.assertIsNone(erro)
        self.assertEqual(len(tela["corpo"][0]["linhas"]), 200)
        # ⛔ E é o COMEÇO da lista que fica: quem ordena manda o que importa primeiro.
        self.assertEqual(tela["corpo"][0]["linhas"][0]["celulas"][0]["itens"][0]["texto"], "Item 0")
        tela, _ = validar(expandir(molde, {}, linhas(199)))
        self.assertEqual(len(tela["corpo"][0]["linhas"]), 199)

    def test_sublista_de_para_em_50_itens(self):
        molde = cartao({"_repetir_lista": {"type": "TextBlock", "text": "{nome}"}, "_de": "itens"})
        tela, erro = validar(expandir(molde, {"itens": linhas(60)}, []))
        self.assertIsNone(erro)
        self.assertEqual(len(tela["corpo"]), 50)
        tela, _ = validar(expandir(molde, {"itens": linhas(49)}, []))
        self.assertEqual(len(tela["corpo"]), 49)

    def test_escolha_para_em_60_opcoes(self):
        molde = cartao({
            "type": "Input.ChoiceSet", "id": "escolha", "label": "Escolha",
            "choices": [{"_repetir_lista": {"title": "{nome}", "value": "v{valor}"}}],
        })
        tela, erro = validar(expandir(molde, {}, linhas(80)))
        self.assertIsNone(erro)
        self.assertEqual(len(tela["corpo"][0]["opcoes"]), 60)

    def test_lista_vazia_nao_deixa_tabela_so_com_cabecalho(self):
        # O extremo de baixo: zero linhas. Sem fallback a tabela SOME (e não
        # vira um cabeçalho que promete dado); com fallback, entra a frase do autor.
        tabela = {
            "type": "Table", "columns": [{"width": 1}],
            "rows": [
                {"type": "TableRow", "cells": [{"type": "TableCell", "items": [
                    {"type": "TextBlock", "text": "Nome"}]}]},
                {"_repetir_lista": {"type": "TableRow", "cells": [{"type": "TableCell", "items": [
                    {"type": "TextBlock", "text": "{nome}"}]}]}},
            ],
        }
        titulo = {"type": "TextBlock", "text": "Lista"}
        tela, erro = validar(expandir(cartao(titulo, tabela), {}, []))
        self.assertIsNone(erro)
        self.assertEqual([n["tipo"] for n in tela["corpo"]], ["texto"])
        com_fallback = {**tabela, "fallback": {"type": "TextBlock", "text": "Nada por aqui."}}
        tela, _ = validar(expandir(cartao(titulo, com_fallback), {}, []))
        self.assertEqual(tela["corpo"][1]["texto"], "Nada por aqui.")


class TextosLongosTest(unittest.TestCase):
    LONGO = "palavra " * 800  # 6.400 caracteres

    def test_texto_titulo_e_valor_param_no_teto_do_papel(self):
        molde = cartao(
            {"type": "TextBlock", "text": "{t}"},
            {"type": "FactSet", "facts": [{"title": "{t}", "value": "{t}"}]},
            {"type": "ActionSet", "actions": [
                {"type": "Action.Execute", "title": "{t}", "data": {"operacao": "ler"}}]},
        )
        tela, erro = validar(expandir(molde, {"t": self.LONGO}, []), leituras={"ler"})
        self.assertIsNone(erro)
        texto, fatos, acoes = tela["corpo"]
        self.assertEqual(len(texto["texto"]), 400)
        self.assertEqual(len(fatos["fatos"][0]["titulo"]), 120)
        self.assertEqual(len(fatos["fatos"][0]["valor"]), 200)
        self.assertEqual(len(acoes["botoes"][0]["titulo"]), 40)

    def test_texto_curto_nao_e_tocado(self):
        tela, _ = validar(expandir(cartao({"type": "TextBlock", "text": "{t}"}), {"t": "curto"}, []))
        self.assertEqual(tela["corpo"][0]["texto"], "curto")

    def test_espacos_e_quebras_colapsam_antes_do_teto(self):
        # O teto mede o que a pessoa LÊ: 5.000 quebras de linha não gastam o texto.
        tela, _ = validar(cartao({"type": "TextBlock", "text": "\n" * 5000 + "fim"}))
        self.assertEqual(tela["corpo"][0]["texto"], "fim")

    def test_numero_extremo_sai_formatado_sem_notacao_cientifica(self):
        molde = cartao({"type": "TextBlock", "text": "{a} {b} {c}"})
        tela, _ = validar(expandir(molde, {"a": 1_000_000_000_000, "b": -987654321.25, "c": 0}, []))
        self.assertEqual(tela["corpo"][0]["texto"], "1.000.000.000.000 -987.654.321,25 0")


class AcessibilidadeNosExtremosTest(unittest.TestCase):
    """O texto que um leitor de tela lê não pode sumir no extremo: truncado,
    sim; vazio, nunca."""

    def test_alt_rotulo_e_titulo_sobrevivem_ao_texto_longo(self):
        longo = "descrição " * 300
        molde = cartao(
            {"type": "Image", "url": "https://produto.exemplo/a.png", "altText": "{t}"},
            {"type": "Input.Text", "id": "campo", "label": "{t}"},
            {"type": "ActionSet", "actions": [
                {"type": "Action.Submit", "title": "{t}", "data": {"operacao": "salvar"}}]},
        )
        from okmigo_cartao import Config

        tela, erro = validar(expandir(molde, {"t": longo}, []), escrituras={"salvar"},
                             config=Config(dominios=("produto.exemplo",)))
        self.assertIsNone(erro)
        imagem, campo, acoes = tela["corpo"]
        self.assertTrue(imagem["alt"].startswith("descrição"))
        self.assertLessEqual(len(imagem["alt"]), 120)
        self.assertTrue(campo["rotulo"].startswith("descrição"))
        self.assertTrue(acoes["botoes"][0]["titulo"].startswith("descrição"))

    def test_imagem_de_terceiro_vira_marcador_e_guarda_o_alt(self):
        # A imagem recusada (host de fora) não some: vira marcador — e o
        # marcador leva o `alt`, senão o leitor de tela lê um buraco.
        molde = cartao({"type": "Image", "url": "https://terceiro.exemplo/a.png", "altText": "{t}"})
        tela, erro = validar(expandir(molde, {"t": "Foto da fachada"}, []))
        self.assertIsNone(erro)
        self.assertEqual(tela["corpo"][0]["tipo"], "sem_imagem")
        self.assertEqual(tela["corpo"][0]["alt"], "Foto da fachada")

    def test_botao_sem_titulo_some_em_vez_de_virar_botao_mudo(self):
        molde = cartao({"type": "ActionSet", "actions": [
            {"type": "Action.Submit", "title": "{t}", "data": {"operacao": "salvar"}}]},
            {"type": "TextBlock", "text": "resto"})
        tela, _ = validar(expandir(molde, {"t": ""}, []), escrituras={"salvar"})
        self.assertEqual([n["tipo"] for n in tela["corpo"]], ["texto"])


if __name__ == "__main__":
    unittest.main()
