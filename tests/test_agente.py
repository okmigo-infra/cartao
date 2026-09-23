"""O agente de domínio (contrato 1): o bloco do manifesto e as quatro respostas."""

import unittest

from okmigo_cartao import (
    AgenteDeDominio,
    AgenteInvalido,
    Exemplo,
    Orcamento,
    RespostaDeAgenteInvalida,
    validar_resposta,
)
from okmigo_cartao.sdk import Aplicativo, ContratoDoSdkInvalido, Fonte, Superficie, Tela, Texto


def _agente(**k):
    base = dict(
        competencias=("comparar papéis da B3",),
        ferramentas=("get_quotes", "comparar_ativos_resumo"),
        instrucoes="Ticker inexistente vira pergunta com as opções; nunca escolha pela pessoa.",
        exemplos=(Exemplo("sanb11 × itub11", "precisa_esclarecer"),),
    )
    base.update(k)
    return AgenteDeDominio(**base)


def _app(agente, conversa=("get_quotes", "comparar_ativos_resumo"), **k):
    tela = Tela("Tela", (Texto("Conteúdo"),))
    return Aplicativo(
        slug="radaria", endpoint="https://radaria.example/mcp/", para_tipo="amigo",
        descricao="Radar", descricao_humana=None, nome_visivel="RadarIA", versao="1.0.0",
        conversa=conversa,
        superficies=(Superficie("hoje", "Hoje", "Hoje", "radar", "resumo", Fonte("hoje"), tela),),
        agente=agente, **k,
    )


class OBlocoDoManifesto(unittest.TestCase):
    def test_compila_e_volta_pelo_json_igual(self):
        bloco = _agente().compilar()
        self.assertEqual(bloco["contrato"], "1")
        self.assertEqual(bloco["modo"], "declarado")
        self.assertEqual(bloco["orcamento"], {"chamadas": 3, "tokens": 12_000, "segundos": 20})
        self.assertEqual(AgenteDeDominio.de_json(bloco).compilar(), bloco)

    def test_o_aplicativo_leva_o_bloco_e_SEM_ele_nada_muda(self):
        self.assertIn("agente", _app(_agente()).compilar())
        self.assertNotIn("agente", _app(None).compilar())

    def test_ferramenta_fora_da_conversa_e_recusada(self):
        """⛔ Seria operação escondida da conversa chamada pela porta do agente."""
        with self.assertRaisesRegex(ContratoDoSdkInvalido, "fora da conversa: buscar_ativos"):
            _app(_agente(ferramentas=("get_quotes", "buscar_ativos")))

    def test_sem_lista_de_conversa_o_consumidor_confere_os_efeitos(self):
        _app(_agente(), conversa=None)

    def test_agente_nao_entra_por_extras(self):
        with self.assertRaisesRegex(ContratoDoSdkInvalido, "agente"):
            _app(None, extras={"agente": {"modo": "declarado"}})

    def test_declarado_sem_ferramenta_responderia_de_cabeca(self):
        with self.assertRaisesRegex(AgenteInvalido, "precisa de ferramentas"):
            _agente(ferramentas=())

    def test_instrucao_acima_do_teto_e_a_regra_migrando_para_o_prompt(self):
        with self.assertRaisesRegex(AgenteInvalido, "passa de 4000"):
            _agente(instrucoes="x" * 4001)

    def test_contrato_e_modo_desconhecidos_sao_recusados(self):
        with self.assertRaisesRegex(AgenteInvalido, "contrato '2'"):
            _agente(contrato="2")
        with self.assertRaisesRegex(AgenteInvalido, "modo"):
            _agente(modo="autonomo")

    def test_remoto_precisa_da_operacao_e_declarado_nao_a_aceita(self):
        with self.assertRaisesRegex(AgenteInvalido, "remoto precisa"):
            _agente(modo="remoto")
        with self.assertRaisesRegex(AgenteInvalido, "só do modo remoto"):
            _agente(operacao="conversar")
        remoto = _agente(modo="remoto", operacao="conversar", instrucoes="")
        with self.assertRaisesRegex(ContratoDoSdkInvalido, "conversar"):
            _app(remoto)
        _app(remoto, conversa=("get_quotes", "comparar_ativos_resumo", "conversar"))

    def test_orcamento_tem_teto_e_nao_aceita_booleano(self):
        for errado in (dict(chamadas=5), dict(tokens=50_000), dict(segundos=0), dict(chamadas=True)):
            with self.assertRaises(AgenteInvalido, msg=errado):
                Orcamento(**errado)

    def test_json_cru_com_campo_desconhecido_nao_passa_calado(self):
        bloco = _agente().compilar()
        with self.assertRaisesRegex(AgenteInvalido, "desconhecidos no agente: ferramentass"):
            AgenteDeDominio.de_json({**bloco, "ferramentass": ["x"]})
        with self.assertRaisesRegex(AgenteInvalido, "orçamento aceita só"):
            AgenteDeDominio.de_json({**bloco, "orcamento": {"reais": 3}})
        with self.assertRaisesRegex(AgenteInvalido, "lista"):
            AgenteDeDominio.de_json({**bloco, "ferramentas": "get_quotes"})

    def test_competencia_e_exemplo_sao_conferidos(self):
        with self.assertRaises(AgenteInvalido):
            _agente(competencias=())
        with self.assertRaises(AgenteInvalido):
            _agente(competencias=("x" * 81,))
        with self.assertRaisesRegex(AgenteInvalido, "espera"):
            Exemplo("oi", "respondeu")


