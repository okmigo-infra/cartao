"""⭐ OMINFRA-1328: `okmigoConversaDoGrupo` — o serviço nomeia a coisa dele, o
produto abre a conversa. ⛔ Nada de grupo vindo do serviço."""
import unittest

from okmigo_cartao import ContratoDoSdkInvalido, ConversaDoGrupo
from okmigo_cartao.crivo import validar


def _cartao(*corpo):
    return {"type": "AdaptiveCard", "version": "1.5", "body": list(corpo)}


class ConversaDoGrupoTest(unittest.TestCase):
    def test_compila(self):
        self.assertEqual(ConversaDoGrupo("Abrir conversa", "{id}").compilar(),
                         {"type": "okmigoConversaDoGrupo", "rotulo": "Abrir conversa", "ref": "{id}"})

    def test_sdk_recusa_sem_ref_ou_longo(self):
        with self.assertRaises(ContratoDoSdkInvalido):
            ConversaDoGrupo("Abrir conversa", "")
        with self.assertRaises(ContratoDoSdkInvalido):
            ConversaDoGrupo("Abrir conversa", "x" * 81)
        with self.assertRaises(ContratoDoSdkInvalido):
            ConversaDoGrupo("", "t-1")

    def test_o_crivo_passa_so_rotulo_e_ref(self):
        tela, erro = validar(_cartao({"type": "okmigoConversaDoGrupo", "rotulo": "Abrir conversa", "ref": "t-1",
                                      "grupo": "00000000-0000-0000-0000-000000000001", "id": "x",
                                      "url": "https://golpe.example"}))
        self.assertIsNone(erro)
        (no,) = tela["corpo"]
        self.assertEqual(no["tipo"], "conversa_do_grupo")
        self.assertEqual((no["rotulo"], no["ref"]), ("Abrir conversa", "t-1"))
        for campo in ("grupo", "url"):
            self.assertNotIn(campo, no)

    def test_o_crivo_some_sem_ref_sem_rotulo_ou_longo(self):
        for no in ({"type": "okmigoConversaDoGrupo", "rotulo": "Abrir conversa"},
                   {"type": "okmigoConversaDoGrupo", "ref": "t-1"},
                   {"type": "okmigoConversaDoGrupo", "rotulo": "Abrir conversa", "ref": "x" * 81}):
            tela, _ = validar(_cartao(no, {"type": "TextBlock", "text": "fica"}))
            self.assertEqual([n["tipo"] for n in tela["corpo"]], ["texto"], no)


if __name__ == "__main__":
    unittest.main()
