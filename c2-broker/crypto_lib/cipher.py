"""AES-GCM encryption module for C2 channel.

Mathematical primitive:
    (C, T) = AES-GCM_k(P, N)

Where:
    P = plaintext command
    N = 12-byte random nonce (IV)
    k = 256-bit pre-shared key (PSK)
    C = ciphertext
    T = 16-byte authentication tag

Output format (JSON-serializable dict):
    {
        "iv": "base64_del_nonce",
        "ciphertext": "base64_del_mensaje_cifrado",
        "tag": "base64_del_tag_de_autenticacion"
    }
"""

import os
import json
import base64
import struct
from pathlib import Path
from typing import Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Cipher:
    """AES-GCM encryption/decryption with nonce reuse protection.

    Args:
        key: 256-bit (32-byte) pre-shared key (PSK).
        state_file: Optional path for persistent nonce counter.
            Si se provee, garantiza nonces únicos incluso si el agente
            se reinicia. Fundamental para C2 con agents dormidos.

    Raises:
        ValueError: If key length is not 32 bytes.
    """

    NONCE_SIZE = 12       # 96 bits — estándar AES-GCM
    TAG_SIZE = 16         # 128 bits — tag de autenticación
    KEY_SIZE = 32         # 256 bits — AES-256

    def __init__(
        self,
        key: bytes,
        state_file: Optional[Union[str, Path]] = None,
    ):
        if len(key) != self.KEY_SIZE:
            raise ValueError(
                f"Key must be {self.KEY_SIZE} bytes (256 bits), "
                f"got {len(key)} bytes ({len(key) * 8} bits)"
            )

        self._aesgcm = AESGCM(key)
        self._state_file = Path(state_file) if state_file else None
        self._counter: Optional[int] = None

        if self._state_file:
            self._counter = self._load_counter()

    # ──────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────

    def encrypt(self, plaintext: Union[str, bytes]) -> dict:
        """Encrypt plaintext and return JSON-serializable dict.

        Args:
            plaintext: String o bytes a cifrar (el comando P).

        Returns:
            Dict con iv, ciphertext y tag en base64.

        Example:
            >>> c = Cipher(key)
            >>> msg = c.encrypt("ejecutar comando X")
            >>> msg
            {'iv': 'abc...', 'ciphertext': 'xyz...', 'tag': '123...'}
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        nonce = self._generate_nonce()
        ciphertext_with_tag = self._aesgcm.encrypt(nonce, plaintext, None)

        # AES-GCM devuelve ciphertext || tag (los últimos TAG_SIZE bytes son el tag)
        ct = ciphertext_with_tag[: -self.TAG_SIZE]
        tag = ciphertext_with_tag[-self.TAG_SIZE :]

        return {
            "iv": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ct).decode("ascii"),
            "tag": base64.b64encode(tag).decode("ascii"),
        }

    def decrypt(self, data: dict) -> bytes:
        """Decrypt a message dict back to plaintext bytes.

        Args:
            data: Dict con iv, ciphertext y tag (base64).

        Returns:
            Plaintext descifrado (bytes).

        Raises:
            KeyError: Si faltan campos requeridos.
            InvalidTag: Si el tag de autenticación no coincide
                        (datos manipulados o clave incorrecta).
        """
        nonce = base64.b64decode(data["iv"])
        ciphertext = base64.b64decode(data["ciphertext"])
        tag = base64.b64decode(data["tag"])

        return self._aesgcm.decrypt(nonce, ciphertext + tag, None)

    def encrypt_to_json(self, plaintext: Union[str, bytes], **kwargs) -> str:
        """Encrypt and return JSON string directly.

        Args:
            plaintext: String o bytes a cifrar.
            **kwargs: Argumentos para json.dumps (ej. indent=2).

        Returns:
            String JSON listo para enviar por MQTT.

        Example:
            >>> payload = c.encrypt_to_json("shutdown", indent=2)
            >>> # publicar por MQTT
        """
        return json.dumps(self.encrypt(plaintext), **kwargs)

    def decrypt_from_json(self, data: str) -> bytes:
        """Decrypt from JSON string directly.

        Args:
            data: String JSON con iv, ciphertext y tag.

        Returns:
            Plaintext descifrado (bytes).
        """
        return self.decrypt(json.loads(data))

    # ──────────────────────────────────────────────
    # Nonce management (nonce reuse protection)
    # ──────────────────────────────────────────────

    def _generate_nonce(self) -> bytes:
        """Genera un nonce de 12 bytes garantizado único.

        Con state_file:
            - 8 bytes de contador monotónico persistido en disco
            - 4 bytes aleatorios
            El contador parte de un valor aleatorio de 64 bits,
            y nunca decrece. Garantiza unicidad incluso tras
            reinicios del agente.

        Sin state_file:
            - 12 bytes aleatorios (seguro si la clave es efímera).
        """
        if self._counter is not None:
            # Contador big-endian de 8 bytes (nunca se repite)
            counter_bytes = struct.pack(">Q", self._counter)
            random_bytes = os.urandom(4)  # diversidad intra-mensaje
            self._counter += 1
            self._save_counter()
            return counter_bytes + random_bytes

        # Modo stateless: puramente aleatorio
        return os.urandom(self.NONCE_SIZE)

    def _load_counter(self) -> int:
        """Lee el contador del archivo de estado, o arranca de un valor aleatorio."""
        if self._state_file and self._state_file.exists():
            try:
                return int(self._state_file.read_text().strip())
            except (ValueError, OSError):
                pass  # archivo corrupto -> arrancar de nuevo
        # Primera ejecución o corrupto: arrancar de un offset aleatorio
        return int.from_bytes(os.urandom(8), "big")

    def _save_counter(self):
        """Persiste el contador atómicamente (write-then-rename)."""
        if not self._state_file:
            return
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._state_file.with_suffix(".tmp")
        tmp.write_text(str(self._counter))
        tmp.rename(self._state_file)


def generate_key() -> bytes:
    """Genera una clave AES-256 criptográficamente segura.

    Returns:
        32 bytes listos para usar como PSK.

    Example:
        >>> key = generate_key()
        >>> len(key)
        32
        >>> # Guardar en archivo seguro
        >>> with open("psk.key", "wb") as f:
        ...     f.write(key)
    """
    return AESGCM.generate_key(bit_length=256)


# ──────────────────────────────────────────────
# CLI: generar clave desde terminal
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "genkey":
        key = generate_key()
        out = sys.argv[2] if len(sys.argv) > 2 else "psk.key"
        with open(out, "wb") as f:
            f.write(key)
        print(f"[+] Key generated: {out} ({len(key)} bytes)")
        print(f"[+] Base64:       {base64.b64encode(key).decode('ascii')}")
    else:
        print("Usage: python cipher.py genkey [output_file]")
        print("  Default output: psk.key")
