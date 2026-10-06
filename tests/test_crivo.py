"""O crivo, com o caso negativo ao lado de cada positivo — teste que passa no
cenário quebrado não é teste."""

import json
import unittest

from okmigo_cartao import Config, MAX_NOS, validar


def cartao(*corpo, **topo):
    return {"type": "AdaptiveCard", "version": "1.5", "body": list(corpo), **topo}


class EstruturaTest(unittest.TestCase):
    def test_toque_na_regua_preserva_hora_e_descarta_dado_inventado(self):
        tela, erro = validar(cartao({
            "type": "okmigoCalendario",
            "vista": "dia",
            "de": "2026-09-27",
            "eventos": [],
            "aoTocarODia": {
                "mostrar": "novo_compromisso",
                "preencher": {
                    "dia": "data",
                    "hora": "hora",
                    "campo_proibido": "coordenada_do_toque",
                },
            },
        }))

        self.assertIsNone(erro)
        self.assertEqual(tela["corpo"][0]["ao_tocar_o_dia"]["preencher"], {
            "dia": "data",
            "hora": "hora",
        })

    def test_caixas_clicaveis_aninhadas_nao_misturam_campos(self):
        def acao(nome):
            return {"type": "Action.Execute", "title": nome, "data": {"operacao": nome}}

        tela, erro = validar(
            cartao({
                "type": "Container", "items": [
                    {"type": "Input.Text", "id": "criterio_altas", "campo": "criterio", "value": "altas", "isVisible": False},
                    {"type": "TextBlock", "text": "Maiores altas"},
                    {"type": "Container", "items": [
                        {"type": "Input.Text", "id": "ticker_petr4", "campo": "ticker", "value": "PETR4", "isVisible": False},
                        {"type": "TextBlock", "text": "PETR4"},
                    ], "selectAction": acao("detalhar_ativo")},
                ], "selectAction": acao("ranking_do_mercado"),
            }),
            leituras={"detalhar_ativo", "ranking_do_mercado"},
        )
        self.assertIsNone(erro)
        mae = tela["corpo"][0]
        filha = next(item for item in mae["itens"] if item["tipo"] == "caixa")
        self.assertEqual(mae["ao_tocar"]["campos"], ["criterio_altas"])
        self.assertEqual(filha["ao_tocar"]["campos"], ["ticker_petr4"])

    def test_recusa_o_que_nao_e_cartao(self):
        for bruto, trecho in [
            (42, "objeto"),
            ({"type": "Card", "body": [{}]}, "AdaptiveCard"),
            ({"type": "AdaptiveCard"}, "body"),
            ({"type": "AdaptiveCard", "body": []}, "body"),
        ]:
            with self.subTest(bruto=bruto):
                tela, erro = validar(bruto)
                self.assertIsNone(tela)
                self.assertIn(trecho, erro)

    def test_corpo_so_de_desconhecidos_e_recusado_e_nao_tela_em_branco(self):
        tela, erro = validar(cartao({"type": "Naoexiste", "x": 1}))
        self.assertIsNone(tela)
        self.assertIn("nenhum elemento", erro)

    def test_desconhecido_cai_no_fallback_do_schema(self):
        tela, erro = validar(
            cartao(
                {
                    "type": "Naoexiste",
                    "fallback": {"type": "TextBlock", "text": "plano B"},
                }
            )
        )
        self.assertIsNone(erro)
        self.assertEqual(tela["corpo"][0]["texto"], "plano B")

    def test_teto_de_nos_recusa_a_tela(self):
        muitos = [{"type": "TextBlock", "text": "x"}] * (MAX_NOS + 1)
        tela, erro = validar(cartao(*muitos))
        self.assertIsNone(tela)
        self.assertIn("grande demais", erro)
        tela, erro = validar(cartao(*muitos[:MAX_NOS]))
        self.assertIsNone(erro)

    def test_tema_e_navegacao_so_da_lista(self):
        for tema in (
            "financeiro-violeta",
            "jornada-ativa",
            "mercado-editorial",
            "operacao-direta",
        ):
            with self.subTest(tema=tema):
                tela, _ = validar(
                    cartao(
                        {"type": "TextBlock", "text": "a"},
                        okmigoTema=tema,
                        okmigoNavegacao="inferior",
                    )
                )
                self.assertEqual((tela["tema"], tela["navegacao"]), (tema, "inferior"))
        tela, _ = validar(
            cartao(
                {"type": "TextBlock", "text": "a"},
                okmigoTema="verde-limao",
                okmigoNavegacao="lateral",
            )
        )
        self.assertNotIn("tema", tela)
        self.assertNotIn("navegacao", tela)

    def test_variante_desktop_e_reconstruida_e_nao_repassada(self):
        bruto = cartao(
            {"type": "TextBlock", "text": "celular"},
            okmigoTema="operacao-direta",
            okmigoNavegacao="inferior",
            okmigoDesktop=cartao(
                {"type": "TextBlock", "text": "desktop", "cor": "nao passa"},
                okmigoTema="operacao-direta",
                okmigoNavegacao="inferior",
                lixo="nao passa",
            ),
        )
        tela, erro = validar(bruto)
        self.assertIsNone(erro)
        self.assertEqual(tela["corpo"][0]["texto"], "celular")
        self.assertEqual(tela["desktop"]["corpo"][0]["texto"], "desktop")
        self.assertNotIn("lixo", tela["desktop"])

    def test_variante_desktop_invalida_recusa_a_tela_inteira(self):
        tela, erro = validar(cartao(
            {"type": "TextBlock", "text": "celular"},
            okmigoDesktop={"type": "AdaptiveCard", "body": []},
        ))
        self.assertIsNone(tela)
        self.assertIn("variante desktop inválida", erro)


