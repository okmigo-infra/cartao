"""A busca que ABRE ao escolher, em vez de só preencher o campo.

⛔ Por que isto existe: até 21/09 a `Busca` era um `Input.ChoiceSet` e nada
mais. Quem escolhia «MXRF11» na lista via o campo preencher e a tela ficar
parada — o valor estava lá e nenhuma ação o consumia. Defeito de tela real,
relatado com captura.

⭐ Os casos que importam são os NEGATIVOS: que o crivo recuse escrever ao
escolher, e recuse operação que não é leitura declarada. Teste que só monta o
caso feliz prova que o SDK compila, não que a trava trava.
"""

import unittest

from okmigo_cartao import Acao, ContratoDoSdkInvalido, Tela, validar
from okmigo_cartao.sdk import Busca, Opcao


def _busca(**extra):
    return Busca(
        id="busca_universal",
        campo="termo",
        rotulo="Buscar",
        placeholder="Ticker, nome, emissor...",
        sugestoes_por="buscar_ativos",
        sugestoes_iniciais=(Opcao("PETR4 · Petrobras", "PETR4"),),
        **extra,
    )


def _no_da_busca(tela: Tela, leituras: frozenset[str]):
    limpo, erro = validar(tela.compilar(), frozenset(), leituras)
    assert erro is None, erro
    return next(n for n in limpo["corpo"] if n["tipo"] == "escolha_livre")


class BuscaQueAbre(unittest.TestCase):
    def test_sem_ao_escolher_a_busca_segue_como_era(self):
        """⚠️ O campo é opcional: nenhuma tela existente pode mudar."""
        tela = Tela("T", componentes=(_busca(),))
        no = _no_da_busca(tela, frozenset({"buscar_ativos"}))
        self.assertNotIn("ao_escolher", no)

    def test_a_consulta_ao_escolher_atravessa_o_crivo(self):
        tela = Tela(
            "T",
            componentes=(
                _busca(ao_escolher=Acao.consultar("Abrir", "detalhar_ativo")),
            ),
        )
        no = _no_da_busca(tela, frozenset({"buscar_ativos", "detalhar_ativo"}))
        self.assertEqual(no["ao_escolher"]["consultar"], "detalhar_ativo")
        self.assertEqual(no["ao_escolher"]["titulo"], "Abrir")

    def test_o_sdk_recusa_escrever_ao_escolher(self):
        """⛔ Gravar por engano de toque, sem confirmação."""
        with self.assertRaises(ContratoDoSdkInvalido) as capturado:
            _busca(ao_escolher=Acao.escrever("Gravar", "gravar")).compilar()
        self.assertIn("LEITURA", str(capturado.exception))

    def test_o_crivo_recusa_operacao_que_nao_e_leitura_declarada(self):
        """⛔ A trava que vale é a do CRIVO: o SDK é conveniência de quem
        escreve a tela, e o crivo é o que defende quem a lê."""
        tela = Tela(
            "T",
            componentes=(
                _busca(ao_escolher=Acao.consultar("Abrir", "operacao_fantasma")),
            ),
        )
        _, erro = validar(tela.compilar(), frozenset(), frozenset({"buscar_ativos"}))
        self.assertIsNotNone(erro)
        self.assertIn("operacao_fantasma", erro)

    def test_um_submit_ao_escolher_simplesmente_nao_vira_nada(self):
        """⛔ Sem SDK no caminho: um cartão montado à mão com `Action.Submit`
        no `okmigoAoEscolher` não pode virar uma escrita silenciosa."""
        cartao = Tela("T", componentes=(_busca(),)).compilar()
        alvo = next(
            n for n in cartao["body"] if n.get("type") == "Input.ChoiceSet"
        )
        alvo["okmigoAoEscolher"] = {
            "type": "Action.Submit",
            "title": "Gravar",
            "data": {"operacao": "gravar"},
        }
        limpo, erro = validar(cartao, frozenset({"gravar"}), frozenset({"buscar_ativos"}))
        self.assertIsNone(erro)
        no = next(n for n in limpo["corpo"] if n["tipo"] == "escolha_livre")
        self.assertNotIn("ao_escolher", no)


if __name__ == "__main__":
    unittest.main()
