"""A matriz do contrato (OMINFRA-976): o gerador da §3.2 do PADRAO-QA.

Os manifestos de `tests/dados/manifestos/` são os REGISTRADOS dos onze apps
(14 arquivos: os apps de dois e três lados têm um por slug), copiados da
`main` de cada repo em 05/10/2026. ⚠️ Este repo é público: o `endpoint` de
todos virou `http://SEU-HOST:8000/mcp/` e a `credencial_sondagem` do horaok
virou fictícia — o resto é o que o okmigo recebe.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from okmigo_cartao.__main__ import main
from okmigo_cartao.matriz import (
    CANAIS,
    CATEGORIAS,
    CHAVES_CONHECIDAS,
    COLUNAS,
    NAO_SE_APLICA,
    ChaveDesconhecida,
    ManifestoInvalido,
    conferir,
    contagem,
    gerar,
    gerar_de_varios,
)

DADOS = Path(__file__).parent / "dados" / "manifestos"
TODOS = sorted(DADOS.glob("*.json"))
RAIZ = Path(__file__).resolve().parents[1]


def _ler(nome: str) -> dict:
    return json.loads((DADOS / nome).read_text(encoding="utf-8"))


def _preencher(documento: dict) -> dict:
    """A matriz como o ciclo a devolveria: todo canal aplicável e o resultado."""
    cheia = copy.deepcopy(documento)
    for l in cheia["linhas"]:
        for c in CANAIS:
            if l[c] != NAO_SE_APLICA:
                l[c] = "passou — captura 01"
        l["resultado"] = "passou"
        l["evidencia"] = "ciclo de 05/10, caso 1"
    return cheia


# ── todos os manifestos reais ───────────────────────────────────────────────

def test_os_quatorze_manifestos_estao_aqui():
    assert len(TODOS) == 14


@pytest.mark.parametrize("arquivo", TODOS, ids=lambda p: p.stem)
def test_nenhum_manifesto_real_quebra(arquivo):
    m = json.loads(arquivo.read_text(encoding="utf-8"))
    linhas = gerar(m)
    assert linhas
    ids = [l["id"] for l in linhas]
    assert len(ids) == len(set(ids)), "id repetido"
    for l in linhas:
        assert tuple(l) == COLUNAS
        assert l["slug"] == m["slug"]
        assert l["categoria"] in CATEGORIAS
        assert l["o_que_provar"]
        assert all(l[c] in ("", NAO_SE_APLICA) for c in CANAIS)
        assert l["resultado"] == "" and l["evidencia"] == ""
    # toda superfície tem os sete estados, e nada além deles
    sup = [l for l in linhas if l["categoria"] == "superficie"]
    assert len(sup) == 7 * len(m["superficies"])
    # e nenhuma chave de topo do manifesto passou sem estar na lista
    assert set(m) <= CHAVES_CONHECIDAS


@pytest.mark.parametrize("arquivo", TODOS, ids=lambda p: p.stem)
def test_o_id_e_estavel(arquivo):
    m = json.loads(arquivo.read_text(encoding="utf-8"))
    assert gerar(m) == gerar(copy.deepcopy(m))


#: A tabela de `docs/MATRIZ.md`. Os manifestos daqui são congelados: se este
#: número mudar, mudou o GERADOR — e a tabela do documento muda junto.
LINHAS_POR_ARQUIVO = {
    "calendar": 82, "estoufit-personal": 89, "estoufit-aluno": 206, "estoufit-nutri": 60,
    "dinfinance": 138, "radaria": 346, "horaok": 145, "comcontabil-escritorio": 378,
    "comcontabil-cliente": 201, "dogiromoney": 356, "dogiromoney-pagador": 24,
    "marketplace": 110, "marketplace-loja": 130, "sohautos": 60,
}


def test_a_contagem_de_cada_app_e_a_do_documento():
    contado = {p.stem: len(gerar(json.loads(p.read_text(encoding="utf-8")))) for p in TODOS}
    assert contado == LINHAS_POR_ARQUIVO
    doc = (RAIZ / "docs" / "MATRIZ.md").read_text(encoding="utf-8")
    for n in LINHAS_POR_ARQUIVO.values():
        assert f"| {n} |" in doc


# ── as contagens conferidas à mão ───────────────────────────────────────────

def test_calendar_contado_a_mao():
    """1 superfície (`agenda`) × 7 estados; 7 tipos (ActionSet, Container,
    Input.ChoiceSet, Input.Number, Input.Text, TextBlock, okmigoCalendario);
    12 ações = 2 Submit (decidir_pedido_de_horario, definir_compromisso_do_dia)
    + 6 do evento (atendimento: arrastar e cancelar; compromisso: arrastar,
    remover e o formulário; pedido: o formulário) + o toque no dia + os 2
    sobrepostos + navegar o período; 1 rota; 35 da conversa; 12 ferramentas +
    exemplos + orçamento; e 6 declarações (eventos, avisa_antes,
    relata_mudancas, marca_horario, descricao_humana, versao)."""
    linhas = gerar(_ler("calendar.json"))
    assert contagem(linhas) == {
        "superficie": 7, "elemento": 7, "acao": 12, "rota": 1,
        "conversa": 35, "agente": 14, "declaracao": 6,
    }
    assert len(linhas) == 82
    por_id = {l["id"]: l for l in linhas}
    for id_ in ("superficie:agenda:vazio", "superficie:agenda:carregando",
                "elemento:agenda:okmigoCalendario",
                "acao:agenda:evento:pedido:mostrar:form_pedido",
                "acao:agenda:evento:atendimento:arrastar:remarcar_agendamento",
                "acao:agenda:tocar_o_dia:form", "acao:agenda:sobreposto:form",
                "acao:agenda:navegar:periodo_da_agenda", "rota:periodo_da_agenda",
                "conversa:criar_agendamento", "agente:ferramenta:interpretar_data",
                "agente:exemplos", "agente:orcamento", "declaracao:marca_horario"):
        assert id_ in por_id, id_
    # os canais da §3.1
    tela = por_id["superficie:agenda:vazio"]
    assert (tela["web"], tela["android"], tela["ios"], tela["conversa"]) == ("", "", "", "—")
    push = por_id["declaracao:avisa_antes"]
    assert (push["web"], push["android"], push["ios"], push["conversa"]) == ("—", "", "", "—")
    conv = por_id["conversa:criar_agendamento"]
    assert (conv["web"], conv["android"], conv["ios"], conv["conversa"]) == ("—", "—", "—", "")
    versao = por_id["declaracao:versao"]
    assert all(versao[c] == "—" for c in CANAIS)
    assert por_id["agente:orcamento"]["alvo"] == "chamadas=3, segundos=20, tokens=12000"


def test_estoufit_aluno_contado_a_mao():
    """8 superfícies × 7; 49 tipos por superfície (inicio 4, treino 10,
    nutricao 9, historico 5, saude 8, perfil 4, objetivo 4, modo 5); 50 ações
    (treino 22, nutricao 7, historico 1, saude 8, perfil 1, objetivo 1, modo
    10); 2 rotas; 3 grupos de navegação; 31 da conversa; 7 ferramentas +
    exemplos + orçamento; 6 declarações (eventos, convite, para_tipo,
    nome_visivel, descricao_humana, versao)."""
    linhas = gerar(_ler("estoufit-aluno.json"))
    assert contagem(linhas) == {
        "superficie": 56, "elemento": 49, "acao": 50, "rota": 2, "navegacao": 3,
        "conversa": 31, "agente": 9, "declaracao": 6,
    }
    acoes: dict[str, int] = {}
    for l in linhas:
        if l["categoria"] == "acao":
            sup = l["id"].split(":")[1]
            acoes[sup] = acoes.get(sup, 0) + 1
    assert acoes == {"treino": 22, "nutricao": 7, "historico": 1, "saude": 8,
                     "perfil": 1, "objetivo": 1, "modo": 10}
    ids = {l["id"] for l in linhas}
    # o elemento que só existe dentro de um molde `_repetir_lista`
    assert "elemento:inicio:okmigoGrafico" in ids
    assert "acao:modo:navegar:treino" in ids
    assert "navegacao:fitness" in ids


# ── o percurso do cartão ────────────────────────────────────────────────────

def _manifesto(cartao: dict, **extra) -> dict:
    return {"slug": "teste", "versao": "1.0.0", "endpoint": "http://SEU-HOST:8000/mcp/",
            "forma": "do_operador", "descricao": "x",
            "superficies": [{"nome": "tela", "cartao": cartao}], **extra}


def test_acha_o_elemento_dentro_do_molde_do_fallback_e_do_desktop():
    cartao = {
        "type": "AdaptiveCard", "version": "1.5",
        "body": [
            {"type": "Container", "items": [
                {"_repetir_lista": {"type": "okmigoRanking", "titulo": "{nome}"}}]},
            {"type": "okmigoInventado", "fallback": {"type": "FactSet", "facts": []}},
        ],
        "okmigoDesktop": {"type": "AdaptiveCard", "body": [{"type": "okmigoAgenda"}]},
    }
    tipos = {l["alvo"].split(" · ")[1] for l in gerar(_manifesto(cartao))
             if l["categoria"] == "elemento"}
    assert tipos == {"Container", "okmigoRanking", "okmigoInventado", "FactSet", "okmigoAgenda"}


def test_as_acoes_de_cada_forma():
    cartao = {
        "type": "AdaptiveCard",
        "body": [
            {"type": "ActionSet", "actions": [
                {"type": "Action.Submit", "title": "Salvar", "data": {"operacao": "salvar"},
                 "okmigoAposEnviar": {"type": "Action.ToggleVisibility",
                                      "targetElements": [{"elementId": "a", "isVisible": False}]}},
                {"type": "Action.Execute", "title": "Ver", "data": {"operacao": "ver"}},
                {"type": "Action.Execute", "title": "Abrir",
                 "data": {"okmigoNavegar": {"rota": "detalhe", "parametros": {}}}},
                {"type": "Action.ToggleVisibility", "title": "x",
                 "targetElements": [{"elementId": "b", "isVisible": True},
                                    {"elementId": "c", "isVisible": False}]},
                # a mesma alternância escrita em outra ordem é o MESMO gesto
                {"type": "Action.ToggleVisibility", "title": "y",
                 "targetElements": [{"elementId": "c", "isVisible": False},
                                    {"elementId": "b", "isVisible": True}]},
                {"type": "Action.ShowCard", "title": "Mais"},
                {"type": "Action.Submit", "title": "sem operação", "data": {}},
            ]},
            {"type": "Container", "id": "form", "okmigoSobreposto": True,
             "selectAction": {"type": "Action.Execute", "title": "t",
                              "data": {"operacao": "ver"}}},
            {"type": "okmigoDocumento", "ler": {"operacao": "baixar"}},
            {"type": "Input.ChoiceSet", "id": "q", "style": "filtered",
             "okmigoBuscar": "sugerir"},
        ],
    }
    ids = sorted(l["id"] for l in gerar(_manifesto(cartao)) if l["categoria"] == "acao")
    assert ids == [
        "acao:tela:alternar:+b,-c",
        "acao:tela:autocompletar:sugerir",
        "acao:tela:consultar:baixar",
        "acao:tela:consultar:ver",
        "acao:tela:enviar:salvar",
        "acao:tela:navegar:detalhe",
        "acao:tela:showcard:Mais",
        "acao:tela:sobreposto:form",
    ]


def test_operacoes_fora_da_conversa_e_declaracoes_por_entrada():
    m = _manifesto(
        {"type": "AdaptiveCard", "body": [{"type": "TextBlock", "text": "oi"}]},
        conversa=["ler"],
        operacoes=[{"nome": "ler", "efeitos": "leitura"},
                   {"nome": "agenda_canonica_eventos", "efeitos": "leitura"}],
        recebe_documento=[{"operacao": "conectar", "campos": ["cpf"]}],
        estados_restauraveis=[{"superficie": "tela", "campos": ["filtros"]}],
        so_por_convite=False,
    )
    por_id = {l["id"]: l for l in gerar(m)}
    assert "conversa:ler" in por_id
    fora = por_id["operacao:agenda_canonica_eventos"]
    assert all(fora[c] == "—" for c in CANAIS)
    assert "operacao:ler" not in por_id
    assert "declaracao:recebe_documento:conectar" in por_id
    restaura = por_id["declaracao:estados_restauraveis:tela"]
    assert (restaura["web"], restaura["android"], restaura["ios"]) == ("—", "", "")
    # declarada como falsa não é declaração presente
    assert "declaracao:so_por_convite" not in por_id


def test_sem_lista_de_conversa_toda_operacao_entra_nela():
    m = _manifesto({"type": "AdaptiveCard", "body": [{"type": "TextBlock", "text": "oi"}]},
                   operacoes=[{"nome": "a"}, {"nome": "b"}])
    ids = {l["id"] for l in gerar(m)}
    assert {"conversa:a", "conversa:b"} <= ids
    assert not any(i.startswith("operacao:") for i in ids)


def test_o_aplicativo_do_sdk_deste_pacote_passa():
    """O SDK emite `busca`: o gerador não pode recusar o que o próprio pacote produz."""
    sys.path.insert(0, str(RAIZ / "exemplos"))
    try:
        import sdk_catalogo
    finally:
        sys.path.pop(0)
    m = sdk_catalogo.APLICATIVO.compilar()
    assert "busca" in m
    linhas = gerar(m)
    assert any(l["id"] == "declaracao:busca" for l in linhas)


# ── a chave que o gerador não conhece ───────────────────────────────────────

def test_chave_inventada_reprova():
    m = _ler("calendar.json")
    m["promete_teletransporte"] = {"operacao": "x"}
    with pytest.raises(ChaveDesconhecida) as e:
        gerar(m)
    assert "promete_teletransporte" in str(e.value)
    assert "acrescente a chave à tabela §3.1 do PADRAO-QA e ao gerador" in str(e.value)


def test_chave_inventada_reprova_pela_linha_de_comando(tmp_path, capsys):
    m = _ler("calendar.json")
    m["promete_teletransporte"] = True
    arq = tmp_path / "m.json"
    arq.write_text(json.dumps(m), encoding="utf-8")
    saida = tmp_path / "matriz.md"
    assert main(["matriz", str(arq), "--saida", str(saida)]) == 2
    err = capsys.readouterr().err
    assert "`promete_teletransporte`" in err and "PADRAO-QA" in err
    assert not saida.exists(), "matriz parcial não pode ser escrita"


def test_o_que_nao_e_manifesto_reprova():
    with pytest.raises(ManifestoInvalido):
        gerar({"type": "AdaptiveCard", "body": []})


# ── a linha de comando ──────────────────────────────────────────────────────

def test_gera_markdown_e_json(tmp_path, capsys):
    md = tmp_path / "m.md"
    js = tmp_path / "m.json"
    cal, aluno = str(DADOS / "calendar.json"), str(DADOS / "estoufit-aluno.json")
    assert main(["matriz", cal, aluno, "--saida", str(md)]) == 0
    assert main(["matriz", cal, aluno, "--formato", "json", "--saida", str(js)]) == 0
    texto = md.read_text(encoding="utf-8")
    assert "## agenda" in texto and "## estoufit-aluno" in texto
    assert "| superficie:agenda:vazio | agenda | superficie |" in texto
    doc = json.loads(js.read_text(encoding="utf-8"))
    assert doc["formato"] == "okmigo-matriz/1"
    assert [m["slug"] for m in doc["manifestos"]] == ["agenda", "estoufit-aluno"]
    assert len(doc["linhas"]) == 82 + 206
    assert doc["colunas"] == list(COLUNAS)


def test_sem_saida_escreve_no_terminal(capsys):
    assert main(["matriz", str(DADOS / "sohautos.json"), "--formato", "json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert any(l["id"] == "declaracao:vitrine_url" for l in doc["linhas"])


def test_roda_como_modulo():
    r = subprocess.run([sys.executable, "-m", "okmigo_cartao", "matriz",
                        str(DADOS / "calendar.json")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "82 linhas" in r.stdout


# ── --conferir ──────────────────────────────────────────────────────────────

def _conferir_cli(tmp_path, manifestos: list[dict], matriz: dict) -> int:
    caminhos = []
    for i, m in enumerate(manifestos):
        p = tmp_path / f"manifesto{i}.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        caminhos.append(str(p))
    preenchida = tmp_path / "preenchida.json"
    preenchida.write_text(json.dumps(matriz), encoding="utf-8")
    return main(["matriz", *caminhos, "--conferir", str(preenchida)])


def test_matriz_completa_passa(tmp_path, capsys):
    ms = [_ler("calendar.json"), _ler("estoufit-aluno.json")]
    cheia = _preencher(gerar_de_varios(ms))
    assert conferir(ms, cheia) == ([], [])
    assert _conferir_cli(tmp_path, ms, cheia) == 0
    assert "matriz completa" in capsys.readouterr().out


def test_matriz_com_uma_linha_vazia_reprova(tmp_path, capsys):
    ms = [_ler("calendar.json")]
    cheia = _preencher(gerar_de_varios(ms))
    alvo = next(l for l in cheia["linhas"] if l["id"] == "superficie:agenda:erro")
    alvo["ios"] = ""
    alvo["resultado"] = ""
    problemas, _ = conferir(ms, cheia)
    assert problemas == ["agenda superficie:agenda:erro: canal `ios` vazio",
                         "agenda superficie:agenda:erro: `resultado` vazio"]
    assert _conferir_cli(tmp_path, ms, cheia) == 1
    out = capsys.readouterr().out
    assert "REPROVADA" in out and "canal `ios` vazio" in out


def test_o_traco_num_canal_que_se_aplica_conta_como_vazio():
    ms = [_ler("calendar.json")]
    cheia = _preencher(gerar_de_varios(ms))
    alvo = next(l for l in cheia["linhas"] if l["id"] == "declaracao:avisa_antes")
    alvo["android"] = NAO_SE_APLICA
    problemas, _ = conferir(ms, cheia)
    assert problemas == ["agenda declaracao:avisa_antes: canal `android` vazio"]


def test_resultado_que_falhou_ou_nao_diz_reprova():
    ms = [_ler("calendar.json")]
    cheia = _preencher(gerar_de_varios(ms))
    cheia["linhas"][0]["resultado"] = "falhou: a tela pisca"
    cheia["linhas"][1]["resultado"] = "ok"
    cheia["linhas"][2]["web"] = "falhou"
    problemas, _ = conferir(ms, cheia)
    assert len(problemas) == 3
    assert "`resultado` falhou" in problemas[0]
    assert "não diz «passou» nem «falhou»" in problemas[1]
    assert "canal `web` falhou" in problemas[2]


def test_matriz_que_nao_cobre_o_manifesto_de_hoje_reprova():
    """O manifesto ganhou uma operação na conversa depois da matriz preenchida."""
    antigo = _ler("calendar.json")
    cheia = _preencher(gerar_de_varios([antigo]))
    hoje = copy.deepcopy(antigo)
    hoje["conversa"].append("teletransportar")
    hoje["conversa"].remove("criar_servico")
    problemas, avisos = conferir([hoje], cheia)
    assert problemas == ["agenda conversa:teletransportar: linha nova no manifesto, sem par "
                         "na matriz preenchida — regenere a matriz e prove a linha"]
    assert avisos == ["agenda conversa:criar_servico: linha que o manifesto de hoje não tem "
                      "mais (ignorada)"]


def test_conferir_com_chave_inventada_reprova(tmp_path):
    m = _ler("calendar.json")
    cheia = _preencher(gerar_de_varios([m]))
    m["promete_teletransporte"] = True
    assert _conferir_cli(tmp_path, [m], cheia) == 2


def test_conferir_arquivo_que_nao_e_matriz():
    problemas, _ = conferir([_ler("calendar.json")], {"nada": 1})
    assert problemas and "linhas" in problemas[0]