class EscritaTest(unittest.TestCase):
    def botao(self, depois=None, operacao="salvar", escrituras=frozenset({"salvar"})):
        acao = {
            "type": "Action.Submit",
            "title": "Continuar",
            "data": {"operacao": operacao},
        }
        if depois is not None:
            acao["okmigoAposEnviar"] = depois
        return validar(
            cartao({"type": "ActionSet", "actions": [acao]}), escrituras=escrituras
        )

    def test_operacao_fora_do_contrato_recusa_a_tela_inteira(self):
        tela, erro = self.botao(operacao="apagar")
        self.assertIsNone(tela)
        self.assertIn("apagar", erro)

    def test_sem_contrato_nao_confere(self):
        tela, erro = self.botao(operacao="qualquer", escrituras=None)
        self.assertIsNone(erro)
        self.assertEqual(tela["corpo"][0]["botoes"][0]["enviar"], "qualquer")

    def test_open_url_evapora(self):
        tela, erro = validar(
            cartao(
                {
                    "type": "ActionSet",
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "Ir",
                            "url": "https://exemplo.com",
                        }
                    ],
                }
            )
        )
        self.assertIsNone(tela)
        self.assertIn("nenhum elemento", erro)

    def test_transicao_depois_de_salvar_so_com_estados_explicitos(self):
        tela, erro = self.botao(
            {
                "type": "Action.ToggleVisibility",
                "targetElements": [
                    {"elementId": "perfil", "isVisible": False},
                    {"elementId": "foco", "isVisible": True},
                ],
            }
        )
        self.assertIsNone(erro)
        self.assertEqual(
            tela["corpo"][0]["botoes"][0]["apos_enviar"],
            [{"id": "perfil", "mostrar": False}, {"id": "foco", "mostrar": True}],
        )
        for depois in [
            {"type": "Action.OpenUrl", "url": "https://x"},
            {"type": "Action.Submit", "data": {"operacao": "apagar"}},
            {
                "type": "Action.ToggleVisibility",
                "targetElements": [
                    "perfil",
                    {"elementId": "perfil"},
                    {"elementId": "perfil", "isVisible": "false"},
                ],
            },
            {"type": "Action.ToggleVisibility", "targetElements": 42},
        ]:
            with self.subTest(depois=depois):
                tela, erro = self.botao(depois)
                self.assertIsNone(erro)
                self.assertNotIn("apos_enviar", tela["corpo"][0]["botoes"][0])

    def test_enfase_vem_do_style_e_do_mode(self):
        tela, _ = validar(
            cartao(
                {
                    "type": "ActionSet",
                    "actions": [
                        {
                            "type": "Action.Submit",
                            "title": "A",
                            "data": {"operacao": "a"},
                            "style": "positive",
                        },
                        {
                            "type": "Action.Submit",
                            "title": "B",
                            "data": {"operacao": "b"},
                            "style": "destructive",
                            "okmigoIcone": "delete",
                            "mode": "secondary",
                        },
                        {
                            "type": "Action.Submit",
                            "title": "C",
                            "data": {"operacao": "c"},
                            "mode": "secondary",
                        },
                        {
                            "type": "Action.Submit",
                            "title": "D",
                            "data": {"operacao": "d"},
                            "style": "verde",
                        },
                    ],
                }
            )
        )
        self.assertEqual(
            [b["enfase"] for b in tela["corpo"][0]["botoes"]],
            ["primaria", "destrutiva", "discreta", "padrao"],
        )
        self.assertEqual(tela["corpo"][0]["botoes"][1]["icone"], "lixeira")

    def test_submit_escopa_os_ids_da_propria_caixa(self):
        tela, _ = validar(
            cartao(
                {
                    "type": "Container",
                    "items": [
                        {"type": "Input.Text", "id": "quando_c30", "campo": "quando"},
                        {
                            "type": "ActionSet",
                            "actions": [
                                {
                                    "type": "Action.Submit",
                                    "title": "S",
                                    "data": {"operacao": "op"},
                                }
                            ],
                        },
                    ],
                },
                {
                    "type": "Container",
                    "items": [
                        {"type": "Input.Text", "id": "quando_c31", "campo": "quando"},
                        {
                            "type": "ActionSet",
                            "actions": [
                                {
                                    "type": "Action.Submit",
                                    "title": "S",
                                    "data": {"operacao": "op"},
                                }
                            ],
                        },
                    ],
                },
            )
        )
        self.assertEqual(
            tela["corpo"][0]["itens"][1]["botoes"][0]["campos"], ["quando_c30"]
        )
        self.assertEqual(
            tela["corpo"][1]["itens"][1]["botoes"][0]["campos"], ["quando_c31"]
        )

    def test_caixa_que_perdeu_obrigatorio_perde_os_botoes(self):
        tela, _ = validar(
            cartao(
                {
                    "type": "Container",
                    "items": [
                        {
                            "type": "Input.ChoiceSet",
                            "id": "motivo",
                            "isRequired": True,
                            "choices": [],
                        },
                        {
                            "type": "ActionSet",
                            "actions": [
                                {
                                    "type": "Action.Submit",
                                    "title": "Aceitar",
                                    "data": {"operacao": "op"},
                                }
                            ],
                        },
                    ],
                }
            )
        )
        self.assertEqual([i["tipo"] for i in tela["corpo"][0]["itens"]], [])
        tela, _ = validar(
            cartao(
                {
                    "type": "Container",
                    "items": [
                        {
                            "type": "Input.ChoiceSet",
                            "id": "motivo",
                            "isRequired": True,
                            "choices": [{"title": "A", "value": "a"}],
                        },
                        {
                            "type": "ActionSet",
                            "actions": [
                                {
                                    "type": "Action.Submit",
                                    "title": "Aceitar",
                                    "data": {"operacao": "op"},
                                }
                            ],
                        },
                    ],
                }
            )
        )
        self.assertEqual(
            [i["tipo"] for i in tela["corpo"][0]["itens"]], ["escolha", "acoes"]
        )


