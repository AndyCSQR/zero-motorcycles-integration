"""CryptoJS-compatible AES encryption for Zero Motorcycles API.

The Zero app uses CryptoJS.AES.encrypt(plaintext, stringKey) which produces
OpenSSL-compatible format: Base64("Salted__" + salt + AES-256-CBC ciphertext).

Key derivation uses EVP_BytesToKey with MD5:
    D_1 = MD5(password + salt)
    D_i = MD5(D_{i-1} + password + salt)
    key = D_1 || D_2 (32 bytes for AES-256)
    iv = D_3[:16]
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


def cryptojs_encrypt(plaintext: str, key: str) -> str:
    """Encrypt plaintext with CryptoJS.AES.encrypt(plaintext, key) semantics.

    Args:
        plaintext: The string to encrypt (UTF-8).
        key: The password string used for key derivation.

    Returns:
        Base64-encoded OpenSSL-format ciphertext string.
    """
    plaintext_bytes = plaintext.encode("utf-8")
    salt = os.urandom(8)
    key_bytes = key.encode("utf-8")

    # EVP_BytesToKey with MD5
    # D_i = MD5(D_{i-1} + password + salt)
    block1 = hashlib.md5(key_bytes + salt).digest()
    block2 = hashlib.md5(block1 + key_bytes + salt).digest()
    block3 = hashlib.md5(block2 + key_bytes + salt).digest()

    derived_key = block1 + block2  # 32 bytes -> AES-256
    iv = block3[:16]

    # AES-256-CBC with PKCS7 padding
    padder = PKCS7(128).padder()
    padded_data = padder.update(plaintext_bytes) + padder.finalize()

    cipher = Cipher(algorithms.AES(derived_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    # OpenSSL format: "Salted__" + salt + ciphertext
    result = b"Salted__" + salt + ciphertext
    return base64.b64encode(result).decode("ascii")
