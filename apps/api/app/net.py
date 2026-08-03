import ipaddress

from fastapi import Request

from .config import settings


def _trusted_networks() -> list[str]:
    raw = (settings.trusted_proxy_networks or "").strip()
    return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]


def _is_trusted_proxy(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for network in _trusted_networks():
        try:
            if addr in ipaddress.ip_network(network, strict=False):
                return True
        except ValueError:
            continue
    return False


def get_client_ip(request: Request) -> str:
    """IP real del visitante. Por defecto (TRUSTED_PROXY_NETWORKS vacío) siempre
    devuelve el peer directo del socket, que es lo correcto ahora que el navegador le
    habla directo a esta API (ver NEXT_PUBLIC_API_URL en docker-compose.yml). Solo si el
    salto directo viene de una red declarada como proxy de confianza (para cuando en
    producción se ponga un reverse proxy real delante) se usa X-Forwarded-For — nunca se
    confía en ese header desde un origen no declarado, porque cualquier cliente puede
    falsificarlo."""
    direct_ip = request.client.host if request.client else "unknown"
    if direct_ip == "unknown" or not _is_trusted_proxy(direct_ip):
        return direct_ip
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct_ip
    # X-Forwarded-For: cliente_original, proxy1, proxy2, ... — el primer valor es el
    # cliente original.
    parts = [chunk.strip() for chunk in forwarded.split(",") if chunk.strip()]
    return parts[0] if parts else direct_ip