class LeituraInterativaTest(unittest.TestCase):
    def test_execute_usa_leitura_e_escopa_os_campos_da_caixa(self):
        tela, erro = validar(
            cartao(
                {
                    "type": "Container",
                    "items": [
                        {
                            "type": "Input.Text",
                            "id": "ticker",
                            "campo": "ticker",
                            "isRequired": True,
                        },
                        {
                            "type": "ActionSet",
                            "actions": [
                                {
                                    "type": "Action.Execute",
                                    "title": "Buscar",
                                    "data": {"operacao": "detalhar_ativo"},
                                    "style": "positive",
                                }
                            ],
                        },
                    ],
                }
            ),
            leituras={"detalhar_ativo"},
        )

        self.assertIsNone(erro)
        self.assertEqual(
            tela["corpo"][0]["itens"][1]["botoes"],
            [
                {
                    "titulo": "Buscar",
                    "consultar": "detalhar_ativo",
                    "enfase": "primaria",
                    "campos": ["ticker"],
                }
            ],
        )

    def test_execute_fora_das_leituras_recusa_a_tela(self):
        tela, erro = validar(
            cartao(
                {
                    "type": "ActionSet",
                    "actions": [
                        {
                            "type": "Action.Execute",
                            "title": "Buscar",
                            "data": {"operacao": "apagar"},
                        }
                    ],
                }
            ),
            leituras={"detalhar_ativo"},
        )

        self.assertIsNone(tela)
        self.assertIn("apagar", erro)
        self.assertIn("leitura", erro)


class ConfigTest(unittest.TestCase):
    NOSSA = Config(
        dominios=("exemplo.com", "cdn.exemplo.net"),
        base_de_imagens="https://exemplo.com/",
    )

    def test_imagem_so_do_dominio_configurado_e_absoluta(self):
        for url, esperado in [
            ("/img/abc", "https://exemplo.com/img/abc"),
            ("https://exemplo.com/x.png", "https://exemplo.com/x.png"),
            ("https://fit.exemplo.com/x.png", "https://fit.exemplo.com/x.png"),
            ("https://cdn.exemplo.net/x.png", "https://cdn.exemplo.net/x.png"),
        ]:
            with self.subTest(url=url):
                tela, _ = validar(
                    cartao({"type": "Image", "url": url}), config=self.NOSSA
                )
                self.assertEqual(
                    (tela["corpo"][0]["tipo"], tela["corpo"][0]["url"]),
                    ("imagem", esperado),
                )
        for url in [
            "https://outro.com/x.png",
            "http://exemplo.com/x.png",
            "https://exemplo.com.br/x.png",
            "https://mau.example@exemplo.com/x",
            "https://exemplo.com:8443/x.png",
            "",
        ]:
            with self.subTest(url=url):
                tela, _ = validar(
                    cartao({"type": "Image", "url": url, "altText": "foto"}),
                    config=self.NOSSA,
                )
                self.assertEqual(tela["corpo"][0]["tipo"], "sem_imagem")

    def test_sem_config_nenhum_dominio_e_nosso(self):
        tela, _ = validar(cartao({"type": "Image", "url": "https://exemplo.com/x.png"}))
        self.assertEqual(tela["corpo"][0]["tipo"], "sem_imagem")

    def test_autorizar_recusa_o_proprio_dominio_e_aceita_terceiro(self):
        def aut(url):
            tela, _ = validar(
                cartao(
                    {
                        "type": "okmigoAutorizar",
                        "url": url,
                        "rotulo": "Autorizar",
                        "motivo": "ler sua conta",
                    },
                    {"type": "TextBlock", "text": "x"},
                ),
                config=self.NOSSA,
            )
            return [n["tipo"] for n in tela["corpo"]]

        self.assertEqual(
            aut("https://banco.com.br/autorizar?t=abc"), ["autorizar", "texto"]
        )
        for ruim in [
            "https://exemplo.com/autorizar",
            "https://app.exemplo.com/a",
            "http://banco.com.br/a",
            "https://banco.com.br@mau.example/a",
            "https://10.0.0.1/a",
            "https://banco.com.br:8080/a",
            "javascript:alert(1)",
            "https://" + "a" * 3000,
        ]:
            with self.subTest(ruim=ruim):
                self.assertEqual(aut(ruim), ["texto"])

    def test_autorizar_e_um_por_cartao(self):
        tela, _ = validar(
            cartao(
                {
                    "type": "okmigoAutorizar",
                    "url": "https://b1.com/a",
                    "rotulo": "1",
                    "motivo": "m",
                },
                {
                    "type": "okmigoAutorizar",
                    "url": "https://b2.com/a",
                    "rotulo": "2",
                    "motivo": "m",
                },
            )
        )
        self.assertEqual([n["onde"] for n in tela["corpo"]], ["b1.com"])

    def test_anexo_so_aperta_o_teto(self):
        cfg = Config(anexo_max_bytes=1000)
        for declarado, esperado in [
            (None, 1000),
            (500, 500),
            (5000, 1000),
            (0, 1000),
            (-1, 1000),
        ]:
            with self.subTest(declarado=declarado):
                no = (
                    {"type": "okmigoArquivo", "id": "f", "maxBytes": declarado}
                    if declarado is not None
                    else {"type": "okmigoArquivo", "id": "f"}
                )
                tela, _ = validar(cartao(no), config=cfg)
                self.assertEqual(tela["corpo"][0]["max_bytes"], esperado)

    def test_config_nao_vaza_entre_chamadas(self):
        validar(cartao({"type": "Image", "url": "/img/a"}), config=self.NOSSA)
        tela, _ = validar(cartao({"type": "Image", "url": "/img/a"}))
        self.assertEqual(tela["corpo"][0]["url"], "/img/a")


