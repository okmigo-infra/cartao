"""O crivo, com o caso negativo ao lado de cada positivo — teste que passa no
cenário quebrado não é teste."""
import unittest

from okmigo_cartao import Config, MAX_NOS, validar


def cartao(*corpo, **topo):
    return {"type": "AdaptiveCard", "version": "1.5", "body": list(corpo), **topo}


class EstruturaTest(unittest.TestCase):
    def test_recusa_o_que_nao_e_cartao(self):
        for bruto, trecho in [
            (42, "objeto"), ({"type": "Card", "body": [{}]}, "AdaptiveCard"),
            ({"type": "AdaptiveCard"}, "body"), ({"type": "AdaptiveCard", "body": []}, "body"),
        ]:
            with self.subTest(bruto=bruto):
                tela, erro = validar(bruto)
                self.assertIsNone(tela); self.assertIn(trecho, erro)

    def test_corpo_so_de_desconhecidos_e_recusado_e_nao_tela_em_branco(self):
        tela, erro = validar(cartao({"type": "Naoexiste", "x": 1}))
        self.assertIsNone(tela); self.assertIn("nenhum elemento", erro)

    def test_desconhecido_cai_no_fallback_do_schema(self):
        tela, erro = validar(cartao({"type": "Naoexiste", "fallback": {"type": "TextBlock", "text": "plano B"}}))
        self.assertIsNone(erro); self.assertEqual(tela["corpo"][0]["texto"], "plano B")

    def test_teto_de_nos_recusa_a_tela(self):
        muitos = [{"type": "TextBlock", "text": "x"}] * (MAX_NOS + 1)
        tela, erro = validar(cartao(*muitos))
        self.assertIsNone(tela); self.assertIn("grande demais", erro)
        tela, erro = validar(cartao(*muitos[:MAX_NOS]))
        self.assertIsNone(erro)

    def test_tema_e_navegacao_so_da_lista(self):
        tela, _ = validar(cartao({"type": "TextBlock", "text": "a"}, okmigoTema="financeiro-violeta", okmigoNavegacao="inferior"))
        self.assertEqual((tela["tema"], tela["navegacao"]), ("financeiro-violeta", "inferior"))
        tela, _ = validar(cartao({"type": "TextBlock", "text": "a"}, okmigoTema="verde-limao", okmigoNavegacao="lateral"))
        self.assertNotIn("tema", tela); self.assertNotIn("navegacao", tela)


