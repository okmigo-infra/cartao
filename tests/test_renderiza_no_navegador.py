"""Os exemplos RENDERIZAM: o bundle Web oficial desenha cada superfície, nos
extremos, sem erro no console e sem rolagem horizontal no quadro de celular.

⚠️ Precisa do Playwright com o Chromium (`pip install playwright &&
python -m playwright install chromium`). Sem ele, o teste é PULADO — a
esteira roda num passo próprio que instala os dois, para que o pulo nunca
seja o que vale lá.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from okmigo_cartao.preview import construir_aplicativo, pagina_aplicativo

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover — o passo da esteira instala
    sync_playwright = None

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("compatibilidade", RAIZ / "scripts" / "compatibilidade.py")
compat = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("compatibilidade", compat)
_spec.loader.exec_module(compat)

CENARIOS = ("vazio", "tipico", "muitas_linhas", "textos_longos")

#: Os nós de texto do quadro de celular cuja caixa passa da borda direita dele.
#: Descontados os que moram num contêiner que ROLA de propósito (tabela larga).
_ESTOUROS = """() => {
  const quadro = document.querySelector('.preview-surface');
  const borda = quadro.getBoundingClientRect().right + 1;
  // Rolagem de propósito é a de um COMPONENTE (galeria, etapas do fluxo): um
  // contêiner com `overflow-x` entre o texto e o miolo da tela. O miolo em si
  // rola na vertical, e o CSS lhe dá `overflow-x: auto` de brinde — aceitá-lo
  // desculparia qualquer texto cortado, então a busca PARA nele.
  const miolo = quadro.querySelector('.superficie-tematica-miolo') || quadro;
  const rola = el => { for (let e = el; e && e !== miolo && e !== quadro; e = e.parentElement) {
      const o = getComputedStyle(e).overflowX; if (o === 'auto' || o === 'scroll') return true; }
    return false; };
  const fora = [];
  const andar = document.createTreeWalker(quadro, NodeFilter.SHOW_TEXT);
  while (andar.nextNode()) {
    const t = andar.currentNode; if (!t.textContent.trim()) continue;
    const r = document.createRange(); r.selectNodeContents(t);
    for (const c of r.getClientRects()) {
      if (c.width > 0 && c.right > borda && !rola(t.parentElement)) {
        fora.push(t.textContent.trim().slice(0, 40)); break; }
    }
  }
  return fora.slice(0, 5);
}"""


@unittest.skipIf(sync_playwright is None and not os.environ.get("EXIGIR_NAVEGADOR"),
                 "sem Playwright: rode `pip install playwright && python -m playwright install chromium`")
class RenderizaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sync_playwright is None:
            raise RuntimeError("EXIGIR_NAVEGADOR=1 e o Playwright não está instalado")
        cls._pw = sync_playwright().start()
        cls.navegador = cls._pw.chromium.launch()
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.navegador.close()
        cls._pw.stop()
        cls.tmp.cleanup()

    def _pagina(self, caminho, nome, manifesto, cenario):
        dados = {}
        for s in manifesto["superficies"]:
            resumo, linhas = compat.dados_sinteticos(s["cartao"], cenario)
            dados[s["nome"]] = {"resumo": resumo, "linhas": linhas}
        base = Path(self.tmp.name) / f"{caminho.stem}-{nome}-{cenario}"
        (base.with_suffix(".json")).write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        aplicativo, esc, lei = construir_aplicativo(f"{caminho}:{nome}", base.with_suffix(".json"))
        base.with_suffix(".html").write_text(
            pagina_aplicativo(aplicativo, f"{caminho}:{nome}", esc, lei), encoding="utf-8")
        return aplicativo, base.with_suffix(".html")

    def test_cada_superficie_desenha_nos_extremos(self):
        vistas = 0
        for caminho in sorted((RAIZ / "exemplos").glob("*.py")):
            for nome, manifesto in compat.manifestos_de_um_modulo(caminho).items():
                for cenario in CENARIOS:
                    aplicativo, html = self._pagina(caminho, nome, manifesto, cenario)
                    for s in aplicativo["superficies"]:
                        # Abre JÁ na superfície: a barra pode estar agrupada, e o
                        # que se prova aqui é o desenho, não o clique.
                        html.write_text(pagina_aplicativo({**aplicativo, "atual": s["nome"]},
                                                          f"{caminho}:{nome}", frozenset(), frozenset()),
                                        encoding="utf-8")
                        # ⛔ Janela de 430 px, e não a larga com o quadro de 390 dentro:
                        # o renderer adapta por `@media (max-width: …)`, que olha a
                        # JANELA. Numa janela larga o quadro de celular mostra o
                        # mestre–detalhe lado a lado e cortado — o que nenhum
                        # celular vê (medido ao escrever este teste).
                        pagina = self.navegador.new_page(viewport={"width": 430, "height": 900})
                        erros: list[str] = []
                        pagina.on("pageerror", lambda e, erros=erros: erros.append(str(e)))
                        # A imagem sintética (`/img/sintetica-N.png`) não existe no disco:
                        # recurso que não carrega é rede, não desenho — o resto conta.
                        pagina.on("console", lambda m, erros=erros: erros.append(m.text)
                                  if m.type == "error" and not m.text.startswith("Failed to load resource")
                                  else None)
                        pagina.goto(html.as_uri())
                        pagina.get_by_role("button", name="Celular", exact=True).click()
                        with self.subTest(exemplo=f"{caminho.stem}:{nome}", cenario=cenario, superficie=s["nome"]):
                            quadro = pagina.locator(".preview-surface").first
                            quadro.wait_for(timeout=5000)
                            self.assertGreater(len(quadro.inner_text().strip()), 0)
                            # ⛔ rolagem horizontal no quadro de 390 px = texto longo estourando
                            # Mede o TEXTO, não a caixa: um contêiner com overflow
                            # escondido corta o texto sem rolar, e só o retângulo
                            # do nó de texto mostra que ele passou da borda.
                            estouros = pagina.evaluate(_ESTOUROS)
                            self.assertEqual(estouros, [])
                            self.assertEqual(erros, [])
                            vistas += 1
                        pagina.close()
        self.assertGreater(vistas, 0)

if __name__ == "__main__":
    unittest.main()