class VocabularioTest(unittest.TestCase):
    def test_palavras_fora_da_lista_caem_no_padrao_nunca_passam(self):
        tela, _ = validar(
            cartao(
                {
                    "type": "TextBlock",
                    "text": "t",
                    "size": "gigante",
                    "weight": "pesado",
                    "color": "attention",
                    "horizontalAlignment": "diagonal",
                }
            )
        )
        t = tela["corpo"][0]
        self.assertEqual(
            (t["tamanho"], t["peso"], t["alinhamento"]), ("default", "default", "left")
        )
        self.assertNotIn("color", t)
        self.assertNotIn("cor", t)

    def test_numero_e_um_tipo_e_texto_e_outro(self):
        tela, _ = validar(
            cartao(
                {"type": "Input.Number", "id": "preco", "min": 0},
                {
                    "type": "Input.Text",
                    "id": "obs",
                    "isMultiline": True,
                    "maxLength": 9999,
                },
            )
        )
        self.assertEqual(tela["corpo"][0]["formato"], "numero")
        self.assertEqual(
            (tela["corpo"][1]["linhas"], tela["corpo"][1]["max"]), (4, 400)
        )

    def test_o_valor_numerico_do_campo_nao_ganha_ponto_zero(self):
        """OMINFRA-1016: o simulador abria com «10000.0», «500.0», «24.0» —
        o SDK manda `float` e `str(10000.0)` escreve o «.0»."""
        def valor(v):
            tela, _ = validar(cartao({"type": "Input.Number", "id": "n", "value": v}))
            return tela["corpo"][0]["valor"]
        self.assertEqual(valor(10000.0), "10000")
        self.assertEqual(valor(500), "500")
        self.assertEqual(valor(24.0), "24")
        # fracionário fica com PONTO: é o que os dois clientes leem de volta
        self.assertEqual(valor(13.65), "13.65")
        self.assertEqual(valor(0.1), "0.1")
        # o texto, o booleano e o que não é finito seguem como antes
        self.assertEqual(valor("10000.0"), "10000.0")
        self.assertEqual(valor(True), "True")
        self.assertEqual(valor(float("nan")), "")
        self.assertEqual(valor(None), "")

    def test_input_sem_id_some(self):
        tela, erro = validar(
            cartao({"type": "Input.Text"}, {"type": "TextBlock", "text": "x"})
        )
        self.assertEqual([n["tipo"] for n in tela["corpo"]], ["texto"])

    def test_choiceset_tres_formas_e_a_trava_do_estrito(self):
        base = {
            "type": "Input.ChoiceSet",
            "id": "h",
            "value": "fora",
            "choices": [
                {
                    "title": "Nove",
                    "value": "09:00",
                    "okmigoNota": "cedo",
                    "okmigoIcone": "🌅",
                }
            ],
        }
        lista, _ = validar(cartao(base))
        fichas, _ = validar(cartao({**base, "style": "expanded"}))
        livre, _ = validar(cartao({**base, "style": "filtered"}))
        busca, _ = validar(cartao({**base, "style": "filtered", "okmigoEstrito": True}))
        self.assertEqual(
            (
                lista["corpo"][0]["tipo"],
                lista["corpo"][0]["forma"],
                lista["corpo"][0]["valor"],
            ),
            ("escolha", "lista", ""),
        )
        self.assertEqual(fichas["corpo"][0]["forma"], "cartoes")
        self.assertEqual(fichas["corpo"][0]["opcoes"][0]["nota"], "cedo")
        self.assertEqual(
            (livre["corpo"][0]["tipo"], livre["corpo"][0]["valor"]),
            ("escolha_livre", "fora"),
        )
        self.assertEqual(
            (busca["corpo"][0]["tipo"], busca["corpo"][0]["forma"]),
            ("escolha", "busca"),
        )

    def test_autocomplete_so_usa_operacao_de_leitura_declarada(self):
        no = {
            "type": "Input.ChoiceSet",
            "id": "ticker",
            "style": "filtered",
            "okmigoBuscar": "buscar_ativos",
            "choices": [],
        }
        tela, erro = validar(cartao(no), leituras={"buscar_ativos"})
        self.assertIsNone(erro)
        self.assertEqual(tela["corpo"][0]["buscar"], "buscar_ativos")

        tela, erro = validar(cartao(no), leituras={"outra"})
        self.assertIsNone(tela)
        self.assertIn("não é uma operação de leitura", erro)

    def test_fallback_vale_para_toda_queda_nao_so_para_tipo_desconhecido(self):
        """⛔ O caso real: a tabela do dia sem agendamento nenhum.

        A queda mais comum desta plataforma não é «não conheço esse tipo» — é
        «o elemento veio vazio». Até 11/09 o `fallback` só era consultado no
        tipo desconhecido, então um negócio sem movimento abria a tela sem a
        tabela E sem a frase que o autor tinha escrito para o vazio.
        """
        ancora = {"type": "TextBlock", "text": "ancora"}
        aviso = {"type": "TextBlock", "text": "NADA MARCADO"}
        so_cabecalho = {
            "type": "Table",
            "columns": [{"width": 1}],
            "firstRowAsHeader": True,
            "rows": [
                {
                    "type": "TableRow",
                    "cells": [
                        {
                            "type": "TableCell",
                            "items": [{"type": "TextBlock", "text": "Quem"}],
                        }
                    ],
                }
            ],
        }

        def tem_aviso(bloco):
            tela, _ = validar(cartao(ancora, bloco))
            return "NADA MARCADO" in json.dumps(tela or {}, ensure_ascii=False)

        # POSITIVOS — as quedas que antes sumiam caladas
        self.assertTrue(tem_aviso({**so_cabecalho, "fallback": aviso}))
        self.assertTrue(
            tem_aviso(
                {"type": "Input.ChoiceSet", "id": "x", "choices": [], "fallback": aviso}
            )
        )
        self.assertTrue(
            tem_aviso(
                {
                    "type": "ActionSet",
                    "fallback": aviso,
                    "actions": [
                        {"type": "Action.OpenUrl", "title": "x", "url": "https://a.b"}
                    ],
                }
            )
        )
        # e o que já valia antes continua valendo
        self.assertTrue(tem_aviso({"type": "Carousel", "fallback": aviso}))

        # ⛔ NEGATIVO 1: com dado, o fallback NÃO aparece — senão a tela teria
        # a tabela e o aviso de vazio ao mesmo tempo.
        self.assertFalse(
            tem_aviso(
                {**so_cabecalho, "fallback": aviso, "rows": so_cabecalho["rows"] * 2}
            )
        )

        # ⛔ NEGATIVO 2: sem `fallback`, continua sumindo. A dica é do autor;
        # não inventamos texto para o vazio de ninguém.
        self.assertFalse(tem_aviso(dict(so_cabecalho)))

        # ⛔ NEGATIVO 3: o fallback NÃO é atalho para dentro — ele volta pelo
        # mesmo crivo, e um proibido cai igual.
        tela, _ = validar(
            cartao(
                ancora,
                {
                    "type": "Carousel",
                    "fallback": {
                        "type": "ActionSet",
                        "actions": [
                            {
                                "type": "Action.OpenUrl",
                                "title": "sair",
                                "url": "https://fora.test",
                            }
                        ],
                    },
                },
            )
        )
        self.assertNotIn("OpenUrl", json.dumps(tela or {}))
        self.assertNotIn("fora.test", json.dumps(tela or {}))

    def test_quem_opera_e_buraco_que_o_produto_preenche(self):
        """`okmigoQuemOpera`: as opções são de quem HOSPEDA, não do autor.

        ⛔ O caso que a pediu: uma agenda precisa saber quem atende, e a
        alternativa obrigaria o serviço a conhecer o quadro de pessoal do
        cliente dele. Com a dica ele declara o buraco e recebe, no Submit,
        apenas o nome escolhido.
        """
        base = {
            "type": "Input.ChoiceSet",
            "id": "prof",
            "campo": "nome",
            "label": "Quem atende",
            "style": "expanded",
        }

        # POSITIVO: marcado, e a lista vazia NÃO derruba o campo
        tela, _ = validar(cartao({**base, "okmigoQuemOpera": True}))
        self.assertEqual(tela["corpo"][0]["tipo"], "escolha")
        self.assertIs(tela["corpo"][0]["quem_opera"], True)
        self.assertEqual(tela["corpo"][0]["opcoes"], [])

        # POSITIVO: as `choices` do autor são IGNORADAS — senão a tela
        # ofereceria gente que não opera ao lado de gente que opera.
        tela, _ = validar(
            cartao(
                {
                    **base,
                    "okmigoQuemOpera": True,
                    "choices": [{"title": "Estranho", "value": "x"}],
                }
            )
        )
        self.assertEqual(tela["corpo"][0]["opcoes"], [])

        # POSITIVO: força o ESTRITO. Livre seria um campo de texto com sugestão.
        tela, _ = validar(
            cartao({**base, "style": "filtered", "okmigoQuemOpera": True})
        )
        self.assertEqual(
            (tela["corpo"][0]["tipo"], tela["corpo"][0]["forma"]), ("escolha", "busca")
        )

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
        so_cabecalho = {
            "type": "Table",
            "columns": [{"width": 1}],
            "rows": [
                {
                    "type": "TableRow",
                    "cells": [
                        {
                            "type": "TableCell",
                            "items": [{"type": "TextBlock", "text": "Nome"}],
                        }
                    ],
                }
            ],
        }
        tela, erro = validar(cartao(so_cabecalho))
        self.assertIsNone(tela)
        com_dado = {**so_cabecalho, "rows": so_cabecalho["rows"] * 2}
        tela, _ = validar(cartao(com_dado))
        self.assertEqual(
            (tela["corpo"][0]["tipo"], len(tela["corpo"][0]["linhas"])), ("tabela", 2)
        )

    def test_linha_de_tabela_pode_abrir_uma_consulta_sem_escrever(self):
        cabecalho = {
            "type": "TableRow",
            "cells": [
                {
                    "type": "TableCell",
                    "items": [{"type": "TextBlock", "text": "Ativo"}],
                }
            ],
        }
        dado = {
            "type": "TableRow",
            "selectAction": {
                "type": "Action.Execute",
                "title": "Ver PETR4",
                "data": {"operacao": "detalhar_ativo"},
            },
            "cells": [
                {
                    "type": "TableCell",
                    "items": [
                        {
                            "type": "Input.Text",
                            "id": "ticker_petr4",
                            "campo": "ticker",
                            "value": "PETR4",
                            "isVisible": False,
                        },
                        {"type": "TextBlock", "text": "PETR4"},
                    ],
                }
            ],
        }

        tela, erro = validar(
            cartao(
                {
                    "type": "Table",
                    "columns": [{"width": 1}],
                    "rows": [cabecalho, dado],
                }
            ),
            leituras={"detalhar_ativo"},
        )

        self.assertIsNone(erro)
        self.assertEqual(
            tela["corpo"][0]["linhas"][1]["acao"],
            {
                "titulo": "Ver PETR4",
                "consultar": "detalhar_ativo",
                "enfase": "padrao",
                "campos": ["ticker_petr4"],
            },
        )

        tela, erro = validar(
            cartao(
                {
                    "type": "Table",
                    "columns": [{"width": 1}],
                    "rows": [cabecalho, dado],
                }
            ),
            leituras={"outra_operacao"},
        )
        self.assertIsNone(tela)
        self.assertIn("detalhar_ativo", erro)

    def test_grafico_aceita_numero_cru_e_formatado_e_recusa_nan(self):
        tela, _ = validar(
            cartao(
                {
                    "type": "okmigoGrafico",
                    "series": [{"rotulo": "S"}],
                    "pontos": [
                        {"rotulo": "a", "valores": [1200]},
                        {"rotulo": "b", "valores": ["1.200,50"]},
                        {"rotulo": "c", "valores": ["nan"]},
                        {"rotulo": "d", "valores": ["x"]},
                    ],
                }
            )
        )
        self.assertEqual(
            [p["valores"] for p in tela["corpo"][0]["pontos"]], [[1200.0], [1200.5]]
        )

    def test_progresso_prensa_feito_e_recusa_de_invalido(self):
        tela, _ = validar(
            cartao(
                {"type": "okmigoProgresso", "feito": 9, "de": 6},
                {"type": "okmigoProgresso", "feito": 1, "de": 0},
                {"type": "okmigoProgresso", "feito": -3, "de": 6},
            )
        )
        self.assertEqual(
            [(n["feito"], n["de"]) for n in tela["corpo"]], [(6, 6), (0, 6)]
        )

    def test_cronometro_dentro_da_faixa(self):
        tela, _ = validar(
            cartao(
                {"type": "okmigoCronometro", "rotulo": "Descanso", "segundos": 90},
                {"type": "okmigoCronometro", "rotulo": "x", "segundos": 0},
                {"type": "okmigoCronometro", "rotulo": "x", "segundos": 99999},
                {"type": "okmigoCronometro", "segundos": 30},
            )
        )
        self.assertEqual([n["segundos"] for n in tela["corpo"]], [90])

    def test_documento_fora_das_leituras_recusa_a_tela(self):
        doc = {
            "type": "okmigoDocumento",
            "titulo": "Nota",
            "ler": {"operacao": "baixar", "pedido": {"id": 7, "x": {"n": 1}}},
        }
        tela, erro = validar(cartao(doc), leituras={"outra"})
        self.assertIsNone(tela)
        self.assertIn("baixar", erro)
        tela, erro = validar(cartao(doc), leituras={"baixar"})
        self.assertEqual(
            tela["corpo"][0]["ler"], {"operacao": "baixar", "pedido": {"id": 7}}
        )

    def test_grade_quatro_intencoes(self):
        for dica, esperado in [
            (True, True),
            ("larga", "larga"),
            ("compacta", "compacta"),
            ("etiquetas", "etiquetas"),
            ("gigante", True),
            (None, False),
        ]:
            with self.subTest(dica=dica):
                no = {
                    "type": "Container",
                    "items": [{"type": "TextBlock", "text": "x"}],
                }
                if dica is not None:
                    no["okmigoGrade"] = dica
                tela, _ = validar(cartao(no))
                self.assertEqual(tela["corpo"][0]["grade"], esperado)