class EscritaTest(unittest.TestCase):
    def botao(self, depois=None, operacao="salvar", escrituras={"salvar"}):
        acao = {"type": "Action.Submit", "title": "Continuar", "data": {"operacao": operacao}}
        if depois is not None:
            acao["okmigoAposEnviar"] = depois
        return validar(cartao({"type": "ActionSet", "actions": [acao]}), escrituras=escrituras)

    def test_operacao_fora_do_contrato_recusa_a_tela_inteira(self):
        tela, erro = self.botao(operacao="apagar")
        self.assertIsNone(tela); self.assertIn("apagar", erro)

    def test_sem_contrato_nao_confere(self):
        tela, erro = self.botao(operacao="qualquer", escrituras=None)
        self.assertIsNone(erro); self.assertEqual(tela["corpo"][0]["botoes"][0]["enviar"], "qualquer")

    def test_open_url_evapora(self):
        tela, erro = validar(cartao({"type": "ActionSet", "actions": [
            {"type": "Action.OpenUrl", "title": "Ir", "url": "https://exemplo.com"}]}))
        self.assertIsNone(tela); self.assertIn("nenhum elemento", erro)

    def test_transicao_depois_de_salvar_so_com_estados_explicitos(self):
        tela, erro = self.botao({"type": "Action.ToggleVisibility", "targetElements": [
            {"elementId": "perfil", "isVisible": False}, {"elementId": "foco", "isVisible": True}]})
        self.assertIsNone(erro)
        self.assertEqual(tela["corpo"][0]["botoes"][0]["apos_enviar"],
                         [{"id": "perfil", "mostrar": False}, {"id": "foco", "mostrar": True}])
        for depois in [{"type": "Action.OpenUrl", "url": "https://x"},
                       {"type": "Action.Submit", "data": {"operacao": "apagar"}},
                       {"type": "Action.ToggleVisibility", "targetElements": ["perfil", {"elementId": "perfil"},
                                                                              {"elementId": "perfil", "isVisible": "false"}]},
                       {"type": "Action.ToggleVisibility", "targetElements": 42}]:
            with self.subTest(depois=depois):
                tela, erro = self.botao(depois)
                self.assertIsNone(erro); self.assertNotIn("apos_enviar", tela["corpo"][0]["botoes"][0])

    def test_enfase_vem_do_style_e_do_mode(self):
        tela, _ = validar(cartao({"type": "ActionSet", "actions": [
            {"type": "Action.Submit", "title": "A", "data": {"operacao": "a"}, "style": "positive"},
            {"type": "Action.Submit", "title": "B", "data": {"operacao": "b"}, "style": "destructive", "mode": "secondary"},
            {"type": "Action.Submit", "title": "C", "data": {"operacao": "c"}, "mode": "secondary"},
            {"type": "Action.Submit", "title": "D", "data": {"operacao": "d"}, "style": "verde"}]}))
        self.assertEqual([b["enfase"] for b in tela["corpo"][0]["botoes"]],
                         ["primaria", "destrutiva", "discreta", "padrao"])

    def test_submit_escopa_os_ids_da_propria_caixa(self):
        tela, _ = validar(cartao(
            {"type": "Container", "items": [
                {"type": "Input.Text", "id": "quando_c30", "campo": "quando"},
                {"type": "ActionSet", "actions": [{"type": "Action.Submit", "title": "S", "data": {"operacao": "op"}}]}]},
            {"type": "Container", "items": [
                {"type": "Input.Text", "id": "quando_c31", "campo": "quando"},
                {"type": "ActionSet", "actions": [{"type": "Action.Submit", "title": "S", "data": {"operacao": "op"}}]}]}))
        self.assertEqual(tela["corpo"][0]["itens"][1]["botoes"][0]["campos"], ["quando_c30"])
        self.assertEqual(tela["corpo"][1]["itens"][1]["botoes"][0]["campos"], ["quando_c31"])

    def test_caixa_que_perdeu_obrigatorio_perde_os_botoes(self):
        tela, _ = validar(cartao({"type": "Container", "items": [
            {"type": "Input.ChoiceSet", "id": "motivo", "isRequired": True, "choices": []},
            {"type": "ActionSet", "actions": [{"type": "Action.Submit", "title": "Aceitar", "data": {"operacao": "op"}}]}]}))
        self.assertEqual([i["tipo"] for i in tela["corpo"][0]["itens"]], [])
        tela, _ = validar(cartao({"type": "Container", "items": [
            {"type": "Input.ChoiceSet", "id": "motivo", "isRequired": True, "choices": [{"title": "A", "value": "a"}]},
            {"type": "ActionSet", "actions": [{"type": "Action.Submit", "title": "Aceitar", "data": {"operacao": "op"}}]}]}))
        self.assertEqual([i["tipo"] for i in tela["corpo"][0]["itens"]], ["escolha", "acoes"])


