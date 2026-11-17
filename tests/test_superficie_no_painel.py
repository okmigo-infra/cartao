"""OMINFRA-1341: a superfície que aparece no Painel do Gerenciar (0.32.0)."""
from okmigo_cartao.sdk import Fonte, Superficie, Tela, Texto


def _sup(**kw) -> Superficie:
    tela = Tela("Hoje", (Texto("oi"),))
    return Superficie("hoje", "Hoje", "Hoje", "radar", "o resumo de hoje", Fonte("hoje"), tela, **kw)


def test_so_vai_ao_painel_quem_pede():
    assert "painel" not in _sup().compilar()
    assert _sup(painel=True).compilar()["painel"] is True