if __name__ == "__main__":
    unittest.main()


class OpcaoComImagemTest(unittest.TestCase):
    """A FOTO de uma opção em cartões (OMINFRA-559).

    ⛔ O `icone` é um glifo — um emoji. Há escolha em que a imagem É o
    conteúdo: uma grade de áreas de treino em que cada tile mostra o
    exercício-símbolo. O alvo (Leap «Treino em casa») mostra a foto; nós
    tínhamos 866 demonstrações hospedadas e o tile só conseguia mostrar emoji.
    """

    NOSSA = Config(
        dominios=("exemplo.com", "cdn.exemplo.net"),
        base_de_imagens="https://exemplo.com/",
    )

    def _opcao(self, imagem, style="expanded"):
        tela, _ = validar(
            cartao({
                "type": "Input.ChoiceSet", "id": "area", "style": style,
                "choices": [{"title": "Peito", "value": "peito",
                             "okmigoNota": "3 exercícios", "okmigoIcone": "💪",
                             "okmigoImagem": imagem}],
            }),
            config=self.NOSSA,
        )
        return tela["corpo"][0]["opcoes"][0]

    def test_a_foto_da_casa_atravessa_absoluta(self):
        self.assertEqual(self._opcao("/img/peito")["imagem"],
                         "https://exemplo.com/img/peito")
        self.assertEqual(self._opcao("https://cdn.exemplo.net/p.png")["imagem"],
                         "https://cdn.exemplo.net/p.png")

    def test_foto_de_terceiro_e_recusada_e_o_campo_some(self):
        """⛔ A mesma regra de toda imagem do cartão: uma foto servida pelo
        terceiro faria o aparelho de cada pessoa bater no servidor dele."""
        for url in ("https://outro.com/p.png", "http://exemplo.com/p.png",
                    "https://exemplo.com.br/p.png", "https://mau.example@exemplo.com/p"):
            with self.subTest(url=url):
                self.assertNotIn("imagem", self._opcao(url))

    def test_o_glifo_continua_valendo_quando_nao_ha_foto(self):
        """A imagem ACRESCENTA, não substitui: cliente sem foto tem o ícone."""
        opcao = self._opcao("")
        self.assertNotIn("imagem", opcao)
        self.assertEqual(opcao["icone"], "💪")

    def test_a_foto_vale_em_qualquer_forma_de_escolha(self):
        """Quem desenha é o cliente; o crivo não decide forma por causa dela."""
        for forma in ("expanded", None, "filtered"):
            with self.subTest(forma=forma):
                opcao = self._opcao("/img/peito", style=forma)
                self.assertEqual(opcao.get("imagem"), "https://exemplo.com/img/peito")


