"""OMINFRA-806: o contrato tipado das ações no grupo."""
import pytest

from okmigo_cartao import ContratoDoSdkInvalido
from okmigo_cartao.grupo import (
    Acao, Atividade, CapacidadesDeGrupo, EnviarMensagem, Enquete, ResponderInteracao,
    SugerirPublicacao, acoes_no_grupo,
)


def test_capacidades_fechadas_e_a_reservada_recusada():
    assert CapacidadesDeGrupo(("responder_interacao", "sugerir_publicacao")).compilar() == {
        "capacidades": ["responder_interacao", "sugerir_publicacao"]}
    for ruim in (("criar_evento",), ("voar",), (), ("enviar_mensagem", "enviar_mensagem")):
        with pytest.raises(ContratoDoSdkInvalido):
            CapacidadesDeGrupo(ruim)


def test_a_resposta_que_age_no_grupo():
    r = acoes_no_grupo(ResponderInteracao("t_ab12", "Seu alerta ficou ativo."),
                       SugerirPublicacao("t_ab12", "Qual FII?", titulo="Próxima", enquete=Enquete(("A", "B"))))
    assert r["acoes_no_grupo"][0] == {"tipo": "responder_interacao", "grupo": "t_ab12", "texto": "Seu alerta ficou ativo."}
    s = r["acoes_no_grupo"][1]
    assert s["tipo_de_publicacao"] == "enquete" and s["detalhes"] == {"opcoes": ["A", "B"], "resultado": "sempre"}
    assert s["audiencia"] == "membros" and s["titulo"] == "Próxima"


def test_as_formas_que_o_okmigo_recusaria_nao_saem_do_sdk():
    with pytest.raises(ContratoDoSdkInvalido):
        SugerirPublicacao("t", "x", tipo="material")                    # material sem link
    with pytest.raises(ContratoDoSdkInvalido):
        Acao("http://inseguro")
    with pytest.raises(ContratoDoSdkInvalido):
        Enquete(("só uma",))
    with pytest.raises(ContratoDoSdkInvalido):
        Enquete(tuple("abcdefg"))
    with pytest.raises(ContratoDoSdkInvalido):
        EnviarMensagem("", "oi")
    with pytest.raises(ContratoDoSdkInvalido):
        acoes_no_grupo(ResponderInteracao("t", "a"), ResponderInteracao("t", "b"))
    with pytest.raises(ContratoDoSdkInvalido):
        acoes_no_grupo(*[EnviarMensagem("t", str(i)) for i in range(6)])


def test_material_e_atividade():
    m = SugerirPublicacao("t", "Planilha", tipo="material", acao=Acao("https://ex.com/p", "baixar")).compilar()
    assert m["detalhes"] == {"acao": {"rotulo": "baixar", "url": "https://ex.com/p"}}
    a = SugerirPublicacao("t", "Mutirão", atividade=Atividade("2026-10-03T09:00:00-03:00", "praça")).compilar()
    assert a["tipo_de_publicacao"] == "atividade" and a["detalhes"]["onde"] == "praça"


def test_o_aplicativo_declara_as_capacidades_de_grupo():
    from okmigo_cartao import Aplicativo, Fonte, Superficie, Tela, Texto
    tela = Tela("Radar", (Texto("oi"),))
    kw = dict(slug="radar", endpoint="https://radar.example/mcp", para_tipo="amigo", descricao="Radar",
              descricao_humana=None, nome_visivel="Radar", versao="1", conversa=(),
              superficies=(Superficie("inicio", "Início", "Início", "radar", "lista", Fonte("listar"), tela),))
    m = Aplicativo(**kw, grupo=CapacidadesDeGrupo(("responder_interacao",))).compilar()
    assert m["grupo"] == {"capacidades": ["responder_interacao"]}
    assert "grupo" not in Aplicativo(**kw).compilar()
    with pytest.raises(ContratoDoSdkInvalido):
        Aplicativo(**kw, grupo={"capacidades": ["enviar_mensagem"]}).compilar()
    with pytest.raises(ContratoDoSdkInvalido):
        Aplicativo(**kw, extras={"grupo": {"capacidades": ["x"]}})
