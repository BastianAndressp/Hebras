import hashlib
import hmac
import json
import logging
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response


from .config import settings
from .crypto import decrypt_secret
from .db import pool
from .queue import enqueue

router = APIRouter(prefix="/webhooks", tags=["whatsapp"])
log = logging.getLogger(__name__)


PLACEHOLDER_APP_SECRETS = {"change-me", "REEMPLAZAR_CON_APP_SECRET_DE_META"}


def _is_configured(value: str | None) -> bool:
    v = (value or "").strip("'\"")
    return bool(v) and v not in PLACEHOLDER_APP_SECRETS


def is_app_secret_configured() -> bool:
    """Compat: existe un secreto GLOBAL configurado (fallback de un solo tenant / demo).
    La verificación real de un mensaje entrante usa el secreto de la empresa dueña del
    número (ver receive_webhook), no este."""
    return _is_configured(settings.whatsapp_app_secret)


def is_valid_signature(raw: bytes, signature: str | None, app_secret: str | None = None) -> bool:
    """Valida la firma HMAC-SHA256 de Meta contra un secreto dado. Si no se pasa
    app_secret explícito, usa el global (settings.whatsapp_app_secret) -- así los tests
    existentes y cualquier caller de un solo tenant siguen funcionando igual."""
    secret = (app_secret if app_secret is not None else settings.whatsapp_app_secret) or ""
    secret = secret.strip("'\"")
    if not _is_configured(secret) or not signature:
        return False
    sig_hash = signature.removeprefix("sha256=")
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    valid = hmac.compare_digest(expected, sig_hash)
    if not valid:
        log.error("Signature mismatch! expected=%s..., received=%s...", expected[:16], sig_hash[:16])
    return valid


async def _tenant_app_secret(phone_number_id: str | None) -> str | None:
    """Busca el Meta App Secret que la empresa dueña de este número cargó desde el
    dashboard (ApiKeysTab -> api_keys.whatsapp_app_secret). Cada empresa tiene su propia
    app de Meta, así que la firma de CADA mensaje se valida con el secreto de la empresa
    a la que pertenece ese phone_number_id, no con uno compartido por la plataforma."""
    if not phone_number_id:
        return None
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """select ak.whatsapp_app_secret
               from bots b join api_keys ak on ak.company_id = b.company_id
               where b.phone_number_id = $1""",
            phone_number_id,
        )
    if not row:
        return None
    return decrypt_secret(row["whatsapp_app_secret"])


async def _tenant_verify_token_matches(hub_verify_token: str) -> bool:
    """El handshake GET de suscripción de Meta no trae ningún identificador de empresa
    (todavía no hay ni un phone_number_id conectado a esa app), así que se compara el
    token recibido contra el verify token guardado de cada empresa hasta encontrar uno
    que calce."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "select whatsapp_verify_token from api_keys where whatsapp_verify_token is not null"
        )
    for row in rows:
        token = decrypt_secret(row["whatsapp_verify_token"])
        if token and hmac.compare_digest(token, hub_verify_token):
            return True
    return False


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if hub_mode != "subscribe" or not hub_verify_token:
        raise HTTPException(403, "Webhook verification failed")

    global_token = (settings.webhook_verify_token or "").strip("'\"")
    is_global_match = _is_configured(global_token) and hmac.compare_digest(global_token, hub_verify_token)
    if is_global_match or await _tenant_verify_token_matches(hub_verify_token):
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(403, "Webhook verification failed")



def inbound_messages(payload: dict):
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            for message in value.get("messages", []):
                if message.get("type") == "text":
                    yield {
                        "meta_message_id": message["id"],
                        "phone_number_id": metadata.get("phone_number_id"),
                        "contact_phone": message.get("from"),
                        "text": message.get("text", {}).get("body", "").strip(),
                        "timestamp": message.get("timestamp"),
                    }


def _extract_phone_number_id(payload: dict) -> str | None:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            phone_number_id = change.get("value", {}).get("metadata", {}).get("phone_number_id")
            if phone_number_id:
                return phone_number_id
    return None


@router.post("/whatsapp", status_code=200)
async def receive_webhook(request: Request, x_hub_signature_256: str | None = Header(default=None)):
    raw = await request.body()
    log.info("Received Webhook POST payload: %s", raw.decode("utf-8", errors="replace"))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Invalid JSON") from exc

    phone_number_id = _extract_phone_number_id(payload)
    app_secret = await _tenant_app_secret(phone_number_id)
    if not _is_configured(app_secret):
        # Sin secreto por-tenant (número aún no conectado a ninguna empresa, o esa
        # empresa nunca cargó su Meta App Secret): cae al global, para no romper el modo
        # de un solo tenant / demo que ya dependía de la variable de entorno.
        app_secret = settings.whatsapp_app_secret

    if not _is_configured(app_secret):
        raise HTTPException(503, "Integración de WhatsApp no configurada (falta el Meta App Secret)")
    if not is_valid_signature(raw, x_hub_signature_256, app_secret=app_secret):
        raise HTTPException(403, "Invalid Meta signature")

    async with pool().acquire() as conn:
        for message in inbound_messages(payload):
            inserted = await conn.fetchval(
                """insert into webhook_events (meta_message_id, payload) values ($1, $2::jsonb)
                   on conflict (meta_message_id) do nothing returning meta_message_id""",
                message["meta_message_id"], json.dumps(message),
            )
            if inserted:
                await enqueue(message)
    return {"received": True}
