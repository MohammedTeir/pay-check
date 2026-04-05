"""
Crypto service — AES-like encryption using only Python standard library.
No external dependencies (no cryptography package needed on Termux).

Uses HMAC-SMAC256 in counter mode as a stream cipher, equivalent to CTR mode encryption.
"""

import base64
import hashlib
import hmac
import os
from config import config


def _derive_key(encryption_key: str) -> bytes:
    """Derive a 32-byte key from the encryption key string via SHA-256."""
    return hashlib.sha256(encryption_key.encode()).digest()


def _hmac_ctr(key: bytes, data: bytes, nonce: bytes) -> bytes:
    """
    HMAC-based stream cipher (CTR mode).
    Generates a keystream using HMAC-SHA256 with a nonce + counter.
    XORs the keystream with the data.
    """
    result = bytearray()
    block_size = 32  # HMAC-SHA256 output length

    for i in range(0, len(data), block_size):
        # Counter block = nonce + counter (8 bytes)
        counter_block = nonce + i.to_bytes(8, "big")
        # Generate keystream block
        keystream_block = hmac.new(key, counter_block, hashlib.sha256).digest()
        # XOR data with keystream
        chunk = data[i:i + block_size]
        for j in range(len(chunk)):
            result.append(chunk[j] ^ keystream_block[j])

    return bytes(result)


def encrypt(plaintext: str) -> str:
    """
    Encrypt a string. Returns base64-encoded ciphertext.
    Format: nonce(12 bytes) || encrypted_data, all base64-encoded.
    """
    key = _derive_key(config.encryption_key)
    nonce = os.urandom(12)  # 96-bit nonce for CTR mode
    data = plaintext.encode("utf-8")
    encrypted = _hmac_ctr(key, data, nonce)
    return base64.b64encode(nonce + encrypted).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a base64-encoded ciphertext. Returns the original string.
    Raises ValueError on failure.
    """
    try:
        raw = base64.b64decode(ciphertext)
        if len(raw) < 13:  # At least nonce(12) + 1 byte
            raise ValueError("Ciphertext too short")

        nonce = raw[:12]
        encrypted = raw[12:]

        key = _derive_key(config.encryption_key)
        decrypted = _hmac_ctr(key, encrypted, nonce)

        return decrypted.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"Failed to decrypt: invalid key or corrupted data") from e
