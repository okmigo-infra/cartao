"""Os exemplos públicos compilam, passam no crivo e viram página — também
com os dados nos extremos.

`exemplos/` é o que alguém de fora abre primeiro. Se um exemplo só
funcionasse com três linhas curtas, o autor descobriria o teto com a tela
dele, depois de registrar. Aqui cada superfície de cada exemplo passa pelos
cinco cenários de `scripts/compatibilidade.py` e vira casca (HTML nu) e
página de preview (o bundle Web oficial).
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from okmigo_cartao import MAX_NOS, casca, expandir
from okmigo_cartao.preview import construir_aplicativo, pagina_aplicativo

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("compatibilidade", RAIZ / "scripts" / "compatibilidade.py")
compat = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("compatibilidade", compat)
_spec.loader.exec_module(compat)

EXEMPLOS = sorted((RAIZ / "exemplos").glob("*.py"))


class ExemplosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifestos = {}
        for p in EXEMPLOS:
            for nome, m in compat.manifestos_de_um_modulo(p).items():
                cls.manifestos[f"{p.stem}:{nome}"] = (p, nome, m)

    def test_ha_exemplo_com_aplicativo(self):
        self.assertTrue(self.manifestos)

    def test_cada_superficie_passa_em_todos_os_cenarios(self):
        for chave, (_, _, m) in self.manifestos.items():
            r = compat.conferir_superficies(m, None, compat.CENARIOS, False)
            self.assertEqual(len(r), len(m["superficies"]))
            for sup, cens in r.items():
                for cen, res in cens.items():
                    with self.subTest(exemplo=chave, superficie=sup, cenario=cen):
                        self.assertIsNone(res["erro"])
                        self.assertLessEqual(res["nos"], MAX_NOS)

    def test_a_casca_desenha_os_extremos(self):
        import okmigo_cartao as c

        for chave, (_, _, m) in self.manifestos.items():
            esc, lei = compat.inferir_operacoes([s["cartao"] for s in m["superficies"]])
            for s in m["superficies"]:
                for cen in ("muitas_linhas", "textos_longos"):
                    resumo, linhas = compat.dados_sinteticos(s["cartao"], cen)
                    tela, erro = c.validar(expandir(s["cartao"], resumo, linhas), esc, lei,
                                           rotas=compat.rotas_de(m))
                    with self.subTest(exemplo=chave, superficie=s["nome"], cenario=cen):
                        self.assertIsNone(erro)
                        documento = casca(tela, s["nome"])
                        self.assertIn("<", documento)
                        if cen == "textos_longos" and "Texto sintético longo" in json.dumps(tela, ensure_ascii=False):
                            self.assertIn("Texto sintético longo", documento)

    def test_a_pagina_de_preview_monta_com_dados_extremos(self):
        for chave, (caminho, nome, m) in self.manifestos.items():
            for cen in ("muitas_linhas", "textos_longos"):
                dados = {}
                for s in m["superficies"]:
                    resumo, linhas = compat.dados_sinteticos(s["cartao"], cen)
                    dados[s["nome"]] = {"resumo": resumo, "linhas": linhas}
                with tempfile.TemporaryDirectory() as t:
                    arquivo = Path(t) / "dados.json"
                    arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
                    aplicativo, esc, lei = construir_aplicativo(f"{caminho}:{nome}", arquivo)
                    documento = pagina_aplicativo(aplicativo, f"{caminho}:{nome}", esc, lei)
                with self.subTest(exemplo=chave, cenario=cen):
                    self.assertEqual([s["nome"] for s in aplicativo["superficies"]],
                                     [s["nome"] for s in m["superficies"]])
                    self.assertIn("window.OKMIGO_CARTAO_PREVIEW=", documento)
                    # a página leva o renderer inteiro, não um stub
                    self.assertGreater(len(documento), 100_000)


class CascaDaNavegacaoTest(unittest.TestCase):
    """⛔ Achado pelo `sdk_dados.py`: desde as rotas tipadas, um botão que
    NAVEGA fazia `casca()` levantar `KeyError: 'alvos'` — e com ela o
    `--html` da linha de comando, em qualquer tela com navegação."""

    def test_botao_que_navega_vira_casca_com_o_destino(self):
        import okmigo_cartao as c

        cartao = {"type": "AdaptiveCard", "version": "1.5", "body": [{"type": "ActionSet", "actions": [
            {"type": "Action.Execute", "title": "Abrir",
             "data": {"okmigoNavegar": {"rota": "tarefa", "parametros": {"id": "t1"}}}}]}]}
        tela, erro = c.validar(cartao, rotas={"tarefa": {"id": {"tipo": "texto"}}})
        self.assertIsNone(erro)
        documento = casca(tela)
        self.assertIn("abre: tarefa(id=t1)", documento)

    def test_gesto_desconhecido_nao_derruba_a_casca(self):
        tela = {"versao": "1.5", "corpo": [{"tipo": "acoes", "botoes": [{"titulo": "Novo", "gesto_futuro": {}}]}]}
        self.assertIn("gesto sem casca", casca(tela))


if __name__ == "__main__":
    unittest.main()
