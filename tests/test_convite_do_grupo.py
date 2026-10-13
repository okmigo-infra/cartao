"""⭐ OMINFRA-1237: `okmigoConviteDoGrupo` — o serviço nomeia a coisa dele, o
produto gera o link. ⛔ Nada de link vindo do serviço."""
import unittest

from okmigo_cartao import ContratoDoSdkInvalido, ConviteDoGrupo
from okmigo_cartao.crivo import validar


def _cartao(*corpo):
    return {"type": "AdaptiveCard", "version": "1.5", "body": list(corpo)}


class ConviteDoGrupoTest(unittest.TestCase):
    def test_compila(self):
        self.assertEqual(ConviteDoGrupo("Convidar alunos", "{id}").compilar(),
                         {"type": "okmigoConviteDoGrupo", "rotulo": "Convidar alunos", "ref": "{id}"})

    def test_sdk_recusa_sem_ref_ou_longo(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            ConviteDoGrupo("Convidar", "")
        with self.assertRaises(ContratoDoSdkInvalido):
            ConviteDoGrupo("Convidar", "x" * 81)

    def test_o_crivo_passa_so_rotulo_e_ref(self):
        tela, erro = validar(_cartao({"type": "okmigoConviteDoGrupo", "rotulo": "Convidar alunos", "ref": "t-1",
                                      "link": "https://golpe.example/entrar", "url": "https://golpe.example"}))
        self.assertIsNone(erro)
        (no,) = tela["corpo"]
        self.assertEqual(no["tipo"], "convite_do_grupo")
        self.assertEqual((no["rotulo"], no["ref"]), ("Convidar alunos", "t-1"))
        self.assertNotIn("link", no)
        self.assertNotIn("url", no)

    def test_o_crivo_some_sem_ref_sem_rotulo_ou_longo(self):
        for no in ({"type": "okmigoConviteDoGrupo", "rotulo": "Convidar"},
                   {"type": "okmigoConviteDoGrupo", "ref": "t-1"},
                   {"type": "okmigoConviteDoGrupo", "rotulo": "Convidar", "ref": "x" * 81}):
            tela, _ = validar(_cartao(no, {"type": "TextBlock", "text": "fica"}))
            self.assertEqual([n["tipo"] for n in tela["corpo"]], ["texto"], no)


if __name__ == "__main__":
    unittest.main()