class DiaInteiroNoCalendarioTest(unittest.TestCase):
    """OMINFRA-937: o evento SÓ com data. Até aqui o evento do calendário só
    sabia dizer «começa às», e um feriado tinha de inventar uma hora. O caso
    negativo fica ao lado de cada positivo: o mesmo evento, sem o campo, tem
    de sobreviver — o que recusa é a MISTURA de dia inteiro com hora."""

    def _eventos(self, *eventos):
        tela, erro = validar(cartao({
            "type": "okmigoCalendario",
            "vista": "mes",
            "de": "2026-10-01",
            "eventos": list(eventos),
        }))
        self.assertIsNone(erro)
        return tela["corpo"][0]["eventos"]

    def test_dia_inteiro_so_com_data_passa_e_sai_marcado(self):
        [ev] = self._eventos({"inicio": "2026-10-12", "titulo": "Feriado", "dia_inteiro": True})
        self.assertEqual((ev["inicio"], ev["fim"], ev["dia_inteiro"]), ("2026-10-12", "", True))

    def test_dia_inteiro_de_varios_dias_guarda_o_fim_inclusivo(self):
        [ev] = self._eventos({
            "inicio": "2026-10-05", "fim": "2026-10-07", "titulo": "Férias",
            "dia_inteiro": True, "id": "f1",
        })
        self.assertEqual((ev["inicio"], ev["fim"], ev["dia_inteiro"], ev["id"]),
                         ("2026-10-05", "2026-10-07", True, "f1"))

    def test_dia_inteiro_com_hora_e_descartado(self):
        com_hora = {"inicio": "2026-10-12T10:00:00-03:00", "titulo": "Feriado"}
        # O MESMO evento sem o campo sobrevive: é o negativo que prova o positivo.
        self.assertEqual(len(self._eventos(com_hora)), 1)
        self.assertEqual(self._eventos({**com_hora, "dia_inteiro": True}), [])
        # Hora no `fim` é a mesma mistura.
        self.assertEqual(self._eventos({
            "inicio": "2026-10-12", "fim": "2026-10-12T18:00", "titulo": "x", "dia_inteiro": True,
        }), [])
        # E um dia que não existe cai pela mesma porta.
        self.assertEqual(self._eventos({"inicio": "2026-02-30", "titulo": "x", "dia_inteiro": True}), [])

    def test_so_o_evento_errado_cai_e_os_vizinhos_ficam(self):
        eventos = self._eventos(
            {"inicio": "2026-10-12", "titulo": "Feriado", "dia_inteiro": True},
            {"inicio": "2026-10-12T10:00", "titulo": "Errado", "dia_inteiro": True},
            {"inicio": "2026-10-13T09:00:00-03:00", "fim": "2026-10-13T09:30:00-03:00", "titulo": "Consulta"},
        )
        self.assertEqual([e["titulo"] for e in eventos], ["Feriado", "Consulta"])
        self.assertEqual([e["dia_inteiro"] for e in eventos], [True, False])

    def test_evento_com_hora_segue_igual_e_sem_o_campo_sai_falso(self):
        [ev] = self._eventos({
            "inicio": "2026-10-13T09:00:00-03:00", "fim": "2026-10-13T09:30:00-03:00",
            "titulo": "Consulta", "detalhe": "Sala 2", "id": "c1", "tipo": "atendimento",
        })
        self.assertEqual(ev, {
            "inicio": "2026-10-13T09:00:00-03:00", "fim": "2026-10-13T09:30:00-03:00",
            "dia_inteiro": False, "titulo": "Consulta", "detalhe": "Sala 2",
            "recurso": "", "id": "c1", "tipo": "atendimento",
        })

    def test_dia_inteiro_e_booleano_literal_nunca_texto(self):
        # A expansão do molde entrega TEXTO: `"{dia_inteiro}"` vira `"True"`,
        # que não é `true`. Texto não liga o campo — e, com hora, o evento
        # fica, porque sem o campo ele é um evento de hora como qualquer outro.
        for valor in ("true", "True", "sim", 1):
            with self.subTest(valor=valor):
                [ev] = self._eventos({"inicio": "2026-10-12T10:00", "titulo": "x", "dia_inteiro": valor})
                self.assertFalse(ev["dia_inteiro"])

    def test_fim_antes_do_inicio_cai_para_um_dia(self):
        [ev] = self._eventos({"inicio": "2026-10-07", "fim": "2026-10-05", "titulo": "x", "dia_inteiro": True})
        self.assertEqual((ev["inicio"], ev["fim"], ev["dia_inteiro"]), ("2026-10-07", "", True))

    def test_no_molde_o_dia_inteiro_se_separa_por_quando(self):
        """O caminho documentado: duas repetições, uma por forma. Prova a
        travessia molde → expansão → crivo, não só o crivo."""
        from okmigo_cartao import expandir

        molde = cartao({"type": "okmigoCalendario", "vista": "mes", "eventos": [
            {"_repetir_lista": {"inicio": "{dia}", "titulo": "{titulo}", "dia_inteiro": True},
             "_quando": {"campo": "forma", "em": ["dia_inteiro"]}},
            {"_repetir_lista": {"inicio": "{inicio}", "fim": "{fim}", "titulo": "{titulo}"},
             "_quando": {"campo": "forma", "em": ["com_hora"]}},
        ]})
        linhas = [
            {"forma": "dia_inteiro", "dia": "2026-10-12", "titulo": "Feriado"},
            {"forma": "com_hora", "inicio": "2026-10-13T09:00", "fim": "2026-10-13T09:30", "titulo": "Consulta"},
        ]
        tela, erro = validar(expandir(molde, {}, linhas))
        self.assertIsNone(erro)
        eventos = tela["corpo"][0]["eventos"]
        self.assertEqual([(e["titulo"], e["dia_inteiro"], e["inicio"]) for e in eventos],
                         [("Feriado", True, "2026-10-12"), ("Consulta", False, "2026-10-13T09:00")])

    def test_casca_descreve_o_dia_inteiro_e_o_relatorio_diz_por_que_sumiu(self):
        from okmigo_cartao import casca, relatorio

        bruto = cartao({"type": "okmigoCalendario", "vista": "semana", "de": "2026-10-12", "eventos": [
            {"inicio": "2026-10-12", "titulo": "Feriado", "dia_inteiro": True},
            {"inicio": "2026-10-13T10:00", "titulo": "Errado", "dia_inteiro": True},
            {"inicio": "2026-10-14T09:00", "fim": "2026-10-14T09:30", "titulo": "Consulta"},
            {"inicio": "2026-10-16", "fim": "2026-10-15", "titulo": "Invertido", "dia_inteiro": True},
        ]})
        tela, erro = validar(bruto)
        documento = casca(tela)
        self.assertIn("<time>2026-10-12</time> (dia inteiro) Feriado", documento)
        self.assertIn("<time>2026-10-14T09:00</time> – 2026-10-14T09:30 Consulta", documento)
        self.assertNotIn("(dia inteiro) Consulta", documento)
        self.assertNotIn("Errado", documento)

        linhas = relatorio(bruto, tela, erro)
        comido = [l for l in linhas if "eventos[1]" in l]
        self.assertEqual(len(comido), 1, linhas)
        self.assertIn("dia inteiro", comido[0])
        self.assertIn("some", comido[0])
        self.assertTrue(any("eventos[3]" in l and "um dia" in l for l in linhas), linhas)
        # O que sobreviveu não é acusado.
        self.assertFalse(any("eventos[0]" in l or "eventos[2]" in l for l in linhas), linhas)


