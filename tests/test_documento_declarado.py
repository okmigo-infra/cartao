"""O documento DECLARADO — a exceção ao filtro de privacidade do consumidor.

⛔⛔ **Por que este contrato existe.** O okmigo passa todo pedido de saída por
um filtro (D21): o amigo traduz o que sabe no MÍNIMO que o outro agente
precisa, e a camada estrutural barra documento, financeiro, saúde e credencial.
Medido em 18/09, era esse filtro que fazia CONECTAR UM BANCO ser impossível
pela tela — o CPF que a pessoa digitava batia no padrão de `documento` e o
pedido morria antes de sair, com o formulário certo e o serviço saudável do
lado. O mesmo valia para o formulário antigo, com dois bancos chumbados: o
caminho nunca funcionou, para banco nenhum.

⭐ O filtro continua valendo. O que muda é que a exceção passa a ser DECLARADA,
no contrato que a pessoa aprova ao instalar.
"""

from __future__ import annotations

import pytest

from okmigo_cartao import (
    Aplicativo, ContratoDoSdkInvalido, DocumentoDeclarado, Superficie,
)


def _superficie() -> Superficie:
    from okmigo_cartao import Fonte, Tela, Texto

    # ⚠️ Posicional, como os vizinhos: nome, titulo, rotulo, icone, hint,
    # fonte, tela.
    return Superficie(
        "contas", "Contas", "Contas", "contas", "as suas contas",
        Fonte("contas_resumo", "contas"),
        Tela("Contas", componentes=(Texto("oi"),)),
    )


def test_declara_a_operacao_e_os_campos():
    d = DocumentoDeclarado("conectar", ("cpf", "cnpj"))
    assert d.compilar() == {"operacao": "conectar", "campos": ["cpf", "cnpj"]}


def test_a_lista_de_campos_e_FECHADA_e_senha_NUNCA_entra():
    """⛔ Quem pede a senha do banco é o banco, na página dele. Um serviço que
    tentasse declarar `senha` como documento estaria pedindo para o okmigo
    deixar passar exatamente o que o filtro existe para barrar."""
    with pytest.raises(ContratoDoSdkInvalido) as e:
        DocumentoDeclarado("conectar", ("senha",))
    assert "senha" in str(e.value).lower()
    for proibido in ("password", "token", "secret", "cvv", "api_key"):
        with pytest.raises(ContratoDoSdkInvalido):
            DocumentoDeclarado("conectar", (proibido,))


def test_declaracao_VAZIA_e_recusada():
    """⚠️ Declarar a operação sem campo nenhum seria uma exceção sem escopo —
    o pior formato, porque parece uma decisão e não delimita nada."""
    with pytest.raises(ContratoDoSdkInvalido):
        DocumentoDeclarado("conectar", ())


def test_o_aplicativo_SEM_declaracao_nao_emite_a_chave():
    """⛔ O padrão é NÃO receber documento. Emitir uma chave vazia faria todo
    manifesto parecer que pediu alguma coisa."""
    app = Aplicativo(
        slug="x", endpoint="https://x/mcp/", para_tipo=None, descricao="d",
        descricao_humana=None, nome_visivel=None, versao="1.0",
        conversa=None, superficies=(_superficie(),),
    )
    assert "recebe_documento" not in app.compilar()


def test_o_aplicativo_COM_declaracao_a_emite():
    app = Aplicativo(
        slug="x", endpoint="https://x/mcp/", para_tipo=None, descricao="d",
        descricao_humana=None, nome_visivel=None, versao="1.0",
        conversa=None, superficies=(_superficie(),),
        recebe_documento=(DocumentoDeclarado("conectar", ("cpf",)),),
    )
    assert app.compilar()["recebe_documento"] == [
        {"operacao": "conectar", "campos": ["cpf"]}
    ]


def test_extras_nao_pode_atropelar_a_declaracao():
    """⛔ `extras` é a porta de trás do manifesto. Se ela pudesse escrever
    `recebe_documento`, a lista fechada de campos deixaria de valer."""
    with pytest.raises(ContratoDoSdkInvalido):
        Aplicativo(
            slug="x", endpoint="https://x/mcp/", para_tipo=None, descricao="d",
            descricao_humana=None, nome_visivel=None, versao="1.0",
            conversa=None, superficies=(_superficie(),),
            extras={"recebe_documento": [{"operacao": "conectar",
                                          "campos": ["senha"]}]},
        )