class ConfigTest(unittest.TestCase):
    NOSSA = Config(dominios=("exemplo.com", "cdn.exemplo.net"), base_de_imagens="https://exemplo.com/")

    def test_imagem_so_do_dominio_configurado_e_absoluta(self):
        for url, esperado in [
            ("/img/abc", "https://exemplo.com/img/abc"),
            ("https://exemplo.com/x.png", "https://exemplo.com/x.png"),
            ("https://fit.exemplo.com/x.png", "https://fit.exemplo.com/x.png"),
            ("https://cdn.exemplo.net/x.png", "https://cdn.exemplo.net/x.png"),
        ]:
            with self.subTest(url=url):
                tela, _ = validar(cartao({"type": "Image", "url": url}), config=self.NOSSA)
                self.assertEqual((tela["corpo"][0]["tipo"], tela["corpo"][0]["url"]), ("imagem", esperado))
        for url in ["https://outro.com/x.png", "http://exemplo.com/x.png", "https://exemplo.com.br/x.png",
                    "https://mau.example@exemplo.com/x", "https://exemplo.com:8443/x.png", ""]:
            with self.subTest(url=url):
                tela, _ = validar(cartao({"type": "Image", "url": url, "altText": "foto"}), config=self.NOSSA)
                self.assertEqual(tela["corpo"][0]["tipo"], "sem_imagem")

    def test_sem_config_nenhum_dominio_e_nosso(self):
        tela, _ = validar(cartao({"type": "Image", "url": "https://exemplo.com/x.png"}))
        self.assertEqual(tela["corpo"][0]["tipo"], "sem_imagem")

    def test_autorizar_recusa_o_proprio_dominio_e_aceita_terceiro(self):
        def aut(url):
            tela, _ = validar(cartao({"type": "okmigoAutorizar", "url": url, "rotulo": "Autorizar",
                                      "motivo": "ler sua conta"}, {"type": "TextBlock", "text": "x"}), config=self.NOSSA)
            return [n["tipo"] for n in tela["corpo"]]
        self.assertEqual(aut("https://banco.com.br/autorizar?t=abc"), ["autorizar", "texto"])
        for ruim in ["https://exemplo.com/autorizar", "https://app.exemplo.com/a", "http://banco.com.br/a",
                     "https://banco.com.br@mau.example/a", "https://10.0.0.1/a", "https://banco.com.br:8080/a",
                     "javascript:alert(1)", "https://" + "a" * 3000]:
            with self.subTest(ruim=ruim):
                self.assertEqual(aut(ruim), ["texto"])

    def test_autorizar_e_um_por_cartao(self):
        tela, _ = validar(cartao(
            {"type": "okmigoAutorizar", "url": "https://b1.com/a", "rotulo": "1", "motivo": "m"},
            {"type": "okmigoAutorizar", "url": "https://b2.com/a", "rotulo": "2", "motivo": "m"}))
        self.assertEqual([n["onde"] for n in tela["corpo"]], ["b1.com"])

    def test_anexo_so_aperta_o_teto(self):
        cfg = Config(anexo_max_bytes=1000)
        for declarado, esperado in [(None, 1000), (500, 500), (5000, 1000), (0, 1000), (-1, 1000)]:
            with self.subTest(declarado=declarado):
                no = {"type": "okmigoArquivo", "id": "f", "maxBytes": declarado} if declarado is not None \
                    else {"type": "okmigoArquivo", "id": "f"}
                tela, _ = validar(cartao(no), config=cfg)
                self.assertEqual(tela["corpo"][0]["max_bytes"], esperado)

    def test_config_nao_vaza_entre_chamadas(self):
        validar(cartao({"type": "Image", "url": "/img/a"}), config=self.NOSSA)
        tela, _ = validar(cartao({"type": "Image", "url": "/img/a"}))
        self.assertEqual(tela["corpo"][0]["url"], "/img/a")


