"""A conferência de versão do manifesto, que veio de oito cópias SEM TESTE.

⛔ **As oito cópias de origem não tinham teste nenhum, e a razão era estrutural:**
toda a regra vivia dentro do `main`, misturada com impressão e código de saída.
Testar exigia capturar stdout. Na migração (OMINFRA-576) a decisão saiu para
`conferir()`, que devolve as três listas e não imprime nada — é o que torna
estes casos baratos.

⚠️ O caso que ninguém escreveria de cabeça é o quarto: mudar SÓ a `versao` não
conta como mudança de conteúdo. Sem ele, uma implementação que compara os
dicionários INTEIROS passaria nos outros três e se aprovaria sozinha.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from okmigo_cartao.esteira import versao_do_manifesto as v


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Um repositório de verdade: `conferir()` chama `git show`, não um dublê."""
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "config", "user.email", "prova@okmigo.local")
    _git(tmp_path, "config", "user.name", "prova")
    (tmp_path / "manifesto.json").write_text(
        json.dumps({"slug": "prova", "versao": "1.0.0",
                    "superficies": [{"nome": "a"}]}), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          capture_output=True, text=True, check=True).stdout.strip()
    monkeypatch.chdir(tmp_path)
    return base


def _escrever(**campos) -> None:
    Path("manifesto.json").write_text(json.dumps(campos), encoding="utf-8")


def test_conteudo_inalterado_passa(repo):
    falhas, iguais, novos = v.conferir(repo, ["manifesto.json"])
    assert (falhas, iguais, novos) == ([], ["manifesto.json"], [])


def test_conteudo_mudou_e_a_versao_subiu_passa(repo):
    _escrever(slug="prova", versao="1.1.0",
              superficies=[{"nome": "a"}, {"nome": "b"}])
    falhas, iguais, novos = v.conferir(repo, ["manifesto.json"])
    assert (falhas, iguais, novos) == ([], [], [])


def test_conteudo_mudou_e_a_versao_FICOU_reprova(repo):
    """⛔ O caso que o script existe para pegar: a tela velha ficaria no ar."""
    _escrever(slug="prova", versao="1.0.0",
              superficies=[{"nome": "a"}, {"nome": "b"}])
    falhas, _, _ = v.conferir(repo, ["manifesto.json"])
    assert falhas == [("manifesto.json", "1.0.0")]


def test_mudar_SO_a_versao_nao_conta_como_mudanca(repo):
    """⚠️ O caso sutil, e o que impede a checagem de se aprovar sozinha.

    Comparar os dicionários inteiros faria «trocar só o número» contar como
    conteúdo novo — e a condição que se quer provar é exatamente a outra.
    """
    _escrever(slug="prova", versao="9.9.9", superficies=[{"nome": "a"}])
    falhas, iguais, _ = v.conferir(repo, ["manifesto.json"])
    assert falhas == []
    assert iguais == ["manifesto.json"]


def test_manifesto_novo_nao_tem_base_e_nao_reprova(repo):
    Path("novo.json").write_text(json.dumps({"slug": "outro", "versao": "0.1.0"}),
                                 encoding="utf-8")
    falhas, iguais, novos = v.conferir(repo, ["novo.json"])
    assert (falhas, iguais, novos) == ([], [], ["novo.json"])


def test_varios_alvos_de_uma_vez(repo):
    """Cada alvo é julgado sozinho: um reprovado não esconde os outros."""
    _escrever(slug="prova", versao="1.0.0",
              superficies=[{"nome": "a"}, {"nome": "b"}])
    Path("novo.json").write_text(json.dumps({"slug": "o", "versao": "0.1"}),
                                 encoding="utf-8")
    falhas, iguais, novos = v.conferir(repo, ["manifesto.json", "novo.json"])
    assert [a for a, _ in falhas] == ["manifesto.json"]
    assert novos == ["novo.json"]


def test_o_codigo_de_saida_acompanha_a_decisao(repo):
    """⛔ Verde com defeito é pior que vermelho: o `main` tem de devolver 1."""
    assert v.main([repo, "manifesto.json"]) == 0
    _escrever(slug="prova", versao="1.0.0",
              superficies=[{"nome": "a"}, {"nome": "b"}])
    assert v.main([repo, "manifesto.json"]) == 1
    # e sem argumentos suficientes, 2 — nem sucesso nem falha de conteúdo
    assert v.main([]) == 2
    assert v.main(["so-a-base"]) == 2
