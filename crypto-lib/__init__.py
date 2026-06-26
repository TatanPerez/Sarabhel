"""crypto-lib — AES-GCM encryption module for C2 channel.

Usage:
    from cipher import Cipher, generate_key

    # Generar clave (una sola vez)
    key = generate_key()

    # Cifrar
    c = Cipher(key, state_file="nonce.state")
    msg = c.encrypt("comando")
    # -> {"iv": "...", "ciphertext": "...", "tag": "..."}

    # Descifrar
    plain = c.decrypt(msg)
    # -> b"comando"
"""

from .cipher import Cipher, generate_key

__all__ = ["Cipher", "generate_key"]
