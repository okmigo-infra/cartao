"""ADR 005 do okmigo: o agente declara as competências do catálogo que COBRE."""

import unittest

from okmigo_cartao import AgenteDeDominio, AgenteInvalido
from okmigo_cartao.sdk import Aplicativo, ContratoDoSdkInvalido, Fonte, Superficie, Tela, Texto


def _agente(**k):
    base = dict(
        competencias=("extrato: o que entrou e o que saiu",),
        ferramentas=("extrato", "fluxo_de_caixa"),
        instrucoes="Use o extrato para o que entrou e saiu.",
        cobre=("financeiro.fluxo_de_caixa", "financeiro.conciliacao"),
    )
    base.update(k)
    return AgenteDeDominio(**base)


def _app(agente, para_tipo="socio"):
    tela = Tela("Tela", (Texto("Conteúdo"),))
    return Aplicativo(
        slug="dinfinance", endpoint="https://dinfinance.example/mcp/", para_tipo=para_tipo,
        descricao="Dinheiro", descricao_humana=None, nome_visivel="Financeiro", versao="1.0.0",
        conversa=("extrato", "fluxo_de_caixa"),
        superficies=(Superficie("hoje", "Hoje", "Hoje", "dinheiro", "resumo", Fonte("hoje"), tela),),
        agente=agente,
    )


class OCobre(unittest.TestCase):
    def test_compila_e_volta_pelo_json_igual(self):
        bloco = _agente().compilar()
        self.assertEqual(bloco["cobre"], ["financeiro.fluxo_de_caixa", "financeiro.conciliacao"])
        self.assertEqual(AgenteDeDominio.de_json(bloco).compilar(), bloco)

    def test_sem_cobre_o_bloco_nao_muda(self):
        # Quem já está registrado sem cobre recompila igual: nada novo no JSON.
        self.assertNotIn("cobre", _agente(cobre=()).compilar())

    def test_id_fora_da_forma_do_catalogo_recusa(self):
        for ruim in ("conciliacao", "Financeiro.conciliacao", "financeiro.", "financeiro.x-y", 3):
            with self.subTest(ruim=ruim), self.assertRaises(AgenteInvalido):
                _agente(cobre=(ruim,))

    def test_repetido_recusa(self):
        with self.assertRaises(AgenteInvalido):
            _agente(cobre=("financeiro.conciliacao", "financeiro.conciliacao"))

    def test_mais_de_vinte_recusa(self):
        with self.assertRaises(AgenteInvalido):
            _agente(cobre=tuple(f"financeiro.c{i}" for i in range(21)))

    def test_remoto_nao_cobre(self):
        # ⛔ Cobrir é responder com as ferramentas do agente declarado.
        with self.assertRaises(AgenteInvalido):
            _agente(modo="remoto", operacao="conversar", ferramentas=())

    def test_cobre_precisa_ser_lista_no_json(self):
        bloco = _agente().compilar()
        bloco["cobre"] = "financeiro.conciliacao"
        with self.assertRaises(AgenteInvalido):
            AgenteDeDominio.de_json(bloco)

    def test_app_de_negocio_compila_com_cobre(self):
        self.assertEqual(_app(_agente()).compilar()["agente"]["cobre"][0], "financeiro.fluxo_de_caixa")

    def test_app_da_conta_pessoal_nao_cobre(self):
        # ⛔ ADR 005 §4.2: o setor é socio; app de amigo nunca instala nele.
        with self.assertRaises(ContratoDoSdkInvalido):
            _app(_agente(), para_tipo="amigo").compilar()


if __name__ == "__main__":
    unittest.main()
