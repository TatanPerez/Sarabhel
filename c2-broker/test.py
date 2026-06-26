import unittest
import os
from crypto_lib.cipher import Cipher, generate_key
from cryptography.exceptions import InvalidTag


class TestCryptoLib(unittest.TestCase):
    def setUp(self):
        self.key = generate_key()
        self.state_file = "test_nonce.state"
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

    def test_basic_encryption_decryption(self):
        c = Cipher(self.key)
        msg = "ls -la"
        encrypted = c.encrypt(msg)
        decrypted = c.decrypt(encrypted)
        self.assertEqual(decrypted.decode(), msg)

    def test_nonce_persistence(self):
        c1 = Cipher(self.key, state_file=self.state_file)
        c1.encrypt("cmd1")

        c2 = Cipher(self.key, state_file=self.state_file)
        msg = c2.encrypt("cmd2")

        self.assertEqual(c2.decrypt(msg).decode(), "cmd2")

    def test_tamper_protection(self):
        c = Cipher(self.key)
        encrypted = c.encrypt("comando_original")

        # Manipulamos el ciphertext
        encrypted["ciphertext"] = "A" + encrypted["ciphertext"][1:]

        # Esto deberia fallar (Integridad garantizada)
        with self.assertRaises(InvalidTag):
            c.decrypt(encrypted)


if __name__ == "__main__":
    unittest.main()
