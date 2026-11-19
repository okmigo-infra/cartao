"""OMINFRA-1364: a operação que diz se o serviço já anda para o tenant."""

import unittest

from okmigo_cartao import (
    AgenteDeDominio,
    AgenteInvalido,
    RespostaDeAgenteInvalida,
    validar_prontidao,
)


def _agente(**k):
    base = dict(
        competencias=("extrato: o que entrou e o que saiu",),
        ferramentas=("extrato", "fluxo_de_caixa"),
        instrucoes="Use o extrato para o que entrou e saiu.",
        cobre=("financeiro.fluxo_de_caixa",),
        prontidao="prontidao",
    )
    base.update(k)
    return AgenteDeDominio(**base)


class TestDeclarar(unittest.TestCase):
    def test_compila_e_volta_pelo_json(self):
        bloco = _agente().compilar()
        self.assertEqual(bloco["prontidao"], "prontidao")
        self.assertEqual(AgenteDeDominio.de_json(bloco), _agente())

    def test_sem_prontidao_o_bloco_nao_muda(self):
        self.assertNotIn("prontidao", _agente(prontidao=None).compilar())

    def test_recusa_sem_cobre(self):
        with self.assertRaisesRegex(AgenteInvalido, "junto de cobre"):
            _agente(cobre=())

    def test_recusa_nome_que_nao_e_identificador(self):
        with self.assertRaises(AgenteInvalido):
            _agente(prontidao="está pronto?")


class TestResposta(unittest.TestCase):
    def test_pronto(self):
        self.assertEqual(validar_prontidao({"pronto": True, "falta": "x"}), {"pronto": True})

    def test_falta_conectar(self):
        r = validar_prontidao({"pronto": False, "falta": " conectar um banco ", "superficie": "bancos"})
        self.assertEqual(r, {"pronto": False, "falta": "conectar um banco", "superficie": "bancos"})

    def test_falta_e_obrigatoria(self):
        for bruto in ({"pronto": False}, {"pronto": False, "falta": "  "}):
            with self.assertRaises(RespostaDeAgenteInvalida):
                validar_prontidao(bruto)

    def test_pronto_precisa_ser_booleano(self):
        for bruto in ({"pronto": "sim"}, {"pronto": 1}, {}, [], None):
            with self.assertRaises(RespostaDeAgenteInvalida):
                validar_prontidao(bruto)

    def test_superficie_invalida(self):
        with self.assertRaises(RespostaDeAgenteInvalida):
            validar_prontidao({"pronto": False, "falta": "conectar", "superficie": "../x"})

    def test_falta_longa_e_cortada(self):
        r = validar_prontidao({"pronto": False, "falta": "a" * 500})
        self.assertEqual(len(r["falta"]), 120)


if __name__ == "__main__":
    unittest.main()