class RecursoNoEventoTest(unittest.TestCase):
    """OMINFRA-942: a cadeira, a sala, o profissional — o evento diz a que
    recurso pertence, e o elemento lista os recursos que o filtro oferece.
    O negativo ao lado: recurso vazio ou longo SOME, e o evento FICA."""

    def _calendario(self, eventos, **extra):
        tela, erro = validar(cartao({
            "type": "okmigoCalendario", "vista": "dia", "de": "2026-10-13",
            "eventos": eventos, **extra,
        }))
        self.assertIsNone(erro)
        return tela["corpo"][0]

    def test_evento_com_recurso_passa_e_sai_com_o_nome(self):
        [ev] = self._calendario([{
            "inicio": "2026-10-13T09:00", "titulo": "Corte", "recurso": "  Cadeira   2 ", "id": "a7",
        }])["eventos"]
        self.assertEqual(ev["recurso"], "Cadeira 2")
        self.assertEqual((ev["titulo"], ev["id"]), ("Corte", "a7"))

    def test_evento_sem_recurso_segue_igual_e_sai_vazio(self):
        [ev] = self._calendario([{"inicio": "2026-10-13T09:00", "titulo": "Corte"}])["eventos"]
        self.assertEqual(ev["recurso"], "")
        self.assertEqual(ev["titulo"], "Corte")

    def test_recurso_vazio_ou_longo_some_e_o_evento_fica(self):
        no_teto, acima = "x" * 60, "x" * 61
        eventos = self._calendario([
            {"inicio": "2026-10-13T09:00", "titulo": "Vazio", "recurso": "   "},
            {"inicio": "2026-10-13T10:00", "titulo": "Longo", "recurso": acima},
            {"inicio": "2026-10-13T11:00", "titulo": "No teto", "recurso": no_teto},
        ])["eventos"]
        # Os três ficam — o que some é o CAMPO, e sem cortar.
        self.assertEqual([(e["titulo"], e["recurso"]) for e in eventos],
                         [("Vazio", ""), ("Longo", ""), ("No teto", no_teto)])

    def test_recursos_do_elemento_lista_sem_repetir_e_sem_o_que_nao_e_nome(self):
        calendario = self._calendario([], recursos=[
            "Cadeira 1", " Cadeira  1", "", "x" * 61, None, "Cadeira 2", 3,
        ])
        self.assertEqual(calendario["recursos"], ["Cadeira 1", "Cadeira 2", "3"])
        # Sem o campo: lista vazia, e o resto do elemento como antes.
        self.assertEqual(self._calendario([])["recursos"], [])
        # Texto no lugar da lista NÃO vira uma letra por recurso.
        self.assertEqual(self._calendario([], recursos="Cadeira 1")["recursos"], [])

    def test_recursos_respeita_o_teto_de_uma_escolha(self):
        calendario = self._calendario([], recursos=[f"Sala {i}" for i in range(70)])
        self.assertEqual(len(calendario["recursos"]), 60)
        self.assertEqual(calendario["recursos"][-1], "Sala 59")

    def test_casca_descreve_o_recurso_e_o_relatorio_diz_o_que_sumiu(self):
        from okmigo_cartao import casca, relatorio

        bruto = cartao({"type": "okmigoCalendario", "vista": "dia", "de": "2026-10-13",
                        "recursos": ["Cadeira 1", "Cadeira 2", "Cadeira 1", ""],
                        "eventos": [
            {"inicio": "2026-10-13T09:00", "titulo": "Corte", "recurso": "Cadeira 2"},
            {"inicio": "2026-10-13T10:00", "titulo": "Barba", "recurso": "y" * 61},
            {"inicio": "2026-10-13T11:00", "titulo": "Solto"},
        ]})
        tela, erro = validar(bruto)
        documento = casca(tela)
        self.assertIn("Corte <small>recurso: Cadeira 2</small>", documento)
        self.assertIn("<small>recursos: Cadeira 1, Cadeira 2</small>", documento)
        self.assertIn("Barba</li>", documento)       # o evento ficou, sem o rótulo
        self.assertNotIn("y" * 61, documento)

        linhas = relatorio(bruto, tela, erro)
        self.assertTrue(any("eventos[1]" in l and "61 caracteres" in l and "o evento fica" in l for l in linhas), linhas)
        self.assertTrue(any("recursos[2]" in l and "repetido" in l for l in linhas), linhas)
        self.assertTrue(any("recursos[3]" in l and "vazio" in l for l in linhas), linhas)
        self.assertFalse(any("eventos[0]" in l or "eventos[2]" in l for l in linhas), linhas)
