import json
import tempfile
import unittest
from pathlib import Path

from okmigo_cartao.preview import (
    carregar_alvo,
    construir_aplicativo,
    construir_tela,
    main_preview,
    pagina,
    pagina_aplicativo,
)

RAIZ = Path(__file__).resolve().parents[1]
ALVO = str(RAIZ / "exemplos" / "sdk_radaria.py") + ":tela_de_ativos"
DADOS = RAIZ / "exemplos" / "radaria.dados.json"


class PreviewTest(unittest.TestCase):
    def test_app_mantem_tela_dirigida_por_dados_navegavel_sem_fixture(self):
        with tempfile.TemporaryDirectory() as pasta:
            modulo = Path(pasta) / "app.py"
            modulo.write_text(
                "APLICATIVO = {'slug':'demo','superficies':[{'nome':'vazia','titulo':'Vazia','cartao':{'type':'AdaptiveCard','version':'1.5','okmigoNavegacao':'inferior','body':[{'type':'Table','columns':[{'width':1}],'rows':[{'_repetir_lista':{'type':'TableRow','cells':[]}}]}]}}]}\n",
                encoding="utf-8",
            )
            app, _, _ = construir_aplicativo(f"{modulo}:APLICATIVO", None)

        self.assertEqual(app["superficies"][0]["nome"], "vazia")
        self.assertIn(
            "dados de demonstração",
            str(app["superficies"][0]["tela"]["corpo"]),
        )

    def test_compila_expande_e_confere_o_sdk(self):
        tela, escrituras, leituras = construir_tela(ALVO, DADOS)

        self.assertEqual("mercado-editorial", tela["tema"])
        self.assertEqual({"adicionar_acompanhado", "remover_acompanhado"}, escrituras)
        self.assertEqual({"buscar_ativos", "detalhar_ativo"}, leituras)

        documento = pagina(tela, ALVO, escrituras, leituras)
        for esperado in (
            "Meus ativos",
            "PETR4",
            "SANB11",
            "Desktop",
            "Celular",
            'data-tema="dark"',
        ):
            self.assertIn(esperado, documento)
        self.assertNotIn("<script src=", documento)

    def test_comando_pode_gerar_html_sem_iniciar_servidor(self):
        with tempfile.TemporaryDirectory() as temporario:
            saida = Path(temporario) / "radaria.html"
            codigo = main_preview([ALVO, "--dados", str(DADOS), "--saida", str(saida)])

            self.assertEqual(0, codigo)
            self.assertTrue(saida.is_file())
            self.assertIn("SANB11", saida.read_text(encoding="utf-8"))

    def test_manifesto_inteiro_vira_aplicativo_navegavel(self):
        cartao = carregar_alvo(ALVO)
        dados = json.loads(DADOS.read_text(encoding="utf-8"))
        manifesto = {
            "slug": "radaria",
            "nome_visivel": "RadarIA",
            "superficies": [
                {
                    "nome": "ativos",
                    "rotulo": "Ativos",
                    "icone": "ativos",
                    "cartao": cartao,
                },
                {
                    "nome": "fiis",
                    "rotulo": "FIIs",
                    "icone": "fiis",
                    "cartao": cartao,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            caminho_manifesto = raiz / "manifesto.json"
            caminho_dados = raiz / "dados.json"
            caminho_manifesto.write_text(json.dumps(manifesto), encoding="utf-8")
            caminho_dados.write_text(
                json.dumps({"ativos": dados, "fiis": dados}), encoding="utf-8"
            )

            aplicativo, escrituras, leituras = construir_aplicativo(
                str(caminho_manifesto), caminho_dados
            )
            documento = pagina_aplicativo(
                aplicativo, str(caminho_manifesto), escrituras, leituras
            )

        self.assertEqual(
            ["ativos", "fiis"], [s["nome"] for s in aplicativo["superficies"]]
        )
        self.assertIn("Telas de RadarIA", documento)
        self.assertIn('data-destino="fiis"', documento)
        self.assertIn('data-tela="fiis" hidden', documento)
        self.assertIn("Tela aberta ·", documento)

    def test_aplicativo_python_vira_preview_navegavel_sem_json_de_layout(self):
        codigo = """\
from okmigo_cartao.sdk import Aplicativo, Fonte, Superficie, Tela, Texto

APLICATIVO = Aplicativo(
    slug="exemplo",
    endpoint="http://exemplo.internal/mcp/",
    para_tipo="amigo",
    descricao="Exemplo",
    descricao_humana="Exemplo navegável",
    nome_visivel="Exemplo SDK",
    versao="1.0.0",
    conversa=(),
    superficies=(
        Superficie("inicio", "Início", "Início", "radar", "resumo", Fonte("inicio"), Tela("Início", (Texto("Olá"),))),
        Superficie("dados", "Dados", "Dados", "ativos", "dados", Fonte("dados"), Tela("Dados", (Texto("Tudo em Python"),))),
    ),
)
"""
        with tempfile.TemporaryDirectory() as temporario:
            alvo_python = Path(temporario) / "aplicativo.py"
            alvo_python.write_text(codigo, encoding="utf-8")
            aplicativo, escrituras, leituras = construir_aplicativo(
                f"{alvo_python}:APLICATIVO", None
            )
            documento = pagina_aplicativo(
                aplicativo, f"{alvo_python}:APLICATIVO", escrituras, leituras
            )

        self.assertEqual(
            ["inicio", "dados"], [s["nome"] for s in aplicativo["superficies"]]
        )
        self.assertIn("Tudo em Python", documento)
        self.assertIn('data-destino="dados"', documento)

    def test_preview_desenha_fatos_grafico_e_grade(self):
        aplicativo = {
            "nome": "RadarIA",
            "atual": "detalhe",
            "superficies": [
                {
                    "nome": "detalhe",
                    "rotulo": "Detalhe",
                    "icone": "ativos",
                    "tela": {
                        "tema": "mercado-editorial",
                        "corpo": [
                            {
                                "tipo": "fatos",
                                "fatos": [{"titulo": "Preço", "valor": "R$ 35,20"}],
                            },
                            {
                                "tipo": "grafico",
                                "titulo": "Preço no período",
                                "series": [{"rotulo": "PETR4", "cor": "positivo"}],
                                "pontos": [
                                    {"rotulo": "D1", "valores": [34.8]},
                                    {"rotulo": "D2", "valores": [35.2]},
                                ],
                            },
                            {
                                "tipo": "caixa",
                                "estilo": "default",
                                "grade": "compacta",
                                "itens": [{"tipo": "texto", "texto": "P/L 6,2"}],
                            },
                        ],
                    },
                }
            ],
        }

        documento = pagina_aplicativo(
            aplicativo, "sdk.py:APLICATIVO", frozenset(), frozenset()
        )

        self.assertIn('class="fatos"', documento)
        self.assertIn('class="grafico"', documento)
        self.assertIn('class="linha-grafico tom-positivo"', documento)
        self.assertIn("caixa-grade-compacta", documento)

    def test_clique_pode_abrir_resposta_compilada_por_fabrica_python(self):
        codigo = """\
from okmigo_cartao.sdk import Acao, Acoes, Aplicativo, Fonte, Superficie, Tela, Texto

def detalhe(dados):
    return Tela(dados["ticker"], (Texto("Ficha completa"),))

APLICATIVO = Aplicativo(
    slug="exemplo",
    endpoint="http://exemplo.internal/mcp/",
    para_tipo="amigo",
    descricao="Exemplo",
    descricao_humana="Exemplo navegável",
    nome_visivel="Exemplo SDK",
    versao="1.0.0",
    conversa=("detalhar",),
    superficies=(
        Superficie(
            "ativos", "Ativos", "Ativos", "ativos", "lista", Fonte("ativos"),
            Tela("Ativos", (Acoes((Acao.consultar("Abrir", "detalhar"),)),)),
        ),
    ),
)
"""
        dados = {
            "ativos": {"resumo": {}, "linhas": []},
            "_preview": {
                "respostas": [
                    {
                        "operacao": "detalhar",
                        "fabrica": "detalhe",
                        "campo": "ticker",
                        "voltar_para": "ativos",
                        "exemplos": [{"ticker": "SANB11"}],
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            alvo_python = raiz / "aplicativo.py"
            dados_json = raiz / "dados.json"
            alvo_python.write_text(codigo, encoding="utf-8")
            dados_json.write_text(json.dumps(dados), encoding="utf-8")
            aplicativo, escrituras, leituras = construir_aplicativo(
                f"{alvo_python}:APLICATIVO", dados_json
            )
            documento = pagina_aplicativo(
                aplicativo, f"{alvo_python}:APLICATIVO", escrituras, leituras
            )

        self.assertEqual("SANB11", aplicativo["respostas"][0]["valor"])
        self.assertIn('data-valor="SANB11"', documento)
        self.assertIn("Ficha completa", documento)
        self.assertIn("abrirResposta(botao.dataset.operacao, valores)", documento)
        self.assertIn("Voltar para Ativos", documento)


if __name__ == "__main__":
    unittest.main()
