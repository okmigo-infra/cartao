"""O corpus de compatibilidade e a régua que compara duas versões do crivo.

O corpus (`tests/compat/corpus/`) é a FORMA dos cartões que os aplicativos
do ecossistema declaram hoje, anonimizada por `scripts/compatibilidade.py
--anonimizar`: estrutura, tipos, chaves do vocabulário, moldes e tetos de
comprimento iguais aos reais; todo texto, nome de campo, operação, rota e
endereço trocado por pseudônimo. A comparação entre versões roda na esteira
(`python3 scripts/compatibilidade.py`); aqui ficam três provas que não
dependem de git:

1. a árvore aceita e expande o corpus inteiro, nos cinco cenários;
2. o corpus não carrega nada que não seja vocabulário público ou pseudônimo;
3. a régua que classifica as diferenças reprova o que tem de reprovar.
"""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

from okmigo_cartao import MAX_NOS

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("compatibilidade", RAIZ / "scripts" / "compatibilidade.py")
compat = importlib.util.module_from_spec(_spec)
sys.modules["compatibilidade"] = compat
_spec.loader.exec_module(compat)

CORPUS = sorted((RAIZ / "tests" / "compat" / "corpus").glob("*.json"))


def _carregar(p):
    return json.loads(p.read_text(encoding="utf-8"))


class CorpusTest(unittest.TestCase):
    """A árvore aceita os cartões de hoje. Os cenários são os mesmos da
    comparação entre versões — aqui a pergunta é só «passa?»."""

    @classmethod
    def setUpClass(cls):
        cls.resultados = {p.stem: compat.conferir_superficies(_carregar(p), None, compat.CENARIOS, False)
                          for p in CORPUS}

    def test_o_corpus_existe_e_nao_e_de_brinquedo(self):
        # ⛔ Um corpus vazio aprovaria tudo. Medido ao gerar: 19 manifestos,
        # 101 superfícies.
        self.assertGreaterEqual(len(CORPUS), 15)
        self.assertGreaterEqual(sum(len(r) for r in self.resultados.values()), 90)

    def test_toda_superficie_passa_nos_cenarios_comuns(self):
        for nome, sups in self.resultados.items():
            for sup, cens in sups.items():
                for cen in ("cru", "vazio", "tipico", "textos_longos"):
                    with self.subTest(forma=nome, superficie=sup, cenario=cen):
                        self.assertIsNone(cens[cen]["erro"])
                        self.assertLessEqual(cens[cen]["nos"], MAX_NOS)

    def test_muitas_linhas_so_recusa_pelo_teto_de_nos(self):
        # 250 linhas podem passar do teto — e é o ÚNICO motivo aceitável.
        recusadas = 0
        for nome, sups in self.resultados.items():
            for sup, cens in sups.items():
                erro = cens["muitas_linhas"]["erro"]
                if erro:
                    recusadas += 1
                    with self.subTest(forma=nome, superficie=sup):
                        self.assertIn("grande demais", erro)
        # E o teto é alcançado de verdade por telas reais: o cenário não é enfeite.
        self.assertGreater(recusadas, 0)

    def test_a_expansao_faz_diferenca(self):
        # ⛔ Validar o molde cru não prova a expansão: se `tipico` desse o
        # mesmo que `cru` em toda parte, os dados sintéticos não estariam
        # chegando ao molde.
        maiores = sum(
            1 for sups in self.resultados.values() for c in sups.values()
            if c["tipico"]["nos"] > c["cru"]["nos"]
        )
        self.assertGreater(maiores, 50)

    def test_ha_navegacao_no_corpus_e_ela_atravessa(self):
        com_rotas = [p for p in CORPUS if _carregar(p).get("rotas")]
        self.assertTrue(com_rotas, "nenhuma forma com `rotas`: a navegação não está coberta")
        for p in com_rotas:
            m = _carregar(p)
            texto = json.dumps(m)
            if "okmigoNavegar" not in texto:
                continue
            # Tirar a rota do catálogo tem de RECUSAR a tela que a abre.
            sem = {**m, "rotas": []}
            r = compat.conferir_superficies(sem, None, ("tipico",), False)
            erros = [c["tipico"]["erro"] or "" for c in r.values()]
            self.assertTrue(any("rota interna não declarada" in e for e in erros), p.name)
            return
        self.fail("nenhuma forma com rotas usa okmigoNavegar")


