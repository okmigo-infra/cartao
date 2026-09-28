"""Como um nome sai do contrato: aviso, janela, mensagem — e a trava que
recusa a remoção sem janela (`scripts/contrato_so_cresce.py`)."""

import subprocess
import sys
import tempfile
import textwrap
import unittest
import warnings
from pathlib import Path
from unittest import mock

import okmigo_cartao
from okmigo_cartao import depreciacao
from okmigo_cartao.depreciacao import Depreciacao, problema_da_janela

RAIZ = Path(__file__).resolve().parent.parent


class ListaDeHojeTest(unittest.TestCase):
    """As regras valem para toda entrada de `DEPRECIACOES`, hoje e amanhã."""

    def test_toda_depreciacao_e_valida(self):
        for d in depreciacao.DEPRECIACOES:
            with self.subTest(nome=d.nome):
                self.assertIsNone(problema_da_janela(d))
                # continua no contrato enquanto avisa
                self.assertIn(d.nome, okmigo_cartao.__all__)
                # e NÃO está no módulo: senão o `__getattr__` nunca roda e o aviso não sai
                self.assertNotIn(d.nome, vars(okmigo_cartao))
                self.assertIsNotNone(d.resolver())
                self.assertTrue(d.motivo)


class JanelaTest(unittest.TestCase):
    def d(self, desde, sai_em):
        return Depreciacao(nome="X", desde=desde, sai_em=sai_em, alvo="okmigo_cartao.sdk:Tela")

    def test_em_zero_x_sao_duas_versoes_menores(self):
        self.assertIsNotNone(problema_da_janela(self.d("0.22.0", "0.23.0")))
        self.assertIsNone(problema_da_janela(self.d("0.22.0", "0.24.0")))

    def test_de_um_em_diante_e_a_maior_seguinte(self):
        self.assertIsNotNone(problema_da_janela(self.d("1.2.0", "1.9.0")))
        self.assertIsNone(problema_da_janela(self.d("1.2.0", "2.0.0")))

    def test_versao_ilegivel_e_problema(self):
        self.assertIsNotNone(problema_da_janela(self.d("x", "0.30.0")))


class AvisoTest(unittest.TestCase):
    """O nome depreciado ainda funciona — e diz, na linha do consumidor,
    quando sai e o que usar."""

    FALSO = Depreciacao(nome="TelaAntiga", desde="0.22.0", sai_em="0.24.0",
                        alvo="okmigo_cartao.sdk:Tela", use="Tela", motivo="Renomeada.")

    def test_acesso_avisa_e_entrega_o_objeto(self):
        with mock.patch.object(depreciacao, "DEPRECIACOES", (self.FALSO,)):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                obj = okmigo_cartao.TelaAntiga
        self.assertIs(obj, okmigo_cartao.Tela)
        self.assertEqual(len(w), 1)
        self.assertIs(w[0].category, DeprecationWarning)
        msg = str(w[0].message)
        for pedaco in ("TelaAntiga", "0.22.0", "0.24.0", "use Tela", "Renomeada."):
            self.assertIn(pedaco, msg)
        # ⭐ o aviso aponta a linha de QUEM usou, não o pacote
        self.assertEqual(w[0].filename, __file__)

    def test_from_import_tambem_avisa(self):
        with mock.patch.object(depreciacao, "DEPRECIACOES", (self.FALSO,)):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                exec("from okmigo_cartao import TelaAntiga", {})
        self.assertTrue(any(issubclass(x.category, DeprecationWarning) for x in w))

    def test_nome_que_nao_existe_continua_attribute_error(self):
        with self.assertRaises(AttributeError):
            okmigo_cartao.NaoExisteNemDepreciado  # noqa: B018


def _repo(tmp: Path, *, init_all, init_dep, versao):
    (tmp / "src/okmigo_cartao").mkdir(parents=True, exist_ok=True)
    (tmp / "src/okmigo_cartao/__init__.py").write_text(f"__all__ = {init_all!r}\n")
    if init_dep is not None:
        (tmp / "src/okmigo_cartao/depreciacao.py").write_text(textwrap.dedent(init_dep))
    (tmp / "pyproject.toml").write_text(f'[project]\nversion = "{versao}"\n')


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"})


class JanelaNaEsteiraTest(unittest.TestCase):
    """`contrato_so_cresce.py` contra um repositório de mentira: a base, a
    mudança, e o veredito."""

    DEP = '''
        DEPRECIACOES = (
            Depreciacao(nome="Velho", desde="0.2.0", sai_em="0.4.0", alvo="m:Velho"),
        )
    '''

    def rodar(self, *, antes_dep, depois_all, depois_versao):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _git(tmp, "init", "-q")
            _repo(tmp, init_all=["Velho", "Novo"], init_dep=antes_dep, versao="0.2.0")
            _git(tmp, "add", ".")
            _git(tmp, "commit", "-qm", "base")
            _repo(tmp, init_all=depois_all, init_dep=None, versao=depois_versao)
            r = subprocess.run([sys.executable, str(RAIZ / "scripts/contrato_so_cresce.py"), "HEAD"],
                               cwd=tmp, capture_output=True, text=True)
            return r.returncode, r.stdout + r.stderr

    def test_remover_sem_ter_depreciado_e_recusado_mesmo_no_slot_de_quebra(self):
        codigo, saida = self.rodar(antes_dep=None, depois_all=["Novo"], depois_versao="0.3.0")
        self.assertEqual(codigo, 1, saida)
        self.assertIn("não o declarava depreciado", saida)

    def test_remover_antes_do_sai_em_e_recusado(self):
        codigo, saida = self.rodar(antes_dep=self.DEP, depois_all=["Novo"], depois_versao="0.3.0")
        self.assertEqual(codigo, 1, saida)
        self.assertIn("prometido para sair em 0.4.0", saida)

    def test_remover_depois_da_janela_passa(self):
        codigo, saida = self.rodar(antes_dep=self.DEP, depois_all=["Novo"], depois_versao="0.4.0")
        self.assertEqual(codigo, 0, saida)

    def test_janela_cumprida_ainda_exige_o_slot_de_quebra(self):
        dep = self.DEP.replace('sai_em="0.4.0"', 'sai_em="0.2.1"')
        codigo, saida = self.rodar(antes_dep=dep, depois_all=["Novo"], depois_versao="0.2.1")
        self.assertEqual(codigo, 1, saida)
        self.assertIn("não é o slot de quebra", saida)

    def test_so_crescer_nao_pede_nada(self):
        codigo, saida = self.rodar(antes_dep=None, depois_all=["Velho", "Novo", "Mais"], depois_versao="0.2.0")
        self.assertEqual(codigo, 0, saida)


if __name__ == "__main__":
    unittest.main()
