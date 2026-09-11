"""Ler o manifesto: a superfície certa, e o contrato tirado das operações."""
import unittest

from okmigo_cartao.manifesto import e_manifesto, escolher, operacoes, superficies

M = {
    "slug": "exemplo", "versao": "1.0.0",
    "operacoes": [
        {"nome": "listar", "efeitos": "leitura"},
        {"nome": "salvar", "efeitos": "escrita"},
        {"nome": "baixar"},                      # sem efeitos = leitura
        {"nome": "", "efeitos": "escrita"},      # sem nome, ignorada
        "lixo",
    ],
    "superficies": [
        {"nome": "a", "cartao": {"type": "AdaptiveCard", "body": [{"type": "TextBlock", "text": "A"}]}},
        {"nome": "sem-cartao"},
    ],
}


class ManifestoTest(unittest.TestCase):
    def test_reconhece_manifesto_e_nao_cartao(self):
        self.assertTrue(e_manifesto(M))
        self.assertFalse(e_manifesto({"type": "AdaptiveCard", "body": []}))
        self.assertFalse(e_manifesto([]))

    def test_operacoes_viram_escrituras_e_leituras(self):
        esc, lei = operacoes(M)
        self.assertEqual(esc, {"salvar"})
        self.assertEqual(lei, {"listar", "baixar"})

    def test_escolher_a_superficie_ou_dizer_quais_ha(self):
        self.assertEqual(escolher(M, "a")["body"][0]["text"], "A")
        with self.assertRaises(KeyError) as c:
            escolher(M, "zzz")
        self.assertIn("a, sem-cartao", c.exception.args[0])
        with self.assertRaises(KeyError):
            escolher(M, "sem-cartao")
        self.assertEqual(superficies(M), ["a", "sem-cartao"])


if __name__ == "__main__":
    unittest.main()
