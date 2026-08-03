from datetime import datetime, timedelta, timezone
from app.auth_router import generate_jwt, hash_password, verify_password


def test_password_hashing():
    password = "SecretPassword123"
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword", hashed)


def test_jwt_generation():
    token = generate_jwt("u1", "c1", "owner", "test@example.com")
    assert isinstance(token, str)
    assert len(token) > 20
