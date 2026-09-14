import hashlib
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
ALVO = str(RAIZ / "exemplos" / "sdk_catalogo.py") + ":FORMULARIO"


class PreviewTest(unittest.TestCase):
    def test_bundle_empacotado_corresponde_aos_hashes_exportados(self):
        ativos = RAIZ / "src" / "okmigo_cartao" / "assets"
        metadados = json.loads((ativos / "renderer.json").read_text(encoding="utf-8"))

        for nome in ("renderer.js", "renderer.css"):
            digest = hashlib.sha256((ativos / nome).read_bytes()).hexdigest()
            self.assertEqual(metadados[f"{nome.replace('.', '_')}_sha256"], digest)

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

    def test_menu_mais_preserva_todos_os_destinos(self):
        superficies = [
            {
                "nome": f"tela-{indice}",
                "rotulo": f"Tela {indice}",
                "icone": "inicio",
                "tela": {"corpo": []},
            }
            for indice in range(7)
        ]
        html = pagina_aplicativo(
            {"nome": "Grande", "atual": "tela-0", "superficies": superficies},
            "grande.py:APLICATIVO",
            frozenset(),
            frozenset(),
        )

        self.assertIn("aria-haspopup", html)
        for indice in range(7):
            self.assertEqual(html.count(f'"nome":"tela-{indice}"'), 1)
        self.assertIn("Mais", html)

    def test_compila_expande_e_confere_o_sdk(self):
        tela, escrituras, leituras = construir_tela(ALVO, None)

        self.assertEqual("jornada-ativa", tela["tema"])
        self.assertEqual({"salvar_cadastro"}, escrituras)
        self.assertEqual(set(), leituras)

        documento = pagina(tela, ALVO, escrituras, leituras)
        for esperado in (
            "Novo cadastro",
            "Prioridade",
            "Anexo opcional",
            "Desktop",
            "Celular",
            "Renderer Web oficial",
        ):
            self.assertIn(esperado, documento)
        self.assertNotIn("<script src=", documento)
        self.assertNotIn("não é o renderer de produção", documento)

    def test_aplicativo_infere_leitura_de_documento_do_catalogo(self):
        alvo = str(RAIZ / "exemplos" / "sdk_catalogo.py") + ":APLICATIVO"

        aplicativo, escrituras, leituras = construir_aplicativo(alvo, None)

        self.assertIn("baixar_extrato", leituras)
        self.assertIn("salvar_cadastro", escrituras)
        self.assertEqual(4, len(aplicativo["superficies"]))

    def test_comando_pode_gerar_html_sem_iniciar_servidor(self):
        with tempfile.TemporaryDirectory() as temporario:
            saida = Path(temporario) / "catalogo.html"
            codigo = main_preview([ALVO, "--saida", str(saida)])

            self.assertEqual(0, codigo)
            self.assertTrue(saida.is_file())
            self.assertIn("Salvar cadastro", saida.read_text(encoding="utf-8"))

    def test_manifesto_inteiro_vira_aplicativo_navegavel(self):
        cartao = carregar_alvo(ALVO)
        manifesto = {
            "slug": "catalogo",
            "nome_visivel": "Catálogo",
            "superficies": [
                {
                    "nome": "cadastro",
                    "rotulo": "Cadastro",
                    "icone": "perfil",
                    "cartao": cartao,
                },
                {
                    "nome": "revisao",
                    "rotulo": "Revisão",
                    "icone": "inicio",
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
                json.dumps({"cadastro": {}, "revisao": {}}), encoding="utf-8"
            )

            aplicativo, escrituras, leituras = construir_aplicativo(
                str(caminho_manifesto), caminho_dados
            )
            documento = pagina_aplicativo(
                aplicativo, str(caminho_manifesto), escrituras, leituras
            )

        self.assertEqual(
            ["cadastro", "revisao"],
            [s["nome"] for s in aplicativo["superficies"]],
        )
        self.assertIn('"nome":"Catálogo"', documento)
        self.assertIn('"nome":"revisao"', documento)
        self.assertIn("superficie-bottom-nav", documento)
        self.assertIn("Renderer Web oficial", documento)

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
        self.assertIn('"nome":"dados"', documento)

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

        self.assertIn('"tipo":"fatos"', documento)
        self.assertIn('"tipo":"grafico"', documento)
        self.assertIn('"cor":"positivo"', documento)
        self.assertIn('"grade":"compacta"', documento)
        self.assertIn("Renderer Web oficial", documento)

    def test_preview_desenha_escolhas_progresso_e_etapas_ocultas(self):
        aplicativo = {
            "nome": "EstouFit",
            "atual": "treino",
            "superficies": [
                {
                    "nome": "treino",
                    "rotulo": "Treino",
                    "icone": "treino",
                    "tela": {
                        "corpo": [
                            {
                                "tipo": "escolha",
                                "id": "nivel",
                                "campo": "nivel",
                                "rotulo": "Nível",
                                "forma": "cartoes",
                                "valor": "iniciante",
                                "obrigatorio": True,
                                "opcoes": [
                                    {
                                        "valor": "iniciante",
                                        "rotulo": "Iniciante",
                                        "nota": "Começando agora",
                                    },
                                    {
                                        "valor": "avancado",
                                        "rotulo": "Avançado",
                                        "nota": "Treina há anos",
                                    },
                                ],
                            },
                            {
                                "tipo": "progresso",
                                "rotulo": "Treino de hoje",
                                "feito": 2,
                                "de": 5,
                            },
                            {
                                "tipo": "caixa",
                                "id": "detalhes",
                                "visivel": False,
                                "estilo": "emphasis",
                                "itens": [{"tipo": "texto", "texto": "Detalhes"}],
                            },
                            {
                                "tipo": "acoes",
                                "botoes": [
                                    {
                                        "titulo": "Abrir detalhes",
                                        "alvos": [{"id": "detalhes", "mostrar": True}],
                                    }
                                ],
                            },
                        ]
                    },
                }
            ],
        }

        documento = pagina_aplicativo(
            aplicativo, "estoufit.py:ALUNO", frozenset(), frozenset()
        )

        self.assertIn('"tipo":"escolha"', documento)
        self.assertIn('"forma":"cartoes"', documento)
        self.assertIn('"valor":"iniciante"', documento)
        self.assertIn("Começando agora", documento)
        self.assertIn('"tipo":"progresso"', documento)
        self.assertIn('"feito":2,"de":5', documento)
        self.assertIn('"id":"detalhes","visivel":false', documento)
        self.assertIn('"alvos":[{"id":"detalhes","mostrar":true}]', documento)
        self.assertNotIn("Componente escolha validado", documento)
        self.assertNotIn("Componente progresso validado", documento)

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
        self.assertIn('"valor":"SANB11"', documento)
        self.assertIn("Ficha completa", documento)
        self.assertIn("Sem resposta de demonstração", documento)
        self.assertIn("Voltar para", documento)


if __name__ == "__main__":
    unittest.main()
