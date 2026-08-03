import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from .config import settings

_fernet = Fernet(settings.app_encryption_key.encode())


def encrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return _fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None


def hash_value(value: str) -> str:
    """HMAC-SHA256 determinístico (misma entrada -> mismo hash) usado para guardar IP y
    user-agent en signup_events sin persistir el dato crudo. No es para secretos que
    haya que descifrar después (a diferencia de encrypt_secret): es solo para poder
    comparar 'esta IP ya se vio antes' sin guardar la IP en texto plano, que en Chile es
    dato personal bajo la Ley 21.719."""
    return hmac.new(settings.app_encryption_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()