class CorpusSemNadaInternoTest(unittest.TestCase):
    """⛔⛔ O repositório é público. Toda string do corpus tem de ser
    vocabulário do próprio pacote (já público), número, sinal ou pseudônimo.
    Uma palavra fora disso é conteúdo de um cartão real vazando."""

    PSEUDONIMO = re.compile(
        r"^(w\d+x*|((txt|num|url|data|hora)\d+)(\.(txt|num|url|data|hora)\d+)*|s\d+"
        r"|/img/u\d+\.png|https://(produto|terceiro)\.exemplo/u\d+\.png)$")

    def _permitida(self, s, voc):
        if s in voc or self.PSEUDONIMO.match(s) or compat._NUMERICO.match(s) or compat._SO_SINAIS.match(s):
            return True
        if "{" in s:
            return all(self._permitida(p.strip(), voc) for p in re.split(r"\{([^}]*)\}", s) if p.strip())
        return all(w in compat._PALAVRAS or any(w and p.startswith(w) for p in compat._PALAVRAS)
                   or self.PSEUDONIMO.match(w) or compat._SO_SINAIS.match(w)
                   for w in s.split())

    def test_toda_string_e_vocabulario_ou_pseudonimo(self):
        voc = compat.vocabulario()
        estranhas = set()

        def andar(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if not self._permitida(k, voc):
                        estranhas.add(k)
                    andar(v)
            elif isinstance(x, list):
                for v in x:
                    andar(v)
            elif isinstance(x, str) and not self._permitida(x, voc):
                estranhas.add(x)

        for p in CORPUS:
            andar(_carregar(p))
        self.assertEqual(sorted(estranhas)[:20], [])

    def test_a_guarda_pega_uma_palavra_de_verdade(self):
        # O negativo da guarda acima: sem ele, um `_permitida` que aceitasse
        # tudo passaria calado.
        voc = compat.vocabulario()
        self.assertFalse(self._permitida("Mensalidade do cliente", voc))
        self.assertFalse(self._permitida("{txt1} pago em dia", voc))
        self.assertFalse(self._permitida("https://api.interno.exemplo/x", voc))
        self.assertTrue(self._permitida("{txt1} · {num2}", voc))

    def test_o_anonimizador_preserva_referencias_cruzadas(self):
        anon = compat.Anonimizador(compat.vocabulario())
        molde = {
            "type": "AdaptiveCard", "body": [
                {"_repetir_lista": {"type": "TextBlock", "text": "Pago: {valor_pago}"},
                 "_de": "cobrancas", "_quando": {"campo": "situacao_real", "em": ["quitada"]}},
                {"type": "Input.Text", "id": "observacao_interna", "label": "Observação do cliente"},
                {"type": "ActionSet", "actions": [
                    {"type": "Action.ToggleVisibility", "title": "Ver",
                     "targetElements": ["observacao_interna"]},
                    {"type": "Action.Submit", "title": "Salvar observação",
                     "data": {"operacao": "gravar_observacao"}}]},
            ]}
        saida = anon.no(molde)
        texto = json.dumps(saida, ensure_ascii=False)
        for real in ("valor_pago", "cobrancas", "situacao_real", "quitada", "observacao_interna",
                     "Observação", "gravar_observacao", "cliente"):
            self.assertNotIn(real, texto)
        corpo = saida["body"]
        # o `{campo}` e o `_de` viram pseudônimos da MESMA família que o gerador lê
        self.assertTrue(compat._PREFIXO.match(corpo[0]["_de"]))
        self.assertEqual(compat.categoria(corpo[0]["_repetir_lista"]["text"].split("{")[1][:-1]), "num")
        # o alvo do toggle continua sendo o id do campo
        self.assertEqual(corpo[2]["actions"][0]["targetElements"], [corpo[1]["id"]])
        # comprimento preservado: os tetos de texto fazem parte da forma
        self.assertEqual(len(corpo[1]["label"]), len("Observação do cliente"))


class DadosSinteticosTest(unittest.TestCase):
    MOLDE = {"type": "AdaptiveCard", "body": [
        {"type": "TextBlock", "text": "{titulo} · {total}"},
        {"_repetir_lista": {"type": "TextBlock", "text": "{nome}: {valor}"},
         "_quando": {"campo": "estado", "em": ["aberto"]}},
        {"_repetir_lista": {"type": "TextBlock", "text": "{rotulo}"}, "_de": "itens"},
    ]}

    def test_os_dados_saem_da_forma_do_molde(self):
        resumo, linhas = compat.dados_sinteticos(self.MOLDE, "tipico")
        self.assertEqual(set(resumo), {"titulo", "total", "itens"})
        self.assertEqual(len(resumo["itens"]), 3)
        self.assertEqual(len(linhas), 3)
        self.assertIsInstance(linhas[0]["valor"], float)
        # o filtro recebe valores que ele aceita E um que ele recusa
        self.assertEqual({l["estado"] for l in linhas}, {"aberto", "fora_do_filtro"})

    def test_deterministico(self):
        self.assertEqual(compat.dados_sinteticos(self.MOLDE, "textos_longos"),
                         compat.dados_sinteticos(self.MOLDE, "textos_longos"))

    def test_os_extremos_sao_extremos(self):
        resumo, linhas = compat.dados_sinteticos(self.MOLDE, "muitas_linhas")
        self.assertEqual(len(linhas), 250)
        self.assertEqual(len(resumo["itens"]), 60)
        resumo, _ = compat.dados_sinteticos(self.MOLDE, "textos_longos")
        self.assertGreater(len(resumo["titulo"]), 1000)
        _, linhas = compat.dados_sinteticos(self.MOLDE, "vazio")
        self.assertEqual(linhas, [])


def _colheita(**cenarios):
    return {"casos": {"c": {"manifestos": {"m": {"compilado": "h", "superficies": {"s": cenarios}}}}}}


def _r(erro=None, nos=3, tipos=None, a11y=None, h="x"):
    return {"erro": erro, "hash": h, "nos": nos, "tipos": tipos or {"texto": nos},
            "a11y": a11y or {"alt": 0, "rotulo": 1, "titulo": 1}}


class ReguaTest(unittest.TestCase):
    """A régua que decide se a versão nova pode sair com o número que tem."""

    def classes(self, antes, depois):
        return {c for c, _, _ in compat.comparar(_colheita(tipico=antes), _colheita(tipico=depois))}

    def test_igual_nao_acusa_nada(self):
        self.assertEqual(self.classes(_r(), _r()), set())

    def test_passava_e_agora_recusa_e_quebra(self):
        self.assertEqual(self.classes(_r(), _r(erro="x", h="y")), {compat.QUEBRA})

    def test_no_a_menos_e_quebra(self):
        self.assertEqual(self.classes(_r(nos=3), _r(nos=2, h="y")), {compat.QUEBRA})

    def test_tipo_trocado_com_mesmo_numero_de_nos_e_quebra(self):
        antes = _r(nos=2, tipos={"texto": 1, "etiqueta": 1})
        depois = _r(nos=2, tipos={"texto": 2}, h="y")
        self.assertEqual(self.classes(antes, depois), {compat.QUEBRA})

    def test_texto_acessivel_a_menos_e_quebra(self):
        depois = _r(a11y={"alt": 0, "rotulo": 0, "titulo": 1}, h="y")
        self.assertEqual(self.classes(_r(), depois), {compat.QUEBRA})

    def test_saida_diferente_sem_perda_e_so_forma(self):
        self.assertEqual(self.classes(_r(), _r(nos=4, tipos={"texto": 4}, h="y")), {compat.FORMA})

    def test_recusada_que_passa_a_entrar_e_novidade(self):
        self.assertEqual(self.classes(_r(erro="x"), _r(h="y")), {compat.NOVO})

    def test_sdk_que_compila_outro_json_pede_regenerar(self):
        antes, depois = _colheita(tipico=_r()), _colheita(tipico=_r())
        depois["casos"]["c"]["manifestos"]["m"]["compilado"] = "outro"
        self.assertEqual({c for c, _, _ in compat.comparar(antes, depois)}, {compat.REGENERAR})

    def test_aplicativo_que_nao_carrega_mais_e_quebra(self):
        depois = {"casos": {"c": {"erro_de_carga": "ImportError: X"}}}
        self.assertEqual({c for c, _, _ in compat.comparar(_colheita(tipico=_r()), depois)}, {compat.QUEBRA})

    def test_exemplo_novo_que_a_base_nao_carregava_nao_acusa(self):
        antes = {"casos": {"c": {"erro_de_carga": "ImportError: nome novo"}}}
        self.assertEqual(compat.comparar(antes, _colheita(tipico=_r())), [])


class SemVerTest(unittest.TestCase):
    def test_salto(self):
        self.assertEqual(compat.salto("0.21.0", "0.21.0"), "nenhum")
        self.assertEqual(compat.salto("0.21.0", "0.21.1"), "correcao")
        self.assertEqual(compat.salto("0.21.0", "0.22.0"), "menor")
        self.assertEqual(compat.salto("0.21.3", "1.0.0"), "maior")
        self.assertEqual(compat.salto("0.21.0", "0.20.9"), "nenhum")

    def test_o_que_cada_classe_exige(self):
        Q, R, F = compat.QUEBRA, compat.REGENERAR, compat.FORMA
        self.assertEqual(compat.exigido(set(), "0.21.0"), "nenhum")
        self.assertEqual(compat.exigido({F}, "0.21.0"), "correcao")
        self.assertEqual(compat.exigido({R, F}, "0.21.0"), "menor")
        self.assertEqual(compat.exigido({Q}, "0.21.0"), "menor")   # 0.x: o menor é o slot de quebra
        self.assertEqual(compat.exigido({Q}, "1.4.0"), "maior")
        self.assertEqual(compat.exigido({R}, "1.4.0"), "menor")

    def test_basta(self):
        self.assertTrue(compat.basta("menor", "correcao"))
        self.assertFalse(compat.basta("correcao", "menor"))
        self.assertFalse(compat.basta("nenhum", "correcao"))
        self.assertTrue(compat.basta("nenhum", "nenhum"))


if __name__ == "__main__":
    unittest.main()
