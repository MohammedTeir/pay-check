"""
Tests for the Fernet encryption/decryption service.
"""

import os
import pytest
from cryptography.fernet import Fernet
from services.crypto_service import encrypt, decrypt


class TestCryptoService:
    """Encryption/decryption round-trip tests."""

    @pytest.fixture(autouse=True)
    def setup_encryption_key(self, monkeypatch):
        """Set a test encryption key before each test."""
        key = Fernet.generate_key().decode()
        # Patch the config to use our test key
        import config
        config.config.encryption_key = key

        # Reset the fernet singleton
        import services.crypto_service as cs
        cs._fernet = Fernet(key.encode())

    def test_encrypt_decrypt_round_trip(self):
        """Encrypted data should be decryptable back to original."""
        plaintext = "sk_test_123456789abcdef"
        ciphertext = encrypt(plaintext)
        decrypted = decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encryption_produces_different_output(self):
        """Same plaintext should produce different ciphertext (IV randomness)."""
        plaintext = "test_secret"
        ct1 = encrypt(plaintext)
        ct2 = encrypt(plaintext)
        assert ct1 != ct2  # Different IVs

    def test_decrypt_empty_string(self):
        """Empty string should round-trip correctly."""
        ciphertext = encrypt("")
        assert decrypt(ciphertext) == ""

    def test_decrypt_special_characters(self):
        """Special characters should be preserved."""
        plaintext = "sk_test_!@#$%^&*()_+-=[]{}|;':\",./<>?"
        assert decrypt(encrypt(plaintext)) == plaintext

    def test_decrypt_invalid_ciphertext_raises(self):
        """Invalid ciphertext should raise ValueError."""
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt("not_a_valid_ciphertext")

    def test_decrypt_tampered_ciphertext_raises(self):
        """Tampered ciphertext should raise ValueError."""
        ciphertext = encrypt("secret")
        tampered = ciphertext[:-1] + ("A" if ciphertext[-1] != "A" else "B")
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt(tampered)

    def test_long_string(self):
        """Long strings should encrypt/decrypt correctly."""
        plaintext = "sk_live_" + "a" * 1000
        assert decrypt(encrypt(plaintext)) == plaintext