class VocabularioTest(unittest.TestCase):
    def test_palavras_fora_da_lista_caem_no_padrao_nunca_passam(self):
        tela, _ = validar(cartao({"type": "TextBlock", "text": "t", "size": "gigante", "weight": "pesado",
                                  "color": "attention", "horizontalAlignment": "diagonal"}))
        t = tela["corpo"][0]
        self.assertEqual((t["tamanho"], t["peso"], t["alinhamento"]), ("default", "default", "left"))
        self.assertNotIn("color", t); self.assertNotIn("cor", t)

    def test_numero_e_um_tipo_e_texto_e_outro(self):
        tela, _ = validar(cartao({"type": "Input.Number", "id": "preco", "min": 0},
                                 {"type": "Input.Text", "id": "obs", "isMultiline": True, "maxLength": 9999}))
        self.assertEqual(tela["corpo"][0]["formato"], "numero")
        self.assertEqual((tela["corpo"][1]["linhas"], tela["corpo"][1]["max"]), (4, 400))

    def test_input_sem_id_some(self):
        tela, erro = validar(cartao({"type": "Input.Text"}, {"type": "TextBlock", "text": "x"}))
        self.assertEqual([n["tipo"] for n in tela["corpo"]], ["texto"])

    def test_choiceset_tres_formas_e_a_trava_do_estrito(self):
        base = {"type": "Input.ChoiceSet", "id": "h", "value": "fora",
                "choices": [{"title": "Nove", "value": "09:00", "okmigoNota": "cedo", "okmigoIcone": "🌅"}]}
        lista, _ = validar(cartao(base))
        fichas, _ = validar(cartao({**base, "style": "expanded"}))
        livre, _ = validar(cartao({**base, "style": "filtered"}))
        busca, _ = validar(cartao({**base, "style": "filtered", "okmigoEstrito": True}))
        self.assertEqual((lista["corpo"][0]["tipo"], lista["corpo"][0]["forma"], lista["corpo"][0]["valor"]), ("escolha", "lista", ""))
        self.assertEqual(fichas["corpo"][0]["forma"], "cartoes")
        self.assertEqual(fichas["corpo"][0]["opcoes"][0]["nota"], "cedo")
        self.assertEqual((livre["corpo"][0]["tipo"], livre["corpo"][0]["valor"]), ("escolha_livre", "fora"))
        self.assertEqual((busca["corpo"][0]["tipo"], busca["corpo"][0]["forma"]), ("escolha", "busca"))

    def test_quem_opera_e_buraco_que_o_produto_preenche(self):
        """`okmigoQuemOpera`: as opções são de quem HOSPEDA, não do autor.

        ⛔ O caso que a pediu: uma agenda precisa saber quem atende, e a
        alternativa obrigaria o serviço a conhecer o quadro de pessoal do
        cliente dele. Com a dica ele declara o buraco e recebe, no Submit,
        apenas o nome escolhido.
        """
        base = {"type": "Input.ChoiceSet", "id": "prof", "campo": "nome",
                "label": "Quem atende", "style": "expanded"}

        # POSITIVO: marcado, e a lista vazia NÃO derruba o campo
        tela, _ = validar(cartao({**base, "okmigoQuemOpera": True}))
        self.assertEqual(tela["corpo"][0]["tipo"], "escolha")
        self.assertIs(tela["corpo"][0]["quem_opera"], True)
        self.assertEqual(tela["corpo"][0]["opcoes"], [])

        # POSITIVO: as `choices` do autor são IGNORADAS — senão a tela
        # ofereceria gente que não opera ao lado de gente que opera.
        tela, _ = validar(cartao({**base, "okmigoQuemOpera": True,
                                  "choices": [{"title": "Estranho", "value": "x"}]}))
        self.assertEqual(tela["corpo"][0]["opcoes"], [])

        # POSITIVO: força o ESTRITO. Livre seria um campo de texto com sugestão.
        tela, _ = validar(cartao({**base, "style": "filtered",
                                  "okmigoQuemOpera": True}))
        self.assertEqual((tela["corpo"][0]["tipo"], tela["corpo"][0]["forma"]),
                         ("escolha", "busca"))

        # ⛔ NEGATIVO 1: sem a dica, lista vazia continua derrubando o campo.
        tela, _ = validar(cartao(base))
        self.assertIsNone(tela)

        # ⛔ NEGATIVO 2: valor que não é `True` não liga nada — a dica é
        # booleana, e "sim" viria de quem escreveu o manifesto de memória.
        tela, _ = validar(cartao({**base, "okmigoQuemOpera": "sim"}))
        self.assertIsNone(tela)

        # ⛔ NEGATIVO 3: sem a dica e COM opções, nada de `quem_opera` na saída
        # — quem hospeda não pode confundir escolha comum com buraco a encher.
        tela, _ = validar(cartao({**base, "choices": [{"title": "A", "value": "a"}]}))
        self.assertNotIn("quem_opera", tela["corpo"][0])

    def test_tabela_sem_linha_de_dado_some(self):
        so_cabecalho = {"type": "Table", "columns": [{"width": 1}], "rows": [
            {"type": "TableRow", "cells": [{"type": "TableCell", "items": [{"type": "TextBlock", "text": "Nome"}]}]}]}
        tela, erro = validar(cartao(so_cabecalho))
        self.assertIsNone(tela)
        com_dado = {**so_cabecalho, "rows": so_cabecalho["rows"] * 2}
        tela, _ = validar(cartao(com_dado))
        self.assertEqual((tela["corpo"][0]["tipo"], len(tela["corpo"][0]["linhas"])), ("tabela", 2))

    def test_grafico_aceita_numero_cru_e_formatado_e_recusa_nan(self):
        tela, _ = validar(cartao({"type": "okmigoGrafico", "series": [{"rotulo": "S"}],
                                  "pontos": [{"rotulo": "a", "valores": [1200]}, {"rotulo": "b", "valores": ["1.200,50"]},
                                             {"rotulo": "c", "valores": ["nan"]}, {"rotulo": "d", "valores": ["x"]}]}))
        self.assertEqual([p["valores"] for p in tela["corpo"][0]["pontos"]], [[1200.0], [1200.5]])

    def test_progresso_prensa_feito_e_recusa_de_invalido(self):
        tela, _ = validar(cartao({"type": "okmigoProgresso", "feito": 9, "de": 6}, {"type": "okmigoProgresso", "feito": 1, "de": 0},
                                 {"type": "okmigoProgresso", "feito": -3, "de": 6}))
        self.assertEqual([(n["feito"], n["de"]) for n in tela["corpo"]], [(6, 6), (0, 6)])

    def test_cronometro_dentro_da_faixa(self):
        tela, _ = validar(cartao({"type": "okmigoCronometro", "rotulo": "Descanso", "segundos": 90},
                                 {"type": "okmigoCronometro", "rotulo": "x", "segundos": 0},
                                 {"type": "okmigoCronometro", "rotulo": "x", "segundos": 99999},
                                 {"type": "okmigoCronometro", "segundos": 30}))
        self.assertEqual([n["segundos"] for n in tela["corpo"]], [90])

    def test_documento_fora_das_leituras_recusa_a_tela(self):
        doc = {"type": "okmigoDocumento", "titulo": "Nota", "ler": {"operacao": "baixar", "pedido": {"id": 7, "x": {"n": 1}}}}
        tela, erro = validar(cartao(doc), leituras={"outra"})
        self.assertIsNone(tela); self.assertIn("baixar", erro)
        tela, erro = validar(cartao(doc), leituras={"baixar"})
        self.assertEqual(tela["corpo"][0]["ler"], {"operacao": "baixar", "pedido": {"id": 7}})

    def test_grade_quatro_intencoes(self):
        for dica, esperado in [(True, True), ("larga", "larga"), ("compacta", "compacta"), ("etiquetas", "etiquetas"),
                               ("gigante", True), (None, False)]:
            with self.subTest(dica=dica):
                no = {"type": "Container", "items": [{"type": "TextBlock", "text": "x"}]}
                if dica is not None:
                    no["okmigoGrade"] = dica
                tela, _ = validar(cartao(no))
                self.assertEqual(tela["corpo"][0]["grade"], esperado)


if __name__ == "__main__":
    unittest.main()
