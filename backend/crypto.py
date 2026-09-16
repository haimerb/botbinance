import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise RuntimeError(
        "ENCRYPTION_KEY no configurado. "
        "Genera uno con: python -c \"import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\" "
        "y añádelo a tu archivo .env"
    )

_kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=b"binance_bot_salt",
    iterations=100000,
)
_key = base64.urlsafe_b64encode(_kdf.derive(ENCRYPTION_KEY.encode()))
_fernet = Fernet(_key)


def encrypt_value(value: str) -> str:
    if not value:
        return value
    return _fernet.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    if not value:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except Exception:
        return value