class AsQuatroRespostas(unittest.TestCase):
    RESPONDIDO = {
        "forma": "respondido", "texto": "SANB11 tem P/L 6,94x; ITUB4, 11,13x.",
        "fatos": [{"rotulo": "P/L SANB11", "valor": "6,94x"}, {"rotulo": "P/L ITUB4", "valor": 11.13}],
        "fontes": ["radaria"], "data_base": "23/09/2026",
    }

    def test_as_quatro_formas_validas_passam(self):
        for r in (
            self.RESPONDIDO,
            {"forma": "precisa_esclarecer", "pergunta": "ITUB3 ou ITUB4?", "opcoes": ["ITUB3", "ITUB4"],
             "continuacao": "opaco"},
            {"forma": "acao_proposta", "operacao": "favoritar", "parametros": {"ticker": "ITUB4"},
             "resumo": "Favoritar ITUB4"},
            {"forma": "indisponivel", "codigo": "fonte_indisponivel",
             "mensagem_segura": "A fonte não respondeu agora.", "recuperavel": True},
        ):
            self.assertEqual(validar_resposta(r), r)

    def test_respondido_sem_data_base_nao_e_resposta_de_dominio(self):
        sem = {k: v for k, v in self.RESPONDIDO.items() if k != "data_base"}
        with self.assertRaisesRegex(RespostaDeAgenteInvalida, "data_base"):
            validar_resposta(sem)

    def test_fato_precisa_de_rotulo_e_valor(self):
        for fato in ({"valor": 1}, {"rotulo": "x"}, {"rotulo": "x", "valor": True}):
            with self.assertRaisesRegex(RespostaDeAgenteInvalida, "fato"):
                validar_resposta({**self.RESPONDIDO, "fatos": [fato]})

    def test_forma_desconhecida_e_recusada(self):
        for forma in (None, "resposta", "RESPONDIDO"):
            with self.assertRaisesRegex(RespostaDeAgenteInvalida, "forma"):
                validar_resposta({**self.RESPONDIDO, "forma": forma})
        with self.assertRaises(RespostaDeAgenteInvalida):
            validar_resposta("texto solto")

    def test_indisponivel_tem_lista_FECHADA_de_codigos(self):
        base = {"forma": "indisponivel", "mensagem_segura": "Não deu.", "recuperavel": False}
        with self.assertRaisesRegex(RespostaDeAgenteInvalida, "lista fechada"):
            validar_resposta({**base, "codigo": "deu_ruim"})
        with self.assertRaisesRegex(RespostaDeAgenteInvalida, "booleano"):
            validar_resposta({**base, "codigo": "limite", "recuperavel": "sim"})

    def test_acao_proposta_nao_carrega_que_aconteceu(self):
        """⛔ Quem executa é o portão do consumidor, no turno seguinte."""
        base = {"forma": "acao_proposta", "operacao": "favoritar", "parametros": {}, "resumo": "Favoritar"}
        for proibido in ("executado", "confirmado", "confirmado_pela_pessoa"):
            with self.assertRaisesRegex(RespostaDeAgenteInvalida, proibido):
                validar_resposta({**base, proibido: True})

    def test_campo_vazio_nao_e_campo(self):
        with self.assertRaisesRegex(RespostaDeAgenteInvalida, "texto vazio"):
            validar_resposta({**self.RESPONDIDO, "texto": "   "})
        with self.assertRaisesRegex(RespostaDeAgenteInvalida, "fontes vazio"):
            validar_resposta({**self.RESPONDIDO, "fontes": []})


if __name__ == "__main__":
    unittest.main()
