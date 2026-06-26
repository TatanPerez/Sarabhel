import json
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

    def test_json_round_trip(self):
        """encrypt_to_json + decrypt_from_json deben ser inversos."""
        c = Cipher(self.key)
        original = {"task_id": "T001", "command": "ipconfig", "command_type": "shell"}
        original_str = json.dumps(original)

        # Cifrar a JSON string (desde string plano)
        encrypted_json = c.encrypt_to_json(original_str)

        # Verificar que es un string JSON válido con los campos esperados
        parsed = json.loads(encrypted_json)
        self.assertIn("iv", parsed)
        self.assertIn("ciphertext", parsed)
        self.assertIn("tag", parsed)

        # Descifrar desde JSON string
        decrypted = c.decrypt_from_json(encrypted_json)
        self.assertEqual(decrypted.decode(), original_str)

    def test_encrypt_to_json_from_dict(self):
        """encrypt_to_json debe aceptar dict directamente (como usa bridge.py)."""
        c = Cipher(self.key)
        original = {"task_id": "T002", "command": "whoami"}
        encrypted_json = c.encrypt_to_json(original)
        parsed = json.loads(encrypted_json)
        self.assertIn("iv", parsed)
        self.assertIn("ciphertext", parsed)
        self.assertIn("tag", parsed)
        decrypted = c.decrypt(parsed)
        self.assertEqual(json.loads(decrypted), original)

    def test_bytes_plaintext(self):
        """Debe aceptar bytes como entrada."""
        c = Cipher(self.key)
        msg = b"comando_bytes"
        encrypted = c.encrypt(msg)
        decrypted = c.decrypt(encrypted)
        self.assertEqual(decrypted, msg)


if __name__ == "__main__":
    unittest.main()
