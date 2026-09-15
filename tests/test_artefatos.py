"""O JSON gerado só muda quando o contrato muda de verdade."""

import json

from okmigo_cartao import manifesto_confere, materializar_manifesto


def test_materializacao_preserva_formatacao_quando_o_conteudo_e_igual(tmp_path):
    destino = tmp_path / "manifesto.json"
    original = '{\n    "versao": "1",\n    "slug": "teste"\n}\n'
    destino.write_text(original, encoding="utf-8")

    escreveu = materializar_manifesto(
        destino,
        {"slug": "teste", "versao": "1"},
    )

    assert escreveu is False
    assert destino.read_text(encoding="utf-8") == original
    assert manifesto_confere(destino, {"versao": "1", "slug": "teste"})


def test_materializacao_corrige_contrato_diferente(tmp_path):
    destino = tmp_path / "manifesto.json"
    destino.write_text('{"slug": "antigo"}\n', encoding="utf-8")

    escreveu = materializar_manifesto(destino, {"slug": "novo"}, indentacao=1)

    assert escreveu is True
    assert json.loads(destino.read_text(encoding="utf-8")) == {"slug": "novo"}
