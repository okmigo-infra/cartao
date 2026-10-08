"""OMINFRA-1037: o papel do app, que o broker de roteamento do okmigo lê."""

import pytest

from okmigo_cartao import (
    ExemploDeRoteamento as Ex,
    Papel,
    PapelInvalido,
    Relacao,
    avisos_do_cadastro,
    pares_que_nao_batem,
)

GESTAO = Papel(
    descricao="O ERP financeiro da organização: contas a pagar e a receber, cobrança e conciliação.",
    dono_de=("contas a pagar e a receber da empresa", "cobrança", "conciliação"),
    recebe_de=(Relacao("dinfinance", "o extrato do banco, para conciliar"),),
    entrega_para=(Relacao("comcontabil", "o pacote contábil do mês"),),
    nao_e_meu=("saldo e extrato do banco — é do Financeiro",),
    definicoes={"obrigação": "conta a pagar com vencimento"},
    exemplos=(Ex("quais contas a empresa tem para pagar esta semana?", "obrigacoes"),
              Ex("lança a conta de luz de 300 reais para dia 10", "nova_obrigacao")),
)


def test_compila_e_volta_igual():
    bloco = GESTAO.compilar()
    assert Papel.de_json(bloco).compilar() == bloco
    assert bloco["recebe_de"] == [{"app": "dinfinance", "o_que": "o extrato do banco, para conciliar"}]


@pytest.mark.parametrize("bruto,erro", [
    ({"descricao": "x", "dono_de": []}, "dono_de"),
    ({"descricao": "", "dono_de": ["a"]}, "descricao"),
    ({"descricao": "x", "dono_de": ["a"], "inventado": 1}, "desconhecidos"),
    ({"descricao": "x", "dono_de": ["a"], "recebe_de": [{"app": "Não É Slug", "o_que": "y"}]}, "slug"),
    ({"descricao": "x", "dono_de": ["a"], "exemplos": [{"pedido": "oi"}, {"pedido": "OI"}]}, "repetido"),
])
def test_o_bloco_cru_passa_pelo_mesmo_crivo(bruto, erro):
    with pytest.raises(PapelInvalido, match=erro):
        Papel.de_json(bruto)


def _manifesto(**kw):
    m = {"slug": "dogiromoney", "conversa": ["obrigacoes", "nova_obrigacao"], "papel": GESTAO.compilar()}
    m.update(kw)
    return m


def test_cadastro_completo_nao_avisa():
    assert avisos_do_cadastro(_manifesto()) == []


def test_sem_papel_avisa_e_nao_recusa():
    m = _manifesto()
    del m["papel"]
    assert avisos_do_cadastro(m) == ["sem papel: o broker não sabe quando um pedido é deste app (OMINFRA-1037)"]


def test_operacao_da_conversa_sem_exemplo_avisa():
    avisos = avisos_do_cadastro(_manifesto(conversa=["obrigacoes", "nova_obrigacao", "conciliar"]))
    assert any("sem exemplo: conciliar" in a for a in avisos)


def test_exemplo_de_operacao_fora_da_conversa_avisa():
    avisos = avisos_do_cadastro(_manifesto(conversa=["obrigacoes"]))
    assert any("fora da conversa: nova_obrigacao" in a for a in avisos)


def test_quem_marca_horario_entrega_para_a_agenda():
    avisos = avisos_do_cadastro(_manifesto(marca_horario={"operacao": "pedir", "ofertas": "servicos"}))
    assert any("entrega para a agenda" in a for a in avisos)
    a_agenda = _manifesto(slug="agenda", marca_horario={"operacao": "pedir", "ofertas": "servicos"})
    assert not any("entrega para a agenda" in a for a in avisos_do_cadastro(a_agenda))


def test_o_par_das_relacoes_tem_de_bater():
    fin = Papel(descricao="O banco da pessoa pelo Open Finance.", dono_de=("o extrato do banco",)).compilar()
    faltas = pares_que_nao_batem({"dogiromoney": _manifesto(), "dinfinance": {"papel": fin}})
    assert faltas == ["dogiromoney diz que recebe de dinfinance, e dinfinance não diz que entrega para dogiromoney"]
    fin_ok = Papel(descricao="O banco da pessoa pelo Open Finance.", dono_de=("o extrato do banco",),
                   entrega_para=(Relacao("dogiromoney", "o extrato"),)).compilar()
    assert pares_que_nao_batem({"dogiromoney": _manifesto(), "dinfinance": {"papel": fin_ok}}) == []


def test_o_aplicativo_do_sdk_compila_o_papel():
    from okmigo_cartao.sdk import Aplicativo
    import inspect
    assert "papel" in inspect.signature(Aplicativo).parameters


def test_sem_conversa_usa_as_operacoes_da_ponte():
    """⛔ OMINFRA-1055: sem `conversa`, a cobertura era pulada em silêncio."""
    m = _manifesto()
    del m["conversa"]
    m["operacoes"] = [{"nome": "obrigacoes"}, {"nome": "nova_obrigacao"}, {"nome": "conciliar"},
                      {"nome": "so_da_tela", "conversa": False}]
    avisos = avisos_do_cadastro(m)
    assert any("sem exemplo: conciliar" in a for a in avisos)
    assert not any("so_da_tela" in a for a in avisos)


def test_sem_conversa_nem_operacoes_avisa_em_vez_de_calar():
    m = _manifesto()
    del m["conversa"]
    assert any("não foi conferida" in a for a in avisos_do_cadastro(m))


# ── 0.29.0 · OMINFRA-1064: o que o app CEDE a quem marca horário ─────────────

AGENDA_DE_NEGOCIO = Papel(
    descricao="A agenda padrão de todos.",
    dono_de=("os compromissos do dono", "os atendimentos marcados direto na Agenda"),
    exemplos=(Ex("tenho dentista quinta às 15h", "anotar_compromisso"),
              Ex("quem vem hoje?", "listar_agenda_do_dia"),
              Ex("marca a Juliana pra escova sábado às 10", "criar_agendamento")),
    cede_a_quem_marca_horario=("criar_agendamento",),
)


def test_cede_compila_e_volta_igual():
    bloco = AGENDA_DE_NEGOCIO.compilar()
    assert bloco["cede_a_quem_marca_horario"] == ["criar_agendamento"]
    assert Papel.de_json(bloco).compilar() == bloco
    assert "cede_a_quem_marca_horario" not in GESTAO.compilar(), "vazio não aparece no bloco"


@pytest.mark.parametrize("cede,erro", [
    (["Criar Agendamento"], "nome de uma operação"),
    (["criar_agendamento", "criar_agendamento"], "repetida"),
    ([f"op_{i}" for i in range(41)], "no máximo"),
])
def test_cede_passa_pelo_crivo(cede, erro):
    with pytest.raises(PapelInvalido, match=erro):
        Papel.de_json({"descricao": "x", "dono_de": ["a"], "cede_a_quem_marca_horario": cede})


def test_cede_operacao_fora_da_conversa_avisa():
    bloco = {**AGENDA_DE_NEGOCIO.compilar(), "cede_a_quem_marca_horario": ["criar_agendamento", "inventada"]}
    avisos = avisos_do_cadastro({"slug": "agenda", "papel": bloco,
                                 "conversa": ["anotar_compromisso", "listar_agenda_do_dia", "criar_agendamento"]})
    assert avisos == ["operação cedida fora da conversa: inventada"]
