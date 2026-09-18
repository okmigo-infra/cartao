"""O script que abre a PR de promoção, migrado de ONZE cópias sem teste.

⛔ **Nenhuma das onze tinha teste**, e a guarda do ghcr que vive aqui já
quebrou uma vez por isso: a primeira versão dela lia «todo ghcr que aparece na
árvore» e recusava promoção legítima no okmigo, onde os manifestos citam
quatorze pacotes — entre eles um exemplo em prosa, um molde, e os runners da
esteira, que têm etiqueta própria.

⚠️ **Guarda que dá alarme falso é guarda que alguém desliga**, e é por isso que
o caso da prosa e o do molde estão aqui como casos, não como comentário.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from okmigo_cartao.esteira import abrir_pr_de_promocao as p

SHA = "abc1234"


def _arvore(raiz: Path, arquivos: dict[str, str]) -> None:
    for caminho, texto in arquivos.items():
        alvo = raiz / caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8")


def test_acha_a_imagem_amarrada_a_este_sha(tmp_path: Path):
    _arvore(tmp_path, {"k8s/prod/10-api.yaml":
                       f"      - image: ghcr.io/okmigo-infra/app-api:{SHA}\n"})
    assert p.pacotes_no_sha(SHA, str(tmp_path)) == {"app-api"}


def test_acha_pela_forma_do_kustomize(tmp_path: Path):
    _arvore(tmp_path, {"k8s/prod/kustomization.yaml": f'''images:
  - name: app-dev-api
    newName: ghcr.io/okmigo-infra/app-api
    newTag: "{SHA}"
'''})
    assert p.pacotes_no_sha(SHA, str(tmp_path)) == {"app-api"}


def test_IGNORA_o_exemplo_em_prosa(tmp_path: Path):
    """⛔ O caso que derrubou a primeira versão: `ghcr.io/ORG/nome` sem etiqueta."""
    _arvore(tmp_path, {"k8s/README.yaml":
                       "# exemplo: ghcr.io/ORG/nome — troque pelo seu\n"})
    assert p.pacotes_no_sha(SHA, str(tmp_path)) == set()


def test_IGNORA_quem_tem_etiqueta_PROPRIA(tmp_path: Path):
    """⛔ Os runners da esteira não são promovidos junto, e citam ghcr."""
    _arvore(tmp_path, {"k8s/esteira/20-runner.yaml":
                       "      - image: ghcr.io/okmigo-infra/runner:v9\n"
                       f"      - image: ghcr.io/okmigo-infra/app-api:{SHA}\n"})
    assert p.pacotes_no_sha(SHA, str(tmp_path)) == {"app-api"}


def test_IGNORA_o_kustomize_com_outra_etiqueta(tmp_path: Path):
    _arvore(tmp_path, {"k8s/prod/kustomization.yaml": '''images:
  - name: outro
    newName: ghcr.io/okmigo-infra/outro-api
    newTag: "7570697"
'''})
    assert p.pacotes_no_sha(SHA, str(tmp_path)) == set()


def test_so_olha_dentro_de_k8s_e_so_yaml(tmp_path: Path):
    _arvore(tmp_path, {
        f"docker/compose.yml": f"image: ghcr.io/okmigo-infra/fora:{SHA}\n",
        f"k8s/prod/notas.md": f"image: ghcr.io/okmigo-infra/markdown:{SHA}\n",
        f"k8s/prod/10-api.yaml": f"image: ghcr.io/okmigo-infra/dentro:{SHA}\n",
    })
    assert p.pacotes_no_sha(SHA, str(tmp_path)) == {"dentro"}


def test_descobre_os_nomes_em_vez_de_decorar(tmp_path: Path):
    """⚠️ Um mapa de nomes aqui seria mais uma cópia para envelhecer — e,
    envelhecida, faria o guarda APROVAR sem ter olhado."""
    _arvore(tmp_path, {"k8s/a.yaml":
                       f"image: ghcr.io/okmigo-infra/comcontabil-api:{SHA}\n"
                       f"image: ghcr.io/okmigo-infra/radaria:{SHA}\n"})
    assert p.pacotes_no_sha(SHA, str(tmp_path)) == {"comcontabil-api", "radaria"}


def test_as_credenciais_do_ghcr_vem_na_ordem_certa(monkeypatch):
    """⭐ O `GHCR_TOKEN` primeiro: o da corrida não alcança pacote sem vínculo."""
    monkeypatch.setenv("GHCR_TOKEN", "do-ghcr")
    monkeypatch.setenv("GH_TOKEN", "da-corrida")
    assert p.credenciais_do_ghcr() == ["do-ghcr", "da-corrida"]
    monkeypatch.delenv("GHCR_TOKEN")
    assert p.credenciais_do_ghcr() == ["da-corrida"]
    monkeypatch.delenv("GH_TOKEN")
    assert p.credenciais_do_ghcr() == []


def test_sem_pacote_nenhum_o_guarda_RECUSA(tmp_path, monkeypatch):
    """⛔⛔ O caso mais importante: nada encontrado é RECUSA, não «tudo bem».

    Aprovar aqui seria desligar o guarda — e um guarda desligado aprova a
    promoção de um artefato que não existe no registry.
    """
    monkeypatch.setenv("GHCR_TOKEN", "t")
    monkeypatch.setattr(p, "pacotes_no_sha", lambda *a, **k: set())
    assert p.a_imagem_existe(SHA) is False


def test_todas_presentes_aprova(monkeypatch):
    monkeypatch.setenv("GHCR_TOKEN", "t")
    monkeypatch.setattr(p, "pacotes_no_sha", lambda *a, **k: {"a", "b"})
    monkeypatch.setattr(p, "tem_imagem", lambda pac, tag, tok: True)
    assert p.a_imagem_existe(SHA) is True


def test_UMA_ausente_reprova(monkeypatch):
    monkeypatch.setenv("GHCR_TOKEN", "t")
    monkeypatch.setattr(p, "pacotes_no_sha", lambda *a, **k: {"a", "b"})
    monkeypatch.setattr(p, "tem_imagem",
                        lambda pac, tag, tok: pac != "b")
    assert p.a_imagem_existe(SHA) is False


def test_nao_consegui_perguntar_tambem_reprova(monkeypatch):
    """⚠️ Dúvida não é aprovação. `None` é «não consegui», e o guarda recusa."""
    monkeypatch.setenv("GHCR_TOKEN", "t")
    monkeypatch.setattr(p, "pacotes_no_sha", lambda *a, **k: {"a"})
    monkeypatch.setattr(p, "tem_imagem", lambda pac, tag, tok: None)
    assert p.a_imagem_existe(SHA) is False


def test_sem_credencial_nenhuma_reprova(monkeypatch):
    monkeypatch.delenv("GHCR_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert p.a_imagem_existe(SHA) is False


def test_fecha_so_as_da_esteira_e_nunca_a_que_se_mantem(monkeypatch):
    """⚠️ O filtro é DUPLO, e cada metade sozinha erraria: pela base fecharia
    PR de gente que mira `prod`; pelo nome fecharia uma de outro destino."""
    abertas = [
        {"number": 1, "head": {"ref": "promover-velha"}},
        {"number": 2, "head": {"ref": "promover-nova"}},
        {"number": 3, "head": {"ref": "feat/uma-pessoa"}},
    ]
    chamadas: list = []

    def falso_api(caminho, dados=None, metodo=None):
        chamadas.append((caminho, metodo))
        return abertas if caminho.endswith("base=prod") else {}

    monkeypatch.setattr(p, "api", falso_api)
    p.fechar_superadas("okmigo-infra/app", manter="promover-nova")

    fechadas = [c for c, m in chamadas if m == "PATCH"]
    assert fechadas == ["/repos/okmigo-infra/app/pulls/1"], chamadas
    # e comentou ANTES de fechar: PR que some sem explicação faz procurar
    assert ("/repos/okmigo-infra/app/issues/1/comments", None) in chamadas


def test_sem_argumentos_suficientes_devolve_2(capsys):
    assert p.main([]) == 2
    assert p.main(["so-o-sha"]) == 2
