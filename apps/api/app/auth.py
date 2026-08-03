from dataclasses import dataclass
from fastapi import Header, HTTPException
import jwt
from .config import settings


@dataclass
class Principal:
    user_id: str
    company_id: str
    role: str


async def require_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return Principal(str(claims["sub"]), str(claims["company_id"]), str(claims.get("role", "staff")))
    except (jwt.InvalidTokenError, KeyError) as exc:
        raise HTTPException(401, "Invalid session") from exc


def require_owner(principal: Principal) -> Principal:
    if principal.role != "owner":
        raise HTTPException(403, "Owner role required")
    return principal


def require_write_access(principal: Principal) -> Principal:
    if principal.role == "solo-lectura":
        raise HTTPException(403, "Write permission required (read-only role)")
    return principal